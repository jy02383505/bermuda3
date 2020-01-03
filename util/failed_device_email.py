#! /usr/bin/env python
# -*- coding: utf-8 -*-

import redis, datetime, time, os, sys, smtplib, logging
from logging.handlers import RotatingFileHandler
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from util.tools import get_active_devices, get_current_date_str, get_email_list_by_type
from core.models import MONITOR_DEVICE_STATUS_EMAIL
from core.config import config
from core.database import db_session
import core.redisfactory as redisfactory
from util.emailSender import EmailSender

LOG_FILENAME = '/Application/bermuda3/logs/failed_device_email.log'
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s")
fh = RotatingFileHandler(LOG_FILENAME, 'a+',500*1024*1024, 10)
fh.setFormatter(formatter)
logger = logging.getLogger('failed_device_email')
logger.addHandler(fh)
logger.setLevel(logging.DEBUG)

REDIS_CLIENT = redisfactory.getMDB(7)
#REDIS_CLIENT = redis.StrictRedis(host='%s' % '172.16.21.205', port=6379, db=7, password= 'bermuda_refresh')
ads_from = 'nocalert@chinacache.com'

#def make_data(max_count, interval):
#    '''
#    max_count 超过该数发邮件
#    interval  检查间隔时间 单位 分钟
#    '''
#    now = datetime.datetime.now()
#    now_h = now.hour
#
#    all_devices = get_active_devices()
#    failed_devices = {}
#    for dev in all_devices:
#        dev_failed_count = 0
#        m_keys = {}
#        all_values = []
#        for x in xrange(interval):
#            _now = now - datetime.timedelta(minutes=x)
#            now_key = "%s_%s" %(now.strftime('%Y-%M-%d-%H'),dev)
#            _now_minute = _now.minute
#            m_keys.setdefault(now_key,[])
#            m_keys[now_key].append(_now_minute)
#        
#        for k, vl in m_keys.items(): 
#            _v = REDIS_CLIENT.hmget(k, vl)
#            all_values.extend(_v)
#        for v in all_values:
#            if v:
#                dev_failed_count += int(v)
#        
#        if dev_failed_count >= max_count:
#            failed_devices[dev] = dev_failed_count    
#
#    return failed_devices

def bak_data():
    '''
    备份数据
    '''
    for _code in MONITOR_DEVICE_STATUS_EMAIL:
        bak_key = '%s_bak'%(_code)
        if REDIS_CLIENT.exists(bak_key):
            REDIS_CLIENT.delete(bak_key)
    
        day_s = get_current_date_str()
        day_key = '%s_%s' %(day_s, _code)
        current_data = REDIS_CLIENT.hgetall(day_key)
        if current_data:
            REDIS_CLIENT.hmset(bak_key, current_data)
         

def filter_data(info):
    '''
    过滤数据
    '''
    hostname = info[0]
    val = info[1]
    if hostname in DEVICES and val >= MAX_COUNT:
        return info


def make_data():
    '''
    比对bak data
    '''
    day_s = get_current_date_str()
    failed_devices = {}
    for _code in MONITOR_DEVICE_STATUS_EMAIL:
        bak_key = '%s_bak'%(_code)
        day_key = '%s_%s' %(day_s, _code)
        if not REDIS_CLIENT.exists(bak_key):
            continue
        bak_data = REDIS_CLIENT.hgetall(bak_key)
        now_data = REDIS_CLIENT.hgetall(day_key)
        for n_h, n_c in list(now_data.items()):
            bak_c = bak_data.get(n_h,0)
            c = int(n_c) - int(bak_c)
            if c > 0:
                failed_devices.setdefault(n_h, 0)
                failed_devices[n_h] += c

    return failed_devices


def make_all_data(day_s=None):
    '''
    no 比对
    '''
    if not day_s:
        day_s = get_current_date_str()
    failed_devices = {}
    for _code in MONITOR_DEVICE_STATUS_EMAIL:
        day_key = '%s_%s' %(day_s, _code)
        if not REDIS_CLIENT.exists(day_key):
            continue
        now_data = REDIS_CLIENT.hgetall(day_key)
        for n_h, n_c in list(now_data.items()):
            failed_devices.setdefault(n_h, 0)
            failed_devices[n_h] += int(n_c)

    return failed_devices


def make_content(failed_devices):
    '''
    生成邮件内容
    '''
    content = 'Hi,ALL:<br/><br/>以下设备失败数过大，请及时处理~<br/>\n' 
    sorted_info = sorted(list(failed_devices.items()),key=lambda x:x[1],reverse=True)
    table = '<table border="1">\n<tr><th>hostname</th><th>failed count</th></tr>\n%s</table>'
    t_body = ''
    for _info in sorted_info:
        _name = _info[0]
        _failed_count = _info[1]
        t_info = '<tr><td>%s</td><td style="text-align:center">%s</td></tr>\n'%(_name, _failed_count)
        t_body += t_info
    all_table = table %(t_body)
    return content + all_table
    

def send_mail(from_addr, to_addrs, subject, content):
    
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

    global DEVICES
    global MAX_COUNT

    hour = datetime.datetime.now().hour
    failed_devices = make_data()
    
    logger.debug('failed_devices %s'%(failed_devices))

    bak_data()

    if hour != 0 and not failed_devices:
        #print hour
        #print 'no failed devices' 
        #os._exit(0)
        return
    #邮件列表配置
    all_info = db_session().email_management.find({'failed_type':'alarm_link_failed_devices'})
    for _info in all_info:
        #print '_info', _info
        DEVICES = _info.get('devices')
        if not DEVICES:
            #print 'c1-----------------'
            continue
        MAX_COUNT = _info.get('threshold')
        if not MAX_COUNT:
            #print 'c2-----------------'
            continue
        ads_to = _info.get('email_address', [])
        if not ads_to:
            #print 'c3-----------------'
            continue
        rate =_info.get('rate')
        if not rate:
            #print 'c4-----------------'
            continue
        can_email_hour = list(range(0, 23+1, int(rate)))
        if hour not in can_email_hour:
            #print 'c5-----------------'
            #print can_email_hour
            continue
        if rate == 24:
            #汇总邮件
            _day_key = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
            all_failed_devices = make_all_data(_day_key)
            _f = list(filter(filter_data, list(all_failed_devices.items())))
        else:
            _f = list(filter(filter_data, list(failed_devices.items())))

       # print 'DEVICES', DEVICES
       # print 'MAX_COUNT', MAX_COUNT
       # print 'rate', rate

        if not _f:
            #print 'c6-----------------'
            continue

        #print '_f', _f

        _content = make_content(dict(_f))

        logger.debug('ads_to %s'%(ads_to))
        logger.debug('_content %s'%(_content))

        send_mail(ads_from, ads_to, '刷新下发设备异常告警', _content) 

    os._exit(0)


if __name__ == '__main__':

    run()

