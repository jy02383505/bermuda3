#! /usr/bin/env python
# -*- coding: utf-8 -*-
# 冰柏作
import hashlib
import threading
import urllib
import datetime
import time
import logging
import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
#from pymongo import ReplicaSetConnection, ReadPreference, Connection
import xlwt
from collections import Counter, OrderedDict, defaultdict
from core.database import query_db_session
from util.emailSender import EmailSender
import traceback


# DEFAULT_HOST = '172.16.12.135'
# BAK_HOST = '172.16.12.136'
# shanghai host = 101.251.97.201
# test host = 223.202.52.82
# online = 223.202.52.52

# conn = ReplicaSetConnection('%s:27017,%s:27017,%s:27017' % ('172.16.12.136', '172.16.12.135', '172.16.12.134'), replicaSet ='bermuda_db')['bermuda']
# conn = Connection("223.202.52.82", 27017)['bermuda']
conn = query_db_session()
# DEFAULT_PORT = 27017
# DEFAULT_DB = 'bermuda'
# DEFAULT_COLL = 'device'
STATUS_LIST = ['0', '204', '404', '503']
CBU_LIST = ['CBU']
# CBU_LIST = ['GlobalCDN', 'CBU', 'RDB', '文件分发服务', \
#             '页面加速服务', '文件分发下载服务']
ACCESS_ID = 'refresh'
PRIVATE_KEY = '965a13e40f3272ab4e78972766d84aa4'
LIMIT = 5000
# URL_HEAD = 'http://rcmsapi.chinacache.com:36000/devices/department/%s'
# URL_HEAD = 'http://rcmsapi-private.chinacache.net:36000/devices/department/%s'
# URL_HEAD = 'https://ris.chinacache.com/v2/resource/server?access_id=ris&timestamp=1418614056&token=b4e8386551e9eac6cde972ba09d4be4d'
URL_HEAD = 'http://ris.chinacache.com/v2/resource/server?access_id={0}&timestamp={1}&token={2}&department={3}&limit=5000&serverstatus=1&offset={4}'
# 定义null
global null
null = ''
source_device_dict = {}
LOG_DIR = '/Application/bermuda3/logs/outputxls/'
LOG_FILENAME = '/Application/bermuda3/logs/count_device.log'
logging.basicConfig(filename=LOG_FILENAME,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger('count_deivce')
logger.setLevel(logging.DEBUG)

# mail address
# ads_from = 'noreply@chinacache.com'
ads_from = 'nocalert@chinacache.com'
ads_to = ['zhihong.fan@chinacache.com', 'shi.hou@chinacache.com', 'jian.liu@chinacache.com',
          'leo.fu@chinacache.com', 'yuan.yao@chinacache.com', 'yue.lou@chinacache.com',
          'huichao.xie@chinacache.com', 'huan.ma@chinacache.com', 'shanliang.yu@chinacache.com',
          'hongtao.yang@chinacache.com', 'hongan.zhang@chinacache.com', 'haixin.yuan@chinacache.com',
          'hao.yu@chinacache.com']
# ads_to = ['huan.ma@chinacache.com']

def generate_token():
    """
    generate token

    :return: timestamp, token
    """
    timestamp = int(time.time())
    gen_str = "{0}{1}{2}".format(ACCESS_ID,PRIVATE_KEY,timestamp)
    print(gen_str)
    # timestamp2 = time.mktime(datetime.datetime.now().timetuple())
    token = hashlib.new("md5", gen_str).hexdigest()
    print(timestamp, token)
    return timestamp, token



def get_devices(department, timestamp, token, offset):
    get_url = URL_HEAD.format(ACCESS_ID, timestamp, token, department, offset)
    print(get_url)
    got_lst = eval(urllib.request.urlopen(get_url, timeout=100).read())
    print(department, '\t', len(got_lst))
    return got_lst['data']['list'], int(got_lst['data']['total'])


def get_devices_from_rcms():
    # global source_data_lst, department, got_lst, source_device_lst, source_device_dict, dev_data
    source_data_lst = []
    timestamp, token = generate_token()
    for department in CBU_LIST:
        got_lst, total = get_devices(department, timestamp, token, 0)
        source_data_lst.extend(got_lst)  # eval() or json.loads() 需import json
        if total > LIMIT:
            offsets = total / LIMIT
            for num in range(1, offsets+1):
                offset = LIMIT * num + 1
                got_lst, total = get_devices(department, timestamp, token, offset)
                source_data_lst.extend(got_lst)

    source_device_lst = []
    # source_device_dict = {}
    for dev_data in source_data_lst:
        if dev_data['Description'] not in source_data_lst:
            source_device_dict[str(dev_data['Description'])] = {}#dev_data['Description']
    print(source_device_dict)
    # return source_device_dict


def get_data(connect, date_day, date_month, date_year, h, real_date):
    global source_device_dict
    import datetime
    e_hour_time = time.time()
    b_hour = str(h)
    e_hour = str(h + 1)
    print("%s-%s-%s %s:00:00" % (date_year, date_month, date_day, b_hour))
    leftend = datetime.datetime.strptime("%s-%s-%s %s:00:00" % (date_year, date_month, date_day, b_hour),
                                         "%Y-%m-%d %H:%M:%S")
    if h == 23:
        rightend = datetime.datetime.combine(real_date, datetime.time.max)
    else:
        rightend = datetime.datetime.strptime("%s-%s-%s %s:00:00" % (date_year, date_month, date_day, e_hour),
                                              "%Y-%m-%d %H:%M:%S")
    print(leftend, rightend)
    num = 0
    for doc in connect.find({'created_time': {'$gte': leftend, '$lt': rightend}}):
        for device in list(doc['devices'].keys()):
            if device in source_device_dict:  # here
                # new_dev = str(device)

                code = str(doc['devices'][device]['code'])
                device = str(device)

                if h not in list(source_device_dict[device].keys()):
                    code_dic = defaultdict(int) #增加默认值 'CNC-BZ-3-3u1': defaultdict(<type 'int'>, {'0': 0, '404': 0, '204': 0, '503': 0}
                    for c in STATUS_LIST:
                        code_dic[c] += 0
                    source_device_dict[device][h] = code_dic
                source_device_dict[device][h][code] += 1



                num += 1
    e_hour_end = time.time()
    print(h, e_hour_end - e_hour_time, num)
    # print source_device_dict
    logger.debug("process %s - %s time:%s ,count : %s" % (leftend, rightend, e_hour_end - e_hour_time, num))
    # return data_count, name_dict


def merge_dic(source_dict):
    """
    按设备名合并字典

    :{'CNC-BZ-3-3u4': {12: {'503': 3,'200':2}, 13: {'503': 4}}}
    to:{'CNC-BZ-3-3u4': {'200': 2, '503': 7}}
    """

    tag_dic = {}
    for dev_name in source_dict:
        cc = Counter()
        for hour in source_dict[dev_name]:
            cc.update(Counter(source_dict[dev_name][hour]))
        tag_dic[dev_name] = dict(cc)
        if not tag_dic[dev_name]:   #增加默认值'CNC-BZ-3-3u1': defaultdict(<type 'int'>, {'0': 0, '404': 0, '204': 0, '503': 0}
            code_dic = defaultdict(int)
            for c in STATUS_LIST:
                code_dic[c] += 0
            tag_dic[dev_name] = code_dic
    print(tag_dic)
    return tag_dic


def write_excel(connect_time, date_str, name_dict, name_of_devices, starttime):
    # 创建excel
    wbk = xlwt.Workbook()
    sheet = wbk.add_sheet('sheet 1')
    sheet.write(0, 0, 'device \ ISP, status')
    sheet.write(0, 1, 'ISP')

    sheet.write(0, len(STATUS_LIST) + 2, 'total')
    for j in range(0, len(STATUS_LIST)):
        sheet.write(0, j + 2, STATUS_LIST[j])
    for i, device in enumerate(name_of_devices):
        sheet.write(i + 1, 0, device)
        sheet.write(i + 1, 1, device.split('-')[0])
        total = 0
        for jj in range(0, len(STATUS_LIST)):
            num = name_of_devices[device][STATUS_LIST[jj]]
            sheet.write(i + 1, jj + 2, num)
            total += num
        sheet.write(i + 1, len(STATUS_LIST)+2, total)


    wbk.save('%scount_device_status_output%s.xls' % (LOG_DIR, date_str))
    endtime = time.time()
    run_time = endtime - starttime
    logger.debug("process xls time:%s " % (endtime - connect_time))
    print('Total time: ', run_time)
    return run_time


def process(date_str):

    starttime = time.time()
    print(starttime)
    logger.debug('start:%s' % starttime)
    # 读取BU所属设备
    get_devices_from_rcms()
    rcmstime_time = time.time()
    print('Total devices number:\t', len(source_device_dict))
    logger.debug('Total devices number:%s,take time:%s' % (len(source_device_dict), rcmstime_time - starttime))
    # 开始读取服务器数据
    try:
        connect = conn['device']
    except Exception:
        logger.error(traceback.format_exc())
        return

    print(connect)
    date_year = int(date_str[:4])
    date_month = int(date_str[4:6])
    date_day = int(date_str[6:])
    real_date = datetime.date(date_year, date_month, date_day)
    #leftend = datetime.combine(real_date,time.min)
    #rightend = datetime.combine(real_date,time.max)
    name_dict = {}  #记录新设备名字
    data_count = 0
    print('start connect mongodb')
    thread_list = list()
    for h in range(24):
        # if h < 23:
        #      continue
        # 先创建线程对象
        thread_name = "Thread #%s" % (h)
        thread_list.append(threading.Thread(target = get_data, name = thread_name, args = (connect,date_day, date_month, date_year, h, real_date)))
        # get_data(connect,date_day, date_month, date_year, h, real_date)
         # 启动所有线程
    for thread in thread_list:
        thread.start()

    # 主线程中等待所有子线程退出
    for thread in thread_list:
        thread.join()
    print('end',source_device_dict)

    connect_time = time.time()
    logger.debug("process database take time:%s " % (connect_time - rcmstime_time))
    #build and rebuild name_of_devices base on code 503

    name_dict = merge_dic(source_device_dict)

    name_of_devices = OrderedDict(sorted(list(name_dict.items()), key=lambda t: t[1]['503'],reverse=True))
    print(name_of_devices)
    # name_of_devices = sorted(name_dict.keys(), key=str.lower)
    print('Altogether length:\t', len(name_of_devices))
    lst_of_503 = []
    no_503 = []

    print('Converted already:\t', len(lst_of_503))
    print('Amount to be checked:\t', len(no_503))



    run_time = write_excel(connect_time, date_str, name_dict, name_of_devices, starttime)

    print('Total time: ', time.time()-starttime)
    logger.debug("process total time:%s data: %s" % (run_time, data_count))


# 发邮件
def send(from_addr, to_addrs, subject, content):
    # msg = MIMEText(content)
    msg = MIMEMultipart()
    att1 = MIMEText(open('%scount_device_status_output%s.xls' % (LOG_DIR, date_str), 'rb').read(), \
                    'base64', 'utf-8')
    #'%scount_device_status_output%s.xls' % (LOG_DIR, date_str)\
    #'count_device_status_output20140818.xls'
    att1['Content-Type'] = 'application/octet-stream'
    att1['Content-Disposition'] = 'attachment;filename="%scount_device_status_output%s.xls"' % (LOG_DIR, date_str)
    # 'attachment;filename="%scount_device_status_output%s.xls"' % (LOG_DIR, date_str)
    #'attachment;filename="count_device_status_output20140818.xls"'
    msg.attach(att1)
    # from_addr = 'noreply@chinacache.com'
    # from_addr = 'nocalert@chinacache.com'
    msg['Subject'] = subject
    msg['From'] = from_addr
    mail_content = '<html><h1>' + content + '</h1></html>'  # email内容
    msgText = MIMEText(content, 'html', 'utf-8')
    msg.attach(msgText)
    if type(to_addrs) == str:
        msg['To'] = to_addrs
    elif type(to_addrs) == list:
        msg['To'] = ','.join(to_addrs)

    e_s = EmailSender(from_addr, to_addrs, msg)
    r_send = e_s.sendIt()
    if r_send != {}:
        # s = smtplib.SMTP('corp.chinacache.com')
        s = smtplib.SMTP('anonymousrelay.chinacache.com')
        s.ehlo()
        s.starttls()
        s.ehlo()
        # s.login('noreply', 'SnP123!@#')
        s.sendmail(from_addr, to_addrs, msg.as_string())
        s.quit()


def run():
    today = datetime.datetime.today()
    process_date = today - datetime.timedelta(days=1)
    date_str = process_date.strftime('%Y%m%d')  # 待用argparse改正
    process(date_str)
    content = 'Hi,ALL:<br/><br/>此邮件统计的是昨天设备执行刷新任务的状态码，<br/>    0:执行完刷新结果后更新状态时会因为数据集合超过数据库默认的package size而不能正常更新，这部分任务已经执行了刷新;<br/>    503:连接失败;<br/>    204:设备挂起；<br/>   404:FC进程间通信异常；<br/>具体信息请查看附件!'
    send(ads_from, ads_to, '刷新设备状态日报-CBU', content)
    exit()



if __name__ == '__main__':
    # if len(sys.argv) < 2:
    # print 'Wrong argument numbers.'
    #     exit(0)
    if len(sys.argv) > 2:
        if sys.argv[1] == 'help':
            print('python <filename> <8-digit-date>')
            exit(0)
        elif len(sys.argv) > 2:
            date_str = sys.argv[1]
    else:
        today = datetime.datetime.today()
        process_date = today - datetime.timedelta(days=1)
        date_str = process_date.strftime('%Y%m%d')  #待用argparse改正
    process(date_str)
    # get_devices_from_rcms()
    content = 'Hi,ALL:<br/><br/>此邮件统计的是昨天设备执行刷新任务的状态码，<br/>    0:执行完刷新结果后更新状态时会因为数据集合超过数据库默认的package size而不能正常更新，这部分任务已经执行了刷新;<br/>    503:连接失败;<br/>    204:设备挂起；<br/>   404:FC进程间通信异常；<br/>具体信息请查看附件!'
    send(ads_from, ads_to, '刷新设备状态日报-CBU', content)
    exit()
