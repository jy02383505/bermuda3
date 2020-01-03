#! /usr/bin/env python
# -*- coding: utf-8 -*-
import traceback
import imp

__doc__ = '''
统计前一日的刷新任务，收到的任务量，下发的任务量及503的分析

'''
import hashlib
import threading
import urllib
import datetime
import time
import logging
import sys
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from .rep_refresh_count import get_refresh_num

imp.reload(sys)
sys.setdefaultencoding("utf8")
# try:
#     from pymongo import ReplicaSetConnection as MongoClient
# except:
#     from pymongo import MongoClient
from core import database
import xlwt
from collections import Counter, OrderedDict, defaultdict
import redis
from util.emailSender import EmailSender

# conn = MongoClient('%s:27017,%s:27017,%s:27017' % ('172.16.12.136', '172.16.12.135', '172.16.12.134'),
#                    replicaSet='bermuda_db')['bermuda']
#uri = "mongodb://bermuda:bermuda_refresh@172.16.12.135:27018/bermuda"
# uri = 'mongodb://bermuda:bermuda_refresh@%s:27017,%s:27017,%s:27017/bermuda?replicaSet=bermuda_db' % (
#     '172.16.12.136', '172.16.12.135', '172.16.12.134')
# conn = MongoClient(uri)['bermuda']

conn = database.query_db_session()
# STATUS_LIST = ['0', '404', '408', '503', 'a_501', 'a_502', 'a_503', 'a_0', 'r_501', 'r_502', 'r_503', 'r_0']
STATUS_LIST = ['0', '404', '408', '503', '501', '502']
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
# http://j.hope.chinacache.com:8082/api/device/name/{0}/apps
#RCMS_API = 'http://rcmsapi.chinacache.com:36000/device/name/{0}/apps'
RCMS_API = 'http://j.hope.chinacache.com:8082/api/device/name/{0}/apps'
#RCMS_DEVICES_LAYER = 'https://rcmsapi.chinacache.com/upperlayer/devices'
RCMS_DEVICES_LAYER = 'https://cms3-apir.chinacache.com/upperlayer/devices'
#RCMS_MRTG = 'http://rcmsapi.chinacache.com:36000/device/{0}/mrtgnotes'
HOPE_MRTG = 'http://j.hope.chinacache.com:8082/api/device/{0}/mrtgnotes'
DEVICES_LAYER = {}
REDIS_CLIENT = redis.StrictRedis(
    host='%s' % '10.20.56.91', port=6379, db=15, password='bermuda_refresh')
# mail address
# ads_from = 'noreply@chinacache.com'
ads_from = 'nocalert@chinacache.com'

# ads_to = ['huan.ma@chinacache.com', 'hongan.zhang@chinacache.com', 'wangjian@chinacache.com',
#           'libo@chinacache.com', 'bowen.xing@chinacache.com', 'yang.liu@chinacache.com',
#           'CPRD-HPCC-OM@chinacache.com', 'chunyang.wang@chinacache.com', 'rong.chen@chinacache.com', 'BRE-OPS-WD@chinacache.com',
#           'BRE-MSO@chinacache.com', 'pre-ops-network@chinacache.com', 'wizer.li@chinacache.com', 'gen.li@chinacache.com',
#           'robbin.liu@chinacache.com', 'junyu.guo@chinacache.com', 'longjun.zhao@chinacache.com', 'bingli.li@chinacache.com',
#           'bin.wu@chinacache.com', 'haiyue.liu@chinacache.com', 'pengfei.hao@chinacache.com', 'yanming.liang@chinacache.com',
#           'zhida.piao@chinacache.com', 'feng.qiu@chinacache.com'
#           ]
ads_to = ['huan.ma@chinacache.com', 'CPRD-HPCC-OM@chinacache.com', 'chunyang.wang@chinacache.com', 'rong.chen@chinacache.com', 'BRE-OPS-WD@chinacache.com',
          'BRE-MSO@chinacache.com', 'pre-ops-network@chinacache.com','robbin.liu@chinacache.com', 'haiyue.liu@chinacache.com', 'pengfei.hao@chinacache.com', 'yanming.liang@chinacache.com',
          'zhida.piao@chinacache.com', 'feng.qiu@chinacache.com'
          ]

# ads_to = ['yanming.liang@chinacache.com']

send_headers = {'X-HOPE-Authn': 'refresh'}
#req = urllib.request.Request(url, headers=send_headers)


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
            status = str(doc['devices'][device].get('status', 'SUSPEND'))
            if status != 'OPEN':
                continue
            if device not in source_device_dict:  # here
                source_device_dict[str(device)] = {}
                # new_dev = str(device)

            code = str(doc['devices'][device]['code'])
            a_code = str(doc['devices'][device].get('a_code', 0))
            r_code = str(doc['devices'][device].get('r_code', 0))
            firstLayer = doc['devices'][device].get('firstLayer', 'false')

            device = str(device)

            if device not in DEVICES_LAYER:
                DEVICES_LAYER[device] = firstLayer

            if h not in list(source_device_dict[device].keys()):
                code_dic = defaultdict(
                    int)  # 增加默认值 'CNC-BZ-3-3u1mv p /usr/local/bin': defaultdict(<type 'int'>, {'0': 0, '404': 0, '204': 0, '503': 0}
                tmp_dic = [k for k in code_dic if k not in STATUS_LIST]
                if tmp_dic:
                    STATUS_LIST.extend(tmp_dic)
                for c in STATUS_LIST:
                    code_dic[c] += 0
                source_device_dict[device][h] = code_dic
            if code in ['503']:
                source_device_dict[device][h]['a_%s' % a_code] += 1
                source_device_dict[device][h]['r_%s' % r_code] += 1

            source_device_dict[device][h][code] += 1
            num += 1

    e_hour_end = time.time()
    print(h, e_hour_end - e_hour_time, num)
    # print source_device_dict
    logger.debug("process %s - %s time:%s ,count : %s" %
                 (leftend, rightend, e_hour_end - e_hour_time, num))
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
        if not tag_dic[
                dev_name]:  # 增加默认值'CNC-BZ-3-3u1': defaultdict(<type 'int'>, {'0': 0, '404': 0, '204': 0, '503': 0}
            code_dic = defaultdict(int)
            for c in STATUS_LIST:
                code_dic[c] += 0
            tag_dic[dev_name] = code_dic
    # print tag_dic
    return tag_dic


def write_excel(connect_time, date_str, starttime, data_list):
    # 创建excel
    '''
    data_list = [{'200': 1, 'hostname': 'CNC-TI-9-3SI', 'a_0': 0, 'r_0': 0, 'ISP': 'CNC', 'a_501': 0, 'a_502': 0, 'a_503': 0, '0': 0, '404': 0, 'r_503': 0, 'r_502': 0, 'r_501': 0, 'total': 5, 'type': 'FC', '503': 0, '408': 0},
    {'200': 1, 'hostname': 'CNC-TI-9-3SK', 'a_0': 0, 'r_0': 0, 'ISP': 'CNC', 'a_501': 0, 'a_502': 0, 'a_503': 0, '0': 0, '404': 0, 'r_503': 0, 'r_502': 0, 'r_501': 0, 'total': 5, 'type': 'FC', '503': 0, '408': 0}]
    name_dict, name_of_devices, starttime, devices_type
    '''
    wbk = xlwt.Workbook()
    # styleBlueBkg = xlwt.easyxf('pattern: pattern solid, fore_colour
    # ocean_blue; font: bold on;'); # 80% like
    style_red = xlwt.easyxf('font: color-index red, bold on')
    style_italic = xlwt.easyxf('font: color-index red, italic on')
    sheet = wbk.add_sheet('sheet 1')
    sheet.write(0, 0, 'device \ ISP, status')
    sheet.write(0, 1, 'ISP')
    sheet.write(0, 2, 'Type')
    sheet.write(0, 3, 'FirstLayer')
    EX_STATUS_LIST = ['0', '404', '408', '501', '502', '503', '200']
    sheet.write(0, len(EX_STATUS_LIST) + 4, 'FAIL')
    sheet.write(0, len(EX_STATUS_LIST) + 5, 'TOTAL')
    sheet.write(0, len(EX_STATUS_LIST) + 6, 'PER')
    for j, v in enumerate(EX_STATUS_LIST):
        if v in ['501', '502', '503']:
            sheet.write(0, j + 4, v, style_red)
        else:
            sheet.write(0, j + 4, v)

    # for i, device in enumerate(name_of_devices):
    for i, device in enumerate(data_list):
        sheet.write(i + 1, 0, device['hostname'])
        sheet.write(i + 1, 1, device['ISP'])
        sheet.write(i + 1, 2, device['type'])
        sheet.write(i + 1, 3, device['firstLayer'])
        # total = 0
        for jj in range(0, len(EX_STATUS_LIST)):
            # if EX_STATUS_LIST[jj] in ['503']:
            # #     num = device[EX_STATUS_LIST[jj]] + device['r_0']
            # # else:
            num = device[EX_STATUS_LIST[jj]]

            if EX_STATUS_LIST[jj] not in ['501', '502', '503']:
                # total += num
                sheet.write(i + 1, jj + 4, num)
            else:
                sheet.write(i + 1, jj + 4, num, style_italic)
        total = int(device['total'] + device['200'])
        try:
            per = '{0:.2%}'.format(round(device['total'] / float(total), 4))
        except:
            per = '{0:.2%}'.format(0)
        sheet.write(i + 1, len(EX_STATUS_LIST) + 4, device['total'])
        sheet.write(i + 1, len(EX_STATUS_LIST) + 5, total)
        sheet.write(i + 1, len(EX_STATUS_LIST) + 6, per)

    # total_dic['TOTAL']['num'] = len(devices_type)
    wbk.save('%scount_device_status_output%s.xls' % (LOG_DIR, date_str))
    endtime = time.time()
    run_time = endtime - starttime
    logger.debug("process xls time:%s " % (endtime - connect_time))
    print('Total time: ', run_time)
    return run_time


def get_device_type(devices):
    devices_type = {}
    for dev in devices:
        try:
            dd = conn["device_app"].find_one({"name": dev})
            devices_type[dev] = dd["type"]
        except Exception:
            print(e)
            logger.error(e)
            # devices_type[dev] = "unknown"
            # print dev
            get_url = RCMS_API.format(dev)
            # add header
            try:
                req = urllib.Request(get_url, headers=send_headers)
                got_list = eval(urllib.request.urlopen(req, timeout=100).read())

                got_list = got_list.get('data')
                devices_type[dev] = [dic['appName']
                                     for dic in got_list if dic['appName'] in ['FC', 'HPCC']][0]
            except Exception:
                logger.error(traceback.format_exc())
                devices_type[dev] = 'unknown'
    return devices_type


def get_firstLayerDevices():
    try:
        got_list = eval(urllib.request.urlopen(RCMS_DEVICES_LAYER, timeout=100).read())
        dev_info = {}
        FIRSTLAYER_DEVICES = [str(dev['devName'])
                              for dev in got_list if dev['devStatus'] == "OPEN"]
        return FIRSTLAYER_DEVICES
    except Exception:
        logger.debug('get_firstLayerDevices error:%s' %
                     traceback.format_exc())
        return []


def insert_db(name_of_devices, devices_type, conn, date, FIRSTLAYER_DEVICES):
    # {'CNC-BZ-3-3u4': {'200': 2, '503': 7}}
    # print name_of_devices
    stat_dic = {}
    stat_dic['create_time'] = datetime.datetime.today()
    stat_dic['date'] = date
    data_list = []
    stat_dic['HPCC'] = {}
    stat_dic['FC'] = {}
    stat_dic['unknown'] = {}
    for dev in name_of_devices:
        devs_dic = {}
        total = 0
        devs_dic['hostname'] = dev
        devs_dic['ISP'] = dev.split('-')[0]
        devs_dic['firstLayer'] = True if dev in FIRSTLAYER_DEVICES else False
        type = devices_type[dev]
        if 'num' not in stat_dic[type]:
            stat_dic[type]['num'] = 0
        stat_dic[type]['num'] += 1
        devs_dic['type'] = type
        for code in STATUS_LIST + ['200']:
            if code not in name_of_devices[dev]:
                # print name_of_devices[dev], dev
                devs_dic[code] = 0
            else:
                devs_dic[code] = int(name_of_devices[dev][code])
            if code in ['0', '404', '408', '503', '200', '501', '502']:
                if code not in ['200']:
                    total += devs_dic[code]
                if code not in stat_dic[type]:
                    stat_dic[type][code] = 0
                stat_dic[type][code] += devs_dic[code]
        devs_dic['total'] = total
        data_list.append(devs_dic)
    stat_dic['data'] = data_list
    try:
        conn.insert(stat_dic)
    except Exception:
        logger.error(traceback.format_exc())
        logger.error(stat_dic)
        print(ex)

    return stat_dic


def start_thread(connect, date_day, date_month, date_year, devices_type, name_dict, rcmstime_time, real_date):
    print('start connect mongodb')
    thread_list = []
    for h in range(24):
        # if h < 23:
        # continue
        # 先创建线程对象
        thread_name = "Thread #%s" % (h)
        thread_list.append(threading.Thread(target=get_data, name=thread_name,
                                            args=(connect, date_day, date_month, date_year, h, real_date)))
        # get_data(connect,date_day, date_month, date_year, h, real_date)
        # 启动所有线程
    for thread in thread_list:
        thread.start()

    # 主线程中等待所有子线程退出
    for thread in thread_list:
        thread.join()
        logger.debug("name:{0},{1}".format(thread.getName(), thread.isAlive()))
    print('end')
    connect_time = time.time()
    logger.debug("process database take time:%s " %
                 (connect_time - rcmstime_time))
    # build and rebuild name_of_devices base on code 503
    name_dict = merge_dic(source_device_dict)
    devices_type = get_device_type(list(name_dict.keys()))
    name_of_devices = OrderedDict(
        sorted(list(name_dict.items()), key=lambda t: (t[1]['501'] + t[1]['502'] + t[1]['503']), reverse=True))
    # print name_of_devices
    # name_of_devices = sorted(name_dict.keys(), key=str.lower)
    print('Altogether length:\t', len(name_of_devices))
    return connect_time, devices_type, name_dict, name_of_devices


def get_date(date_str):
    date_year = int(date_str[:4])
    date_month = int(date_str[4:6])
    date_day = int(date_str[6:])
    real_date = datetime.date(date_year, date_month, date_day)
    # leftend = datetime.combine(real_date,time.min)
    # rightend = datetime.combine(real_date,time.max)
    date = datetime.datetime.strptime("%s-%s-%s 00:00:00" % (date_year, date_month, date_day),
                                      "%Y-%m-%d %H:%M:%S")
    end_date = date + datetime.timedelta(days=1)
    return date, date_day, date_month, date_year, end_date, real_date


def process(date_str):
    starttime = time.time()
    print(starttime)
    logger.debug('start:%s' % starttime)
    # 读取BU所属设备
    # get_devices_from_rcms()
    rcmstime_time = time.time()
    # print 'Total devices number:\t', len(source_device_dict)
    # logger.debug('Total devices number:%s,take time:%s' % (len(source_device_dict), rcmstime_time - starttime))
    # 开始读取服务器数据
    try:
        connect = conn['device']
    except Exception:
        logger.error(traceback.format_exc())
        return
    name_dict = {}  # 记录新设备名字
    devices_type = {}
    print(connect)

    date, date_day, date_month, date_year, end_date, real_date = get_date(
        date_str)
    connect_day = conn['devices_status_day']
    get_dat = None
    get_dat = connect_day.find_one({'date': {'$gte': date, '$lt': end_date}})
    if not get_dat:
        # connect_time, devices_type, name_dict, name_of_devices = start_thread(connect, date_day, date_month, date_year,
        #                                                                   devices_type, name_dict, rcmstime_time,
        # real_date)
        name_dict = get_redis_data(date_str)
        devices_type = get_device_type(list(name_dict.keys()))
        FIRSTLAYER_DEVICES = get_firstLayerDevices()
        name_of_devices = OrderedDict(
            sorted(list(name_dict.items()), key=lambda t: int(t[1]['501']) + int(t[1]['502']) + int(t[1]['503']),
                   reverse=True))
        get_dat = insert_db(name_of_devices, devices_type,
                            connect_day, date, FIRSTLAYER_DEVICES)
        data_list = get_dat['data']

    else:
        data_list = get_dat['data']
    connect_time = time.time()

    run_time = write_excel(connect_time, date_str, starttime, data_list)
    # run_time,total_dic = write_excel(connect_time, date_str, name_dict, name_of_devices, starttime, devices_type)

    print('Total time: ', time.time() - starttime)
    logger.debug("process total time:%s" % (run_time))
    return get_dat


def get_redis_data(date_str):
    try:
        # connect = conn['ref_err_day']
        DAY_KEYS = '%s*' % date_str
        result_from_redis = REDIS_CLIENT.keys(DAY_KEYS)
    except Exception:
        logger.error(traceback.format_exc())
    name_dict = {}  # 记录新设备名字
    # {'CNC-BZ-3-3u4': {'200': 2, '503': 7}}
    for devs_key in result_from_redis:
        dev_dic = REDIS_CLIENT.hgetall(devs_key)
        code_dic = defaultdict(int)
        code_dic.update(dev_dic)
        name_dict['%s' % devs_key.split('_')[1]] = code_dic
    # delete 3 days ago data
    try:
        today = datetime.datetime.today()
        process_date = today - datetime.timedelta(days=3)
        del_date_str = process_date.strftime('%Y%m%d')
        key_from_redis = REDIS_CLIENT.keys(del_date_str)
        for d_key in key_from_redis:
            REDIS_CLIENT.delete('%s' % d_key)
    except Exception:
        logger.error(traceback.format_exc())

    return name_dict


# 发邮件
def send(from_addr, to_addrs, subject, content, date_str):
    # msg = MIMEText(content)
    msg = MIMEMultipart()
    att1 = MIMEText(open('%scount_device_status_output%s.xls' % (LOG_DIR, date_str), 'rb').read(),
                    'base64', 'utf-8')
    att1['Content-Type'] = 'application/octet-stream'
    att1[
        'Content-Disposition'] = 'attachment;filename="%scount_device_status_output%s.xls"' % (LOG_DIR, date_str)
    msg.attach(att1)
    # from_addr = 'nocalert@chinacache.com'
    msg['Subject'] = subject
    msg['From'] = from_addr
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
        try:
            s.ehlo()
            s.starttls()
            s.ehlo()
        except Exception:
            pass
        # s.login('noreply', 'SnP123!@#')
        s.sendmail(from_addr, to_addrs, msg.as_string())
        s.quit()


def run():
    today = datetime.datetime.today()
    process_date = today - datetime.timedelta(days=1)
    date_str = process_date.strftime('%Y%m%d')  # 待用argparse改
    # :执行完刷新结果后更新状态时会因为数据集合超过数据库默认的package size而不能正常更新，这部分任务已经执行了刷新;<br/>    503:连接失败;<br/>    204:设备挂起；<br/>   404:FC进程间通信异常；<br/>具体信息请查看附件!'
    process(date_str)
    content = 'Hi,ALL:<br/><br/>昨天设备执行刷新任务的状态码，<br/>    0:执行完刷新结果后更新状态时会因为数据集合超过数据库默认的package size而不能正常更新，这部分任务已经执行了刷新;<br/>    503:连接失败;<br/>    204:设备挂起；<br/>   404:FC进程间通信异常；<br/>具体信息请查看附件!'
    send(ads_from, ads_to, '刷新设备状态日报-CBU', content, date_str)
    exit()


def write_statistical():
    try:
        connect = conn['statistical']
    except Exception:
        logger.error(traceback.format_exc())
        return

    today = datetime.datetime.today()
    process_date = today - datetime.timedelta(days=1)
    date_str = process_date.strftime('%Y-%m-%d')

    # theader = '<th>%s</th>'.format('</th><th>'.join(['Date','404','408','503','0']))
    header_list = ['Date', '刷新量', '目录数', '成功', '失败', '失败率']
   # try:
   #     new_datas = conn.fzt_sta.find({'datetime': {"$gt": today - datetime.timedelta(days=2), "$lt": today}})
   #     new_count = []
   #     for index, type in enumerate(new_datas):
   #         new_count.append(type['sum_not_important'])
   #         header_list.append('算法%s' % (index + 1))
   # except Exception, ex:
   #     print ex
   #     data_of_503 = 0

    theader = '<th>{0}</th>'.format('</th><th>'.join(header_list))
    trs = []
   # pre_time = datetime.datetime.combine(process_date.date(), datetime.time())
   # cur_time = pre_time + datetime.timedelta(days=1)
   # find_url_dic = {"finish_time": {"$gte": pre_time, "$lt": cur_time}, "old_status": "FAILED"}
   # old_failed_num = conn.url.find(find_url_dic, no_cursor_timeout=True).count()
    for record in connect.find({'date': date_str}):
        tr = [record["date"]]
        tr.append('{0:,}'.format(int(record["total_refresh"])))
        tr.append('{0:,}'.format(int(record["total_dir"])))
        tr.append('{0:,}'.format(
            int(record["total_refresh"]) - int(record["failed_num"])))
        tr.append('{0:,}'.format(int(record["failed_num"])))
        tr.append('{0:.2%}'.format(
            (round(record["failed_num"] / float(record["total_refresh"]), 4))))
    #    tr.append('{0:.2%}'.format((round(old_failed_num / float(record["total_refresh"]), 4))))
    #    for r_503_data in new_count:
    #        tr.append(
    #            '{0:.2%}'.format((round(abs(record["failed_num"] - r_503_data) / float(record["total_refresh"]), 4))))

        trs.append('<td>{0}</td>'.format('</td><td>'.join(tr)))
    table = '<table border="1">\n<thead><tr>{0}</tr></thead>\n<tbody>\n<tr>{1}</tr></tbody></table>'.format(theader,
                                                                                                            '</tr>\n<tr>'.join(
                                                                                                                trs))
    return table


def write_top_for_count():
    try:
        connect = conn['statistical']
    except Exception:
        logger.error(traceback.format_exc())
        return

    today = datetime.datetime.today()
    process_date = today - datetime.timedelta(days=1)
    date_str = process_date.strftime('%Y-%m-%d')
    data_list = []

    # theader = '<th>%s</th>'.format('</th><th>'.join(['Date','404','408','503','0']))
    header_list = ['NO.', '用户名', '数量']

    theader = '<th>{0}</th>'.format('</th><th>'.join(header_list))

    table = ""
    data = connect.find_one({'date': date_str})
    for tab in ["username_count_list", "username_fail_count_list"]:
        if tab in list(data.keys()):
            data_list = data[tab][:10]
        else:
            continue
        i = 0
        trs = []
        for key, value in data_list:
            tr = [str(i + 1)]
            tr.append(key)
            tr.append('{0:,}'.format(int(value)))
            trs.append('<td>{0}</td>'.format('</td><td>'.join(tr)))
            i += 1
        if tab == "username_count_list":
            table += '<table width="33%" border="1" align=left>\n<thead><tr>{0}</tr></thead>\n<tbody>\n<tr>{1}</tr></tbody></table>'.format(
                theader,
                '</tr>\n<tr>'.join(
                    trs))
        else:
            table += '<table width="33%" border="1" align=center>\n<thead><tr>{0}</tr></thead>\n<tbody>\n<tr>{1}</tr></tbody></table>'.format(
                theader,
                '</tr>\n<tr>'.join(
                    trs))
    return table


def write_url_code_per(process_date):
    try:
        connect = conn['ref_err']
    except Exception:
        logger.error(traceback.format_exc())
        return
    pre_time = datetime.datetime.combine(process_date.date(), datetime.time())
    cur_time = pre_time + datetime.timedelta(days=1)
    print(pre_time, cur_time)
    find_url_dic = {"datetime": {"$gte": pre_time, "$lt": cur_time},
                    "devices.code": {"$in": ['503', '502', '501', '408', '404']}}
    field_dic = {"username": 1, "_id": 1,
                 "devices.code": 1, "uid": 1, "failed.code": 1}

    try:
        collection_url = conn['ref_err']
    except Exception:
        logger.error(traceback.format_exc(ex))

    ref_errs = collection_url.find(
        find_url_dic, field_dic, no_cursor_timeout=True)
    fail_count = ref_errs.count()
    result = {}
    for errrs in ref_errs:
        if errrs.get("devices", None):
            ll = tuple(set([int(dev['code']) for dev in errrs[
                       "devices"] if dev['code'] not in ['0', '200', '204']]))
            if ll not in result:
                result[ll] = 1
            else:
                result[ll] += 1
        elif errrs.get("failed", None):
            ll = tuple(set([int(dev['code']) for dev in errrs[
                       "failed"] if dev['code'] not in ['0', '200', '204']]))
            if ll not in result:
                result[ll] = 1
            else:
                result[ll] += 1
    print(result, fail_count)
    theader = '<th>{0}</th>'.format('</th><th>'.join(['状态码', '数量', '占比']))
    trs = []
    for key, value in list(result.items()):
        tr = []
        tr.append('{0}'.format(key, value, ))
        tr.append('{0:,}'.format(value))
        tr.append('{0:.2%}'.format((round(value / float(fail_count), 4))))
        #
        trs.append('<td>{0}</td>'.format('</td><td>'.join(tr)))
    table = '<table border="1">\n<thead><tr>{0}</tr></thead>\n<tbody>\n<tr>{1}</tr></tbody></table>'.format(theader,
                                                                                                            '</tr>\n<tr>'.join(
                                                                                                                trs))
    return table


def write_code(total_dic):
    today = datetime.datetime.today()
    process_date = today - datetime.timedelta(days=1)
    date_str = process_date.strftime('%Y-%m-%d')
    theader = '<th>设备类型</th><th>设备数</th>' + '<th colspan="2">{0}</th>'.format(
        '</th><th colspan="2">'.join(['503(%)', '404(%)', '408(%)', '0(%)', '200(%)'])) + '<th>总数</th>'

    trs = []
    tre = []

    t_dic = {}
    device_num = 0
    type_list = ['HPCC', 'FC', 'unknown']
    title_list = ["503", "404", "408", "0", "200"]
    ttotal = 0
    for type in type_list:
        if total_dic[type]:
            for ti in title_list:
                if ti not in t_dic:
                    t_dic[ti] = 0
                if type not in t_dic:
                    t_dic[type] = 0
                t_dic[ti] += int(total_dic[type][ti])
                t_dic[type] += int(total_dic[type][ti])
                ttotal += int(total_dic[type][ti])
            device_num += int(total_dic[type]['num'])
            tr = ['<td>%s</td><td>%s</td>' %
                  (type, int(total_dic[type]['num']))]
            for tt in title_list:
                try:
                    per_c = round(
                        int(total_dic[type][tt]) / float(t_dic[type]), 4)
                except:
                    per_c = 0
                tr.append(
                    '<td>{0:,}</td><td style="background-color:#999966";>{1:.2%}</td>'.format(int(total_dic[type][tt]),
                                                                                              per_c))

            tr.append('<td>{0:,}</td>'.format(t_dic[type]))
            trs.append(''.join(tr))
    tre = ['{0:,}'.format(t_dic[tt]) for tt in title_list]
    trs.append('<td>TOTAL</td><td>{0:,}</td>'.format(device_num) + '<td colspan="2">{0}</td>'.format(
        '</td><td colspan="2">'.join(tre)) + '<td>{0:,}</td>'.format(ttotal))
    table = '<table border="1">\n<thead><tr>{0}</tr></thead>\n<tbody>\n<tr>{1}</tr></tbody></table>'.format(theader,
                                                                                                            '</tr>\n<tr>'.join(
                                                                                                                trs))
    return table


def write_top(data):
    theader = '<th>NO.</th><th>hostname</th><th>ISP</th><th>type</th><th>firstLayer</th><th>501</th><th>502</th><th>503</th><th>FAIL</th><th>mrtg</th>'
    trs = []
    mrtg = ""
    for i, device in enumerate(data['data'][:10]):
        try:
            dev = conn.device_app.find_one({"name": device['hostname']})
            url = HOPE_MRTG.format(dev["devCode"])
            # add header
            req = urllib.Request(url, headers=send_headers)
            mrtg_info = eval(urllib.request.urlopen(req, timeout=100).read())
            mrtg = ','.join(mrtg_info['data']['mrtgs'])
            # mrtg = mrtg.decode("utf-8")
        except Exception:
            logger.error(traceback.format_exc())
        tr = [str(i + 1), device['hostname'], device['ISP'], device['type'], str(device['firstLayer']),
              str(device['501']), str(device['502']), str(
                  device['503']), str(device['total']),
              mrtg]  # unicode.encode(mrtg,"utf-8")
        trs.append('<td>{0}</td>'.format('</td><td>'.join(tr)))

    table = '<table border="1">\n<thead><tr>{0}</tr></thead>\n<tbody>\n<tr>{1}</tr></tbody></table>'.format(theader,
                                                                                                            '</tr>\n<tr>'.join(
                                                                                                                trs))
    return table


def write_503_per(total_dic):
    theader = '<th>设备类型</th><th>503总数</th><th>设备数</th>' + '<th colspan="2">{0}</th>'.format(
        '</th><th colspan="2">'.join(['>10000(%)', '>1000(%)', '>100(%)', '10(%)', '>1(%)']))
    type_list = ['HPCC', 'FC', 'unknown']
    num_list = [10000, 1000, 100, 10, 1]
    code = '503'
    trs = []
    devs_num = 0
    r_dic = {}
    for ty in type_list:
        if total_dic[ty]:
            devs_num += total_dic[ty]['num']
            for nn in num_list:
                if ty not in r_dic:
                    r_dic[ty] = {}
                r_dic[ty][nn] = 0

    for item in total_dic['data']:
        num = int(item["503"])
        dev_type = item['type']
        if num >= 10000:
            r_dic[dev_type][10000] += 1
        elif num >= 1000:
            r_dic[dev_type][1000] += 1
        elif num >= 100:
            r_dic[dev_type][100] += 1
        elif num >= 10:
            r_dic[dev_type][10] += 1
        elif num >= 1:
            r_dic[dev_type][1] += 1
    nn = 1
    for type in type_list:
        if total_dic[type]:
            total = total_dic[type][code]
            tr = ['<td>%s</td>' % type]
            tr.append('<td>%s</td>' % total)
            tr.append('<td>{0:,}</td>'.format(total_dic[type]['num']))

            for n in num_list:
                cur_num = r_dic[type][n]
                try:
                    per = round(int(cur_num) /
                                float(total_dic[type]['num']), 4)
                except:
                    per = 0
                tr.append(
                    '<td>{0:,}</td><td style="background-color:#FFA500";>{1:.2%}</td>'.format(cur_num, per))
            # else:
            #         tr.append('<td>{0:,}</td><td style="background-color:#FFFF00";>{1:.2%}</td>'.format(cur_num,per))
            # nn+=1
            trs.append(''.join(tr))

    table = '<table border="1">\n<thead><tr>{0}</tr></thead>\n<tbody>\n<tr>{1}</tr></tbody></table>'.format(theader,
                                                                                                            '</tr>\n<tr>'.join(
                                                                                                                trs))
    return table


def script_run():

    today = datetime.datetime.today()
    process_date = today - datetime.timedelta(days=1)
    date_str = process_date.strftime('%Y%m%d')  # 待用argparse改正
    try:
        old_date = today - datetime.timedelta(days=2)
        old_date_str = old_date.strftime('%Y%m%d')
        old_file = '{0}/{1}.txt'.format(LOG_DIR, old_date_str)
        os.remove(old_file)
    except Exception:
        logger.debug(ex)
    log_file = '{0}/{1}.txt'.format(LOG_DIR, date_str)

    if os.path.isfile(log_file):
        os._exit(0)

    # dic = {'CNC-YZ-2-3g5': {'200': 2, '503': 7},'CNC-YT-2-3H1': {'200': 2, '503': 7}}
    # get_device_type(dic.keys())
    total_dic = process(date_str)
    # # get_devices_from_rcms()
    # content = 'Hi,ALL:<br/><br/>刷新系统每日接收任务统计表:<br/><br/>'
    content = 'Hi,ALL:<br/><br/>刷新系统每日:<br/><br/>'
    # content = '由于采用新的统计方法，数据会比原来的更准确!<br/><br/>'
    content += write_statistical()
    # content += '<br/>[算法1]与[算法2]为按新算法(运营商&&大区)统计的失败率:<br/>'
    # content += '算法1:<br/>'
    # content += '&nbsp;&nbsp;isp : ["CHN", "CNC", "UNI"]<br/>'
    # content += '&nbsp;&nbsp;region : ["BEIJING", "SHANGHAI", "GUANGZHOU"]<br/>'
    # content += '算法2:<br/>'
    # content += '&nbsp;&nbsp;isp: ["CHN", "CNC", "UNI"]<br/>'
    # content += '&nbsp;&nbsp;region: ["BEIJING", "SHANGHAI", "GUANGZHOU","WUHAN","XIAN","SHENYANG","NANJING","CHENGDU"]<br/>'
    content += '<br/><br/>失败设备TOP 10:<br/>'
    content += write_top(total_dic)
    content += '<br/><br/>客户刷新量及刷新失败TOP 10:<br/>'
    content += write_top_for_count()
    # content += '<br/><br/>客户刷新失败TOP 10:<br/>'
    # content += write_top_for_count(True)
    content += '<br/><br/>'
    content += '<br/><br/>刷新系统每日下发任务统计表(数量/占比):<br/>'
    content += write_code(total_dic)
    content += '<br/><br/>刷新系统503分析(设备数及503分布占比):'
    content += write_503_per(total_dic)
    content += '<br/><br/>刷新回调占比分析:'
    content += get_refresh_num()
    content += '<br/><br/>从任务维度统计，导致任务失败的状态码及占比:'
    content += '<br/><br/>注：一个任务可能同时有多个设备失败，返回失败状态码'
    content += write_url_code_per(process_date)
    content += '''<br/><br/> unknown:表示从RCMS中未获取到此设备的类型
                                 0:执行完刷新,FC返回结果异常,解析失败,没有正常更新状态;<br/>
                                 404:FC进程间通信异常；<br/>
                                 408:FC进程异常；<br/>
                                 501: the refreshd response too slow  <br/>
                                 502: The network is OK,But the refreshd does not work <br/>
                                 503 can not reach the server <br/>
                                 200 成功数量 <br/>
                                 TOTAL 发送任务总数 <br/>
                                 FAIL 失败数量 <br/>
                                 PER 失败率 <br/>
                                 具体信息请查看附件!'''

    send(ads_from, ads_to, '刷新任务统计及设备状态日报', content, date_str)
    logger.debug("send email end")
    os.mknod(log_file)
    os._exit(0)


