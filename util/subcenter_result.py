#! -*- coding=utf-8 -*-
"""
@author: rubin
@create time: 2016/8/8 10:30
statistical sub center information
"""
import http.client
from  datetime import datetime
# from pymongo import MongoClient
import logging
import simplejson as json
from core import database
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from util.emailSender import EmailSender

import sys
import imp
imp.reload(sys)

# connect 82 server
# con83 = MongoClient('mongodb://bermuda:bermuda_refresh@223.202.52.82:27018/bermuda')
# db = con83.bermuda

db = database.query_db_session()



LOG_FILENAME = '/Application/bermuda3/logs/subcenter_result.log'
# LOG_FILENAME = '/home/rubin/logs/rubin_postal.log'

# logging.basicConfig(filename=LOG_FILENAME,
#                     format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s',
#                     level=logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s")
fh = logging.FileHandler(LOG_FILENAME)
fh.setFormatter(formatter)

logger = logging.getLogger('subcenter_result')
logger.addHandler(fh)
logger.setLevel(logging.DEBUG)


# 链接mongo 句柄
db = database.query_db_session()

# the email come from
email_from = 'nocalert@chinacache.com'

# mail recipient list, test
#email_to = ['hongan.zhang@chinacache.com','yanming.liang@chinacache.com','pengfei.hao@chinacache.com','hao.li@chinacache.com']
email_to = ['pengfei.hao@chinacache.com','yanming.liang@chinacache.com']


def get_subcenter_data_from_remote(str):
    """
    :param str:
    :return:
    """
    conn = http.client.HTTPConnection(str)
    headers = {"Content-type": "application/json"}
    conn.request("GET", '/v2/keys/subcenter/', '', headers)
    response = conn.getresponse()
    # logger.debug('response info:%s' % response.read())
    logger.debug('response status:%s' % response.status)
    if response.status == 200:
        return json.loads(response.read()).get('node')
    else:
        return None


def parse_subcenter_data(result):
    """
    parse subcenter data, get ip and name
    :param result: {"key":"/subcenter","dir":true,"nodes":[{"key":"/subcenter/crn-cd-1-5a1","value":"123.94.24.2:21109",
                 "expiration":"2016-08-08T02:36:30.865533081Z","ttl":45,"modifiedIndex":472212,"createdIndex":472212}]}
    :return: {'crn-cd-1-5a1':{'name':crn-cd-1-5a1, 'ip':123.94.24.2}}
    """
    ret_result = {}
    if not result:
        return ret_result
    else:
        nodes = result.get('nodes', None)
        if nodes:
            for node in nodes:
                node_temp = {}
                name = get_name(node.get('key', None))
                if name:
                    node_temp['name'] = name
                else:
                    continue
                ip = get_ip(node.get('value', None))
                if ip:
                    node_temp['ip'] = ip
                else:
                    continue
                ret_result[name] = node_temp
    return ret_result


def get_name(str_key):
    """

    :param str_key:  /subcenter/crn-cd-1-5a1
    :return: crn-cd-1-5a1
    """
    if str_key:
        arr = str_key.split('/')
        return arr[len(arr) - 1]
    else:
        return None

def get_ip(str_value):
    """

    :param str_value: 123.94.24.2:21109
    :return: 123.94.24.2
    """
    if not get_ip:
        return None
    else:
        arr = str_value.split(':')
        return arr[0]


def add_info_to_subcenter(data):
    """
    add info to data of sub center
    :param data: {'crn-cd-1-5a1':{'name':crn-cd-1-5a1, 'ip':123.94.24.2}}
    :return: {'crn-cd-1-5a1':{'name':crn-cd-1-5a1, 'ip':123.94.24.2, 'regionName':xxx, 'provinceName':xxx,
                            'status':'open/close', 'update_time': xxxxx}}
    """
    if data:
        for name in list(data.keys()):
            # name = name.upper()
            try:
                result_db = db.device_app.find_one({'name': name})
                logger.debug('add_info_to_subcenter according name:%s get data success!' % name)
            except Exception:
                logger.debug('get data error:%s' % e)
                # return data
            if result_db:
                data[name]['regionName'] = result_db.get('regionName', None)
                data[name]['provinceName'] = result_db.get('provinceName', None)
            data[name]['status'] = 'open'
            data[name]['update_time'] = datetime.now()
        return data
    else:
        return data

def get_data_from_mongo():
    """
    get all data from sub_regis_info
    :return:
    """
    result = []
    try:
        result = db.sub_regis_info.find()
    except Exception:
        logger.debug("get info from sub_regis_info error:%s" % e)
        return result
    return result


def parse_data_update_mongo(data_info, data_mongo):
    """
    by comparing the data, update the data in the database
    :param data_info: the data is now   {'crn-cd-1-5a1':{'name':crn-cd-1-5a1, 'ip':123.94.24.2, 'regionName':xxx, 'provinceName':xxx,
                            'status':'open/close', 'update_time': xxxxx}}
    :param data_mongo: data in the mongo   [{'_id':xxxxx,'name':crn-cd-1-5a1, 'ip':123.94.24.2, 'regionName':xxx, 'provinceName':xxx,
                            'status':'open/close', 'update_time': xxxxx}]
    :return:
    """
    email_dict = []
    logger.debug('data_info:%s' % data_info)
    if data_mongo:
        for dev in data_mongo:
            name_mongo = dev.get('name')
            if name_mongo and name_mongo in data_info:
                dev['status'] = data_info[name_mongo].get('status')
                dev['update_time'] = data_info[name_mongo].get('update_time')
                # delete update data
                del data_info[name_mongo]
                logger.debug('dev status:%s, update_time:%s' % (dev['status'], dev['update_time']))
            else:
                dev['status'] = 'close'
                dev['update_time'] = datetime.now()
                if dev.get('name') != 'CENTOS6':
                    email_dict.append(dev)
            try:
                logger.debug('_id:%s, type:%s,dev:%s' % (dev.get('_id'), type(dev.get('_id')), dev))
                db.sub_regis_info.update_one({'_id': dev.get('_id')}, {'$set':dev})
                logger.debug("subcenter_result  parse_data_update_mongo  update success!")
            except Exception:
                logger.debug('subcenter_result  parse_data_update_mongo  update error:%s' % e)
    if email_dict:
        assemble_mail_content_send(email_dict)

    if data_info:
        try:
            db.sub_regis_info.insert_many(list(data_info.values()))
            logger.debug("subcenter_result  parse_data_update_mongo insert data_info success!")
        except Exception:
            logger.debug("subcenter_result  parse_data_update_mongo insert data_info error:%s" % e)


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


def assemble_mail_content_send(result_dict):
    """
    assemble  mail content
    according result_dict, assemble mail content, and send to somebody
    :param result_dict: [{'_id':xxxxx,'name':crn-cd-1-5a1, 'ip':123.94.24.2, 'regionName':xxx, 'provinceName':xxx,
                            'status':'open/close', 'update_time': xxxxx}]
    :return:
    """
    content = 'Hi,ALL:<br/>下面是关闭的分中央信息:<br/></br></br>'

    if result_dict:
        for subcenter in result_dict:
            content += "</br>" + "设备名称:&nbsp" + subcenter['name'] + "&nbsp&nbsp"
            content += "设备IP:" + subcenter['ip'] + "&nbsp&nbsp"
            content += '设备状态:' + subcenter['status'] + "&nbsp&nbsp"
            content += "更新时间:" + str(subcenter['update_time']) + "&nbsp&nbsp"
            content += '<br/><br/>'
        logger.debug("send email start.....")
        send(email_from, email_to, '关闭的分中心', content)
        logger.debug("send email end")


def subcenter_main():
    """
    main stream progress
    :return:
    """
    # get data from remote
    result = get_subcenter_data_from_remote('rep.chinacache.com')
    # parse data
    ret_result = parse_subcenter_data(result)

    # ret_result = assemble_subcenter_info()
    # add info to ret_result
    ret_result_new = add_info_to_subcenter(ret_result)
    logger.debug('ret_result_new:%s' % ret_result_new)
    # data from mongo
    mongo_data = get_data_from_mongo()
    # update mongo
    parse_data_update_mongo(ret_result_new, mongo_data)


if __name__ == '__main__':
    subcenter_main()
    os._exit(0)
