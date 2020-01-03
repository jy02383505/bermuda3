#! /usr/bin/env python
# -*- coding: utf-8 -*-

import urllib
import datetime
import logging
import sys

#import pymongo
#import xlwt
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from util.emailSender import EmailSender

DEFAULT_HOST = '172.16.12.134'
BAK_HOST = '172.16.12.135'

DEFAULT_PORT = 27017
DEFAULT_DB = 'bermuda'
DEFAULT_COLL = 'device'
STATUS_LIST = ['0', '204', '404', '503']
CBU_LIST = ['GlobalCDN', 'CBU', 'RDB', '文件分发服务', \
            '页面加速服务', '文件分发下载服务']
#URL_HEAD = 'http://rcmsapi.chinacache.com:36000/devices/department/%s'
URL_HEAD = 'http://rcmsapi-private.chinacache.net:36000/devices/department/%s'
# 定义null
global null
null = ''
LOG_DIR = '/Application/bermuda3/logs/'
LOG_FILENAME = '/Application/bermuda3/logs/count_device.log'
logging.basicConfig(filename=LOG_FILENAME,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger('count_deivce')
logger.setLevel(logging.DEBUG)

#mail address
ads_from = 'noreply@chinacache.com'
ads_to = ['hongan.zhang@chinacache.com','haixin.yuan@chinacache.com','shanliang.yu@chinacache.com','jinyan.chi@chinacache.com','xuefeng.hou@chinacache.com','jian.liu@chinacache.com','shi.hou@chinacache.com','huan.ma@chinacache.com','hongtao.yang@chinacache.com']

# 发邮件
def send(from_addr, to_addrs, subject, content):
    msg = MIMEMultipart()
    # from_addr = 'noreply@chinacache.com'
    msg['Subject'] = subject
    msg['From'] = from_addr
    mail_content = '<html><h1>' + content + '</h1></html>'  # email内容
    msgText = MIMEText(mail_content, 'html', 'utf-8')
    msg.attach(msgText)
    if type(to_addrs) == str:
        msg['To'] = to_addrs
    elif type(to_addrs) == list:
        msg['To'] = ','.join(to_addrs)

    e_s = EmailSender(from_addr, to_addrs, msg)
    r_send = e_s.sendIt()
    if r_send != {}:
            #s = smtplib.SMTP('corp.chinacache.com')
        s = smtplib.SMTP('anonymousrelay.chinacache.com')
        s.ehlo()
        s.starttls()
        s.ehlo()
        s.login('noreply', 'SnP123!@#')
        s.sendmail(from_addr, to_addrs, msg.as_string())
        s.quit()


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
    # process(date_str)
    content='Hi,ALL:<br/><br/>此邮件统计的是昨天设备执行刷新任务的状态码，<br/>    0:执行完刷新结果后更新状态时会因为数据集合超过数据库默认的package size而不能正常更新，这部分任务已经执行了刷新;<br/>    503:连接失败;<br/>    204:设备挂起；<br/> 404:FC进程间通信异常；<br/>具体信息请查看附件!'
    send(ads_from,ads_to,'刷新设备状态日报-CBU',content)
    exit()
