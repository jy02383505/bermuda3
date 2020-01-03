#! /usr/bin/env python
# -*- coding: utf-8 -*-
import traceback
import imp

__doc__ = '''
统计前一日的刷新回调量

'''

import urllib
import datetime
import logging
import sys
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from datetime import timedelta

imp.reload(sys)
sys.setdefaultencoding("utf8")

from core import  database

import redis

from util.emailSender import EmailSender


conn_db = database.query_db_session()
conn = database.s1_db_session()
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
RCMS_API = 'http://j.hope.chinacache.com:8082/api/device/name/{0}/apps'
#RCMS_DEVICES_LAYER = 'https://rcmsapi.chinacache.com/upperlayer/devices'
RCMS_DEVICES_LAYER = 'https://cms3-apir.chinacache.com/upperlayer/devices'
HOPE_MRTG = 'http://j.hope.chinacache.com:8082/api/device/{0}/mrtgnotes'
DEVICES_LAYER = {}
REDIS_CLIENT = redis.StrictRedis(host='%s' % '10.20.56.91', port=6379, db=15, password= 'bermuda_refresh')
ads_from = 'nocalert@chinacache.com'
ads_to = ['junyu.guo@chinacache.com','yanming.liang@chinacache.com', 'pengfei.hao@chinacache.com','hao.li@chinacache.com']
#ads_to = ['pengfei.hao@chinacache.com']
send_headers = {'X-HOPE-Authn': 'refresh'}



refresh_result={}
data_all=0
data_success=0
def get_refresh_all_num(begintime,endtime):
    countAll=conn_db['url'].find({'created_time':{'$gte':begintime,'$lte':endtime},"status" : "FINISHED"}).count()
    print(countAll)
def get_data_refresh(conn_sql,begintime,endtime):
    global data_all
    global refresh_result
    global data_success
    results=conn_sql.find({'time':{'$gte':begintime,'$lte':endtime}})
    for result in results:
        #print result
        data_all=data_all+1
        if result['result']=="200" or result['result']==200:
            data_success=data_success+1
        devic_dict = refresh_result.setdefault(result['host'],{})
        result_num = devic_dict.setdefault(result['result'],0)+1
        all_num = devic_dict.setdefault('total', 0) + 1
        #print type(result['host'])
        devic_dict[result['result']]=result_num
        devic_dict['total'] = all_num
    #print refresh_result
def write_statistical_data():
    global data_all
    global refresh_result
    global data_success
    print(refresh_result)
    print(data_success)
    #print '--------------------------------'
    today = datetime.datetime.today()
    header_list = ['Date', '刷新回调量', '成功', '失败', '失败率']
    theader = '<th>{0}</th>'.format('</th><th>'.join(header_list))
    trs = []

    tr = [today.strftime('%Y%m%d')]
    tr.append('{0:,}'.format(data_all))
    tr.append('{0:,}'.format(data_success))
    tr.append('{0:,}'.format(data_all-data_success))
    tr.append('{0:.2%}'.format((round((data_all-data_success) /data_all , 4))))
    trs.append('<td>{0}</td>'.format('</td><td>'.join(tr)))
    table = '<table border="1">\n<thead><tr>{0}</tr></thead>\n<tbody>\n<tr>{1}</tr></tbody></table>'.format(theader,'</tr>\n<tr>'.join(trs))
    return table
def get_top10_device(fail):
    global data_all
    global refresh_result
    if fail:
        sort_list=sorted(iter(refresh_result.items()), key=lambda d: d[1].get('514',0), reverse=True)
    else:
        sort_list=sorted(iter(refresh_result.items()), key=lambda d: d[1]['total'], reverse=True)
    top_list=[]
    for i in range(10):
        if i < len(sort_list):
            dev_dict={}
            dev_arr=sort_list[i]
            host = dev_arr[0]
            in_dict=dev_arr[1]

            dev = conn_db.device_app.find_one({"host": host})
            if dev :
                nodename = dev.get("name","None")#["name"]
                dev_type = dev.get("type","None")#["type"]
                ISP = dev.get("ispName","None")#["ispName"]
                firstlayer = dev.get("firstlayer",False)#["firstlayer"]
                url = HOPE_MRTG.format(dev["devCode"])
                # add header
	        #print url
                req = urllib.Request(url, headers=send_headers)
                #print req
                mrtg_info = eval(urllib.request.urlopen(req, timeout=100).read())
                mrtg = ','.join(mrtg_info['data']['mrtgs'])
            else:
                nodename = host
                dev_type = 'none'
                ISP = 'none'
                firstlayer = False
                mrtg = 'none'
            #mrtg = 'hello'
            dev_dict['mrtg']=mrtg

            dev_dict['nodename'] = nodename
            dev_dict['dev_type'] = dev_type
            dev_dict['ISP'] = ISP
            dev_dict['firstlayer'] = firstlayer
            dev_dict.update(in_dict)
            dev_dict.setdefault('200',0)
            #num_501 = dev_dict.setdefault('501',0)
            #num_502 = dev_dict.setdefault('502', 0)
            #num_503 = dev_dict.setdefault('503', 0)
            num_514 = dev_dict.setdefault('514', 0)
            #dev_dict.setdefault('fail',num_501+num_502+num_503 )
            dev_dict.setdefault('fail',num_514)
            top_list.append(dev_dict)
    return top_list

def write_top(fail=False):
    top_list=get_top10_device(fail)
    #theader = '<th>NO.</th><th>hostname</th><th>ISP</th><th>type</th><th>firstLayer</th><th>200</th><th>501</th><th>502</th><th>503</th><th>FAIL</th><th>mrtg</th>'
    theader = '<th>NO.</th><th>hostname</th><th>ISP</th><th>type</th><th>firstLayer</th><th>200</th><th>514</th><th>FAIL</th><th>mrtg</th>'
    trs = []
    mrtg = ""
    for i, device in enumerate(top_list):
        #tr = [str(i + 1), device['nodename'], device['ISP'], device['dev_type'], str(device['firstlayer']),str(device['200']),str(device['501']), str(device['502']), str(device['503']), str(device['fail']),device['mrtg']]#mrtg]  # unicode.encode(mrtg,"utf-8")
        tr = [str(i + 1), device['nodename'], device['ISP'], device['dev_type'], str(device['firstlayer']),str(device['200']),str(device['514']),  str(device['fail']),device['mrtg']]#mrtg]  # unicode.encode(mrtg,"utf-8")
        trs.append('<td>{0}</td>'.format('</td><td>'.join(tr)))

    table = '<table border="1">\n<thead><tr>{0}</tr></thead>\n<tbody>\n<tr>{1}</tr></tbody></table>'.format(theader,'</tr>\n<tr>'.join(trs))
    return table
# 发邮件
def send(from_addr, to_addrs, subject, content):
    msg = MIMEMultipart()
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
        s = smtplib.SMTP('anonymousrelay.chinacache.com')
        try:
            s.ehlo()
            s.starttls()
            s.ehlo()
        except Exception:
            pass
        #print '开始发送邮件---------'
        #print from_addr
        #print to_addrs
        #print msg.as_string()
        s.sendmail(from_addr, to_addrs, msg.as_string())
        s.quit()

def run():

    now = datetime.datetime.now()
    start_str = 'start script on {datetime}'.format(datetime=now)
    logger.info(start_str)
    cur_time = datetime.datetime.combine(now.date(), now.time().replace(second=0, microsecond=0))
    pre_time = cur_time - timedelta(days=1)

    for i in range(10):
        sql='refresh_result%s'%(i+1)
        conn_sql=conn[sql]
        get_data_refresh(conn_sql,pre_time,cur_time)

    content = 'Hi,ALL:<br/><br/>刷新回调每日:<br/><br/>'
    content += write_statistical_data()
    content += '<br/><br/>刷新失败设备TOP 10:<br/>'
    content += write_top(True)

    content += '<br/><br/>刷新设备总量TOP 10:<br/>'
    content += write_top()

    content += '''<br/><br/>刷新回调结果<br/><br/>200:表示成功的状态<br/><br/>514:表示失败的状态'''
    send(ads_from, ads_to, '刷新回调日报', content)
    logger.debug("send email end")
    os._exit(0)


if __name__ == '__main__':
    run()


