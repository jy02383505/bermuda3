#! -*- coding=utf-8 -*-
"""
@version: ??
@author: rubin
@license:
@contact: longjun.zhao@chinacache.com
@site:
@software: PyCharm
@file: autodesk_failed_task_dev.py
@time: 16-11-25 上午9:26
"""

# try:
#     from pymongo import ReplicaSetConnection as MongoClient
# except:
#     from pymongo import MongoClient

from datetime import datetime, timedelta
from bson import ObjectId
import logging
import traceback


import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from core import database
from core.config import config
import os
import time

from util.tools import get_mongo_str
from util.emailSender import EmailSender


LOG_DIR_ALL = '/Application/bermuda3/logs/custom_all/'
LOG_DIR_FAILED = '/Application/bermuda3/logs/custom_failed/'

LOG_FILENAME = '/Application/bermuda3/logs/autodesk_failed_task_dev.log'
# LOG_FILENAME = '/home/rubin/logs/check_url_autodesk.log'
# logging.basicConfig(filename=LOG_FILENAME, format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s', level=logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s")
fh = logging.FileHandler(LOG_FILENAME)
fh.setFormatter(formatter)

logger = logging.getLogger('autodesk_failed_url_dev')
logger.addHandler(fh)
logger.setLevel(logging.DEBUG)



# conn = MongoClient('mongodb://bermuda:bermuda_refresh@223.202.52.136:27017/bermuda')
# db = conn.bermuda


# 链接mongo 句柄
db = database.query_db_session()
db_s1 = database.s1_db_session()

email_from = 'nocalert@chinacache.com'
# email_to = eval(config.get('autodesk', 'failed_task_group'))
# email_to = ['longjun.zhao@chinacache.com']


def parse_data(str_id, username, created_time):
    """
    return_r  structure
    {dev_name:{'name':xxx, 'ip': xxx, 'type_name': xxx,'urls': [xx,xxx,xx,...], 'dirs': [xxx,xxx,xxx]},
    'dev_name1': {'name':xxx, 'ip': xxx, 'type_name': xxx, 'urls': [{'url':xxx, 'code': xxx},{'url':xxx, 'code':xx},...],
    'dirs': [{'dir':xxx, 'code':xxx},...]}}
    :return:
    """

    return_r = {}
    url_all = []
    try:
        # result = db.url.find({"r_id": ObjectId(str_id), "status": "FAILED"})
        result = db.url.find({"r_id": ObjectId(str_id)}).batch_size(20)
        logger.debug("get data from url_autodesk r_id:%s" % str_id)
    except Exception:
        logger.debug("get data error from url_autodesk r_id:%s, error:%s" % (str_id, e))

    for res in result:
        print("res:%s" % res)
        logger.debug("autodesk_failed_task_dev res:%s" % res)
        dev_id = res.get("dev_id")
        if dev_id:
            dev_id = str(res.get("dev_id"))
        else:
            logger.debug('can not get dev_id')
            continue
        try:
            dev_result = db.device.find_one({"_id": ObjectId(dev_id)})
            logger.debug("get data from device success, dev_id:%s" % (dev_id))
        except Exception:
            logger.debug("through dev_id get data from device error:%s, dev_id:%s" % (e, dev_id))
            continue
        url = res.get('url')
        is_dir = res.get('isdir')

        if not url:
            # not exists url, break this
            continue
        # store all url
        url_all.append(url)

        try:
            if dev_result:
                devices = list(dev_result.get("devices").values())
                if devices:
                    # return_r[url] = []
                    for dev in devices:
                        name = dev.get("name")
                        host = dev.get('host')
                        if dev.get("code") not in [200, 204]:
                            if name not in return_r:

                                temp = {}
                                temp['type_name'] = dev.get('type')
                                temp['name'] = name
                                temp['host'] = host
                                if is_dir:
                                    temp['dirs'] = []
                                    temp_dir = {}
                                    temp_dir['dir'] = url
                                    temp_dir['code'] = dev.get('code')
                                    temp_dir['a_code'] = dev.get('a_code', 0)
                                    temp_dir['r_code'] = dev.get('r_code', 0)
                                    temp['dirs'].append(temp_dir)

                                else:
                                    temp['urls'] = []
                                    temp_url = {}
                                    temp_url['url'] = url
                                    temp_url['code'] = dev.get('code')
                                    temp_url['a_code'] = dev.get('a_code', 0)
                                    temp_url['r_code'] = dev.get('r_code', 0)
                                    temp['urls'].append(temp_url)
                                return_r[name] = temp

                            else:
                                temp = return_r[name]
                                if is_dir:
                                    temp_dir = {}
                                    temp_dir['code'] = dev.get('code')
                                    temp_dir['dir'] = url
                                    temp_dir['a_code'] = dev.get('a_code', 0)
                                    temp_dir['r_code'] = dev.get('r_code', 0)
                                    if temp.get('dirs'):
                                        temp['dirs'].append(temp_dir)
                                    else:
                                        temp['dirs'] = [temp_dir]
                                else:
                                    temp_url = {}
                                    temp_url['code'] = dev.get('code')
                                    temp_url['a_code'] = dev.get('a_code', 0)
                                    temp_url['r_code'] = dev.get('r_code', 0)
                                    temp_url['url'] = url
                                    if temp.get('urls'):
                                        temp['urls'].append(temp_url)
                                    else:
                                        temp['urls'] = [temp_url]
        except Exception:
            logger.debug("autodesk_failed_task_dev error:%s" % traceback.format_exc())
            return
        logger.debug('return_r:%s' % return_r)
        try:
            if res.get('retry_branch_id'):
                dev_subcenter = db.retry_device_branch.find_one({"_id": ObjectId(str(res.get("retry_branch_id")))})
            else:
                dev_subcenter = {}
        except Exception:
            logger.debug("get data, error:%s" % e)
        # central processing results
        try:
            if dev_subcenter:
                sub_devices = dev_subcenter.get("devices")
                if sub_devices:
                    for dev in sub_devices:
                        name = dev.get('name')
                        # host = dev.get('host')
                        branch_code = dev.get('branch_code')
                        temp = return_r.get(name)
                        if branch_code and branch_code == 200:

                            if is_dir:
                                len_dirs = len(temp.get('dirs', []))
                                for i in range(len_dirs):
                                    dir_temp = temp['dirs'][i]
                                    if dir_temp['dir'] == url:
                                        del temp.get('dirs')[i]
                                        break
                            else:
                                len_urls = len(temp.get('urls', []))
                                for i in range(len_urls):
                                    dir_temp = temp['urls'][i]
                                    if dir_temp['url'] == url:
                                        del temp.get('urls')[i]
                                        break
                        if not temp.get('dirs') and (not temp.get('urls')):
                            return_r.pop(name)
        except Exception:
            logger.debug("parse_data  sub center error:%s" % traceback.format_exc())

    logger.debug("email original content:%s" % return_r)
    # # parse return_r
    # parse_return_r = get_final_result(return_r)
    # logger.debug("pasre_data parse_return_r:%s" % parse_return_r)
    # # change equipment latitude
    # parse_return_r = get_dev_final_result(parse_return_r)
    # logger.debug("parse_data 2 parse_return_r:%s" % parse_return_r)
    # save all URL files start
    timestamp_now = trans_timestamp_to_str(time.time())
    logger.debug('parse_data store all urls starting rid:%s, timestamp_now:%s' % (str_id, timestamp_now))

    store_all_urls(url_all, timestamp_now)
    logger.debug('parse_data store all urls end rid:%s, timestamp_now:%s' % (str_id, timestamp_now))
    # save all URL files end

     # store failed urls,  file start
    logger.debug('parse_data store failed urls starting rid:%s, timestamp_now:%s' % (str_id, timestamp_now))
    store_failed_urls(return_r, timestamp_now)
    logger.debug('parse_data store failed urls end rid:%s, timestamp_now:%s' % (str_id, timestamp_now))
    # get email_to list
    email_to = get_email_to_list(username)
    logger.debug("autodesk_failed_task_dev email_to:%s" % email_to)
    if not email_to:
        return
    if not return_r:
        content = combine_success_content(username, created_time)
        send(email_from, email_to, '刷新新接口，下发状态邮件', content, timestamp_now)
        logger.debug('return_r is null')
        return
    else:
        logger.debug('have return_r send email start....')
        content = get_content_string(return_r, username, created_time)
        logger.debug("email content:%s" % content)
        logger.debug('send email start...')
        logger.debug("email_from:%s, email_to:%s, " % (email_from, email_to))
        send(email_from, email_to, '刷新新接口，下发状态邮件', content, timestamp_now)
        logger.debug('send email end ...')


def parse_data_last(str_id, username, created_time):
    """
    return_r  structure
    {dev_name:{'name':xxx, 'ip': xxx, 'type_name': xxx,'urls': [xx,xxx,xx,...], 'dirs': [xxx,xxx,xxx]},
    'dev_name1': {'name':xxx, 'ip': xxx, 'type_name': xxx, 'urls': [{'url':xxx, 'code': xxx},{'url':xxx, 'code':xx},...],
    'dirs': [{'dir':xxx, 'code':xxx},...]}}
    :return:
    """

    return_r = {}
    url_all = []
    try:
        # result = db.url.find({"r_id": ObjectId(str_id), "status": "FAILED"})
        result = db.url.find({"r_id": ObjectId(str_id)}).batch_size(20)
        logger.debug("get data from url_autodesk r_id:%s" % str_id)
    except Exception:
        logger.debug("get data error from url_autodesk r_id:%s, error:%s" % (str_id, e))

    urls = []
    map_result_hpcc = {}
    map_result_fc = {}
    map_result_unknown = {}

    try:
        for res in result:
            print("res:%s" % res)
            logger.debug("autodesk_failed_task_dev res:%s" % res)
            dev_id = res.get("dev_id")
            if dev_id:
                dev_id = str(res.get("dev_id"))
            else:
                logger.debug('can not get dev_id')
                continue
            try:
                dev_result = db.device.find_one({"_id": ObjectId(dev_id)})
                logger.debug("get data from device success, dev_id:%s" % (dev_id))
            except Exception:
                logger.debug("through dev_id get data from device error:%s, dev_id:%s" % (e, dev_id))
                continue
            url = res.get('url')
            urls.append(url)
            is_dir = res.get('isdir')
            _id = str(res.get('_id'))
            retry_branch_id = str(res.get('retry_branch_id', ''))


            if not url:
                # not exists url, break this
                continue
            # get result of hpcc device

            devices = get_all_hpcc_dev(list(dev_result.get('devices').values()))

            result_dev = get_all_report_hpcc_dev(_id)
            if not is_dir:
                judge_re = judge_result(devices, result_dev, type_t='url')
            else:
                judge_re = judge_result(devices, result_dev, type_t='dir')
            success, failed, not_handled = parse_result(judge_re)
            # url as a key will have risk of  Chinese can not be restored
            if len(failed) + len(not_handled) > 0:
                map_result_hpcc[_id] = {"url": url, "failed": failed, "not_handled": not_handled, "url_type": is_dir}

            # progress fc
            devices_fc = get_all_fc_dev(list(dev_result.get('devices').values()), code='code')
            if retry_branch_id:
                result_dev_fc = get_retry_branch_dev(retry_branch_id)
                devices_fc = judge_result_fc(devices_fc, result_dev_fc)
            success_fc, failed_fc, not_handled_fc = parse_result_fc(devices_fc)
            if len(failed_fc) + len(not_handled_fc) > 0:
                map_result_fc[_id] = {'url': url, 'failed': failed_fc, 'not_handled': not_handled_fc, 'url_type': is_dir}


            # progress unknown
            devices_unknow = get_all_fc_dev(list(dev_result.get('devices').values()), code='code', type_dev='unknown')
            if retry_branch_id:
                result_dev_unknown = get_retry_branch_dev(retry_branch_id)
                devices_unknow = judge_result_fc(devices_unknow, result_dev_unknown)
            success_unknown, failed_unknown, not_handled_unknown = parse_result_fc(devices_unknow)
            if (len(failed_unknown) + len(not_handled_unknown)) > 0:
                map_result_unknown[_id] = {'url': url, 'failed': failed_unknown, 'not_handled': not_handled_unknown, 'type_device':'unknown'}


    except Exception:
        logger.debug('parse_data_last formation map_result error:%s' % traceback.format_exc())
        return {}

    timestamp_now = trans_timestamp_to_str(time.time())
    logger.debug('parse_data_last store all urls starting rid:%s, timestamp_now:%s' % (str_id, timestamp_now))

    store_all_urls(urls, timestamp_now)
    logger.debug('parse_data_last store all urls end rid:%s, timestamp_now:%s' % (str_id, timestamp_now))

    if map_result_hpcc or map_result_fc or map_result_unknown:
        email_to_last = get_email_to_list(username, address="email_address_end")
        # send email
        content = get_content_string_last(map_result_hpcc, username, created_time)
        content += get_content_string_last_fc(map_result_fc, type_t='FC')
        content += get_content_string_last_fc(map_result_unknown, type_t='unknown')
        logger.debug("email content:%s" % content)
        logger.debug('send email start...')
        logger.debug("email_from:%s, email_to:%s, " % (email_from, email_to_last))
        # if type_falg == 1   the same to autodesk2  , type_flag ==2  not have failed dev attachment
        send(email_from, email_to_last, '刷新新接口，下发状态邮件', content, timestamp_now, type_flag=2)
        logger.debug('send email end ...')
    else:
        logger.info("all device is success, don't send email, url _id:%s" % str_id)




def get_retry_branch_dev(retry_branch_id):
    """

    Args:
        retry_branch_id:

    Returns:

    """
    try:
        result = db.retry_device_branch.find_one({'_id': ObjectId(retry_branch_id)})
        logger.debug("get_retry_branch_dev result:%s" % result)
        if result:
            devices = result.get('devices')
            logger.debug("get_retry_branch_dev retry_branch_id:%s, devices:%s" % (retry_branch_id, devices))
            return devices
        return {}
    except Exception:
        logger.info('get_retry_branch_dev  retry_branch_id:%s, error:%s' % (retry_branch_id, traceback.format_exc()))
        return {}



def get_content_string_last(return_r, username, created):
    """
　　　
    :param parse_return_r:
    {dev_name:{'name':xxx, 'ip': xxx, 'type_name': xxx,'urls': [xx,xxx,xx,...], 'dirs': [xxx,xxx,xxx]},
    'dev_name1': {'name':xxx, 'ip': xxx, 'type_name': xxx, 'urls': [{'url':xxx, 'code': xxx},{'url':xxx, 'code':xx},...],
    'dirs': [{'dir':xxx, 'code':xxx},...]}}
    param utl_type: True  dir,  False url
    :return:
    """
    content = "Hi,ALL:<br/>下面是刷新失败的url 对应的刷新设备，即刷新命令:<br/>"
    content += "用户名称:" + username + "<br/>"
    content += "刷新开始时间:" + created + "<br/>"
    logger.debug('get_content_string_last get_content_string return_r:%s' % return_r)
    try:
        for res in return_r:
            value = return_r.get(res)
            url = value.get('url')
            failed_dev = value.get('failed')
            not_handled = value.get('not_handled')
            url_type = value.get('url_type')
            if not url:
                logger.debug('url is null')
                continue
            content += url + "<br/>"
            content += "刷新命令："
            if not url_type:
                content += combination_refresh_command_hpcc_url(url)
            else:
                content += combination_refresh_command_hpcc_dir(url)
            content += "<br/>"
            temp_i = 0
            if failed_dev:
                content += "刷新失败的设备：<br/>"
                for dev in failed_dev:
                    temp_i += 1
                    content += dev + "\b  "
                    if not (temp_i % 4):
                        content += "<br/>"
            if not_handled:
                temp_i = 0
                content += "刷新没有收到结果的设备：<br/>"
                for dev in not_handled:
                    temp_i += 1
                    content += dev + "\b  "
                    if not (temp_i % 4):
                        content += "<br/>"
    except Exception:
        logger.debug("get_content_string  error:%s" % traceback.format_exc())
        return "email error"
    logger.debug("get_content_string content:%s" % content)
    return content


def get_content_string_last(return_r, username, created):
    """
　　　
    :param parse_return_r:
    {dev_name:{'name':xxx, 'ip': xxx, 'type_name': xxx,'urls': [xx,xxx,xx,...], 'dirs': [xxx,xxx,xxx]},
    'dev_name1': {'name':xxx, 'ip': xxx, 'type_name': xxx, 'urls': [{'url':xxx, 'code': xxx},{'url':xxx, 'code':xx},...],
    'dirs': [{'dir':xxx, 'code':xxx},...]}}
    param utl_type: True  dir,  False url
    :return:
    """
    content = "Hi,ALL:<br/>下面是刷新失败的url 对应的刷新设备，即刷新命令:<br/>"
    content += "用户名称:" + username + "<br/>"
    content += "刷新开始时间:" + created + "<br/>"
    try:
        for res in return_r:
            value = return_r.get(res)
            url = value.get('url')
            failed_dev = value.get('failed')
            not_handled = value.get('not_handled')
            url_type = value.get('url_type')
            if not url:
                logger.debug('url is null')
                continue
            content += url + "<br/>"
            content += "刷新命令："
            if not url_type:
                content += combination_refresh_command_hpcc_url(url)
            else:
                content += combination_refresh_command_hpcc_dir(url)
            content += "<br/>"
            temp_i = 0
            if failed_dev:
                content += "刷新失败的设备：<br/>"
                for dev in failed_dev:
                    temp_i += 1
                    content += dev + "\b  "
                    if not (temp_i % 4):
                        content += "<br/>"
                content += "<br/>"

            if not_handled:
                temp_i = 0
                content += "刷新没有收到结果的设备：<br/>"
                for dev in not_handled:
                    temp_i += 1
                    content += dev + "\b  "
                    if not (temp_i % 4):
                        content += "<br/>"
                content += "<br/>"
    except Exception:
        logger.debug("get_content_string  error:%s" % traceback.format_exc())
        return "email error"
    logger.debug("get_content_string_last get_content_string content:%s" % content)
    return content


def get_content_string_last_fc(return_r, type_t='FC'):
    """
　　　
    :param parse_return_r:
    {dev_name:{'name':xxx, 'ip': xxx, 'type_name': xxx,'urls': [xx,xxx,xx,...], 'dirs': [xxx,xxx,xxx]},
    'dev_name1': {'name':xxx, 'ip': xxx, 'type_name': xxx, 'urls': [{'url':xxx, 'code': xxx},{'url':xxx, 'code':xx},...],
    'dirs': [{'dir':xxx, 'code':xxx},...]}}
    param utl_type: True  dir,  False url
    :return:
    """
    content = "<br/>"
    try:
        for res in return_r:
            value = return_r.get(res)
            url = value.get('url')
            failed_dev = value.get('failed')
            not_handled = value.get('not_handled')
            url_type = value.get('url_type')
            if not url:
                logger.debug('url is null')
                continue
            content += url + "<br/>"
            content += "刷新命令："
            if not url_type:
                if type_t == 'FC':
                    content += combination_refresh_command_fc_url(url)
                else:
                    content += combination_refresh_command_fc_url(url) + '<br/>'
                    content += combination_refresh_command_hpcc_url(url)
            else:
                if type_t == 'FC':
                    content += combination_refresh_command_fc_dir(url)
                else:
                    content += combination_refresh_command_fc_dir(url) + '<br/>'
                    content += combination_refresh_command_hpcc_dir(url)
            content += "<br/>"
            temp_i = 0
            if failed_dev:
                content += "刷新失败的设备：<br/>"
                for dev in failed_dev:
                    temp_i += 1
                    content += dev + "\b  "
                    if not (temp_i % 4):
                        content += "<br/>"
                content += "<br/>"
            if not_handled:
                temp_i = 0
                content += "刷新没有收到结果的设备：<br/>"
                for dev in not_handled:
                    temp_i += 1
                    content += dev + "\b  "
                    if not (temp_i % 4):
                        content += "<br/>"
                content += "<br/>"
    except Exception:
        logger.debug("get_content_string  error:%s" % traceback.format_exc())
        return "email error"
    logger.debug("get_content_string content:%s" % content)
    return content



def get_all_hpcc_dev(devices, type_dev='HPCC'):
   """

   Args:
       devices:  [{"status" : "OPEN",
            "code" : NumberInt(200),
            "name" : "CHN-JQ-2-3G1",
            "total_cost" : "0.57",
            "connect_cost" : "0.11",
            "serialNumber" : "01079523G1",
            "a_code" : NumberInt(200),
            "r_code" : NumberInt(200),
            "host" : "117.21.218.9",
            "response_cost" : "0.46",
            "firstLayer" : false,
            "type" : "HPCC",
            "port" : NumberInt(21108)}, {
            }]
        type_dev: the type of device

   Returns:{"dev": 0, "dev1": 0}

   """
   result = {}
   try:
       if not devices:
           return {}
       else:
           for dev in devices:
               if dev.get('type') == type_dev:
                   dev_name = dev.get('name')
                   # dev_name = dev_name_temp.rsplit('-', 1)[0]
                   logger.debug('get_all_hpcc_dev dev_name:%s, type:%s' % (dev_name, type_dev))
                   if not dev_name or (dev.get('code') == 204):
                       logger.debug('get_all_hpcc_dev device suspend dev_name:%s, code:%s' %
                                    (dev_name, dev.get('code')))
                       continue
                   else:
                       result[dev_name] = {'data': 0, "name": dev_name}
           logger.debug('get_all_hpcc_dev  result:%s' % result)
           return result
   except Exception:
       logger.debug('get_all_hpcc_dev parse devices error:%s' % traceback.format_exc())
       return result


def get_all_fc_dev(devices, code='code', type_dev='FC'):
   """

   Args:
       devices:  [{"status" : "OPEN",
            "code" : NumberInt(200),
            "name" : "CHN-JQ-2-3G1",
            "total_cost" : "0.57",
            "connect_cost" : "0.11",
            "serialNumber" : "01079523G1",
            "a_code" : NumberInt(200),
            "r_code" : NumberInt(200),
            "host" : "117.21.218.9",
            "response_cost" : "0.46",
            "firstLayer" : false,
            "type" : "HPCC",
            "port" : NumberInt(21108)}, {
            }]
        type_dev: the type of device

   Returns:{"dev": 0, "dev1": 0}

   """
   result = {}
   try:
       if not devices:
           return {}
       else:
           for dev in devices:
               if dev.get('type') == type_dev:
                   dev_name = dev.get('name')
                   logger.debug('get_all_hpcc_dev dev_name:%s, type:%s' % (dev_name, type_dev))
                   if not dev_name or (dev.get(code) == 204):
                       continue
                   else:
                       dev_code = dev.get(code)
                       if dev_code == 200:
                           result[dev_name] = 1
                       else:
                           result[dev_name] = 0
           logger.debug('get_all_hpcc_dev  result:%s' % result)
           return result
   except Exception:
       logger.info('get_all_hpcc_dev parse devices error:%s' % traceback.format_exc())
       return result





def get_all_report_hpcc_dev(_id):
    """
    according  _id session_id in refresh_result
    Args:
        _id: the session_id in refresh_result

    Returns:the list of device of all hpcc device

    """
    str_num = ''
    try:
        num_str =config.get('refresh_result', 'num')
        str_num = get_mongo_str(str(_id), num_str)
    except Exception:
        logger.debug('get refresh_result get number of refresh_result error:%s' % traceback.format_exc())
    result_r = []
    try:

        result = db_s1['refresh_result' + str_num].find({"session_id": _id})
        if not result:
            return []
        else:
            for res in result:
                result_r.append(res)
        return result_r
    except Exception:
        logger.debug("get_all_report_hpcc_dev error:%s" % traceback.format_exc())
        return result_r





def judge_result(devices, result_dev, type_t='url'):
    """
    according result_dev, set devices
    Args:
        devices:
        result_dev:
        type_t:

    Returns: {"dev": 8}
              1           1
            success    failed
    """
    try:
        for res in result_dev:
            code = 0
            if type_t == 'url':
                result = res.get('result')
                result_gzip = res.get('result')
                if result == '200' and result_gzip == '200':
                    code = 2
                elif result != '0' or result_gzip != '0':
                    code = 1
                else:
                    code = 0
            elif type_t == 'dir':
                result = res.get('result')
                if result == '200':
                    code = 2
                elif result != '0':
                    code = 1
                else:
                    code = 0
            dev_name = res.get('name')
            if dev_name in devices:
                value = devices[dev_name]
                # data = value.get('data')
                value['data'] |= code
                # value |= code
                devices[dev_name] = value
        return devices
    except Exception:
        logger.debug('judge_result error:%s' % traceback.format_exc())
        return devices


def judge_result_fc(devices, result_dev, type_t='url'):
    """
    according result_dev, set devices
    Args:
        devices:
        result_dev:
        type_t:

    Returns: {"dev": 8}
             1 success  0 failed
    """
    try:
        for res in result_dev:
            name = res.get('name')
            if res.get('branch_code') == 200:
                if name in devices:
                    devices[name] = 1
        return devices
    except Exception:
        logger.debug('judge_result_fc error:%s' % traceback.format_exc())
        return devices


def parse_result(judge_result):
    """
    parse result
    Args:
        judge_result: {"dev1": 2, "dev2": 1, "dev3": 0}

    Returns:success[], failed[], not_handled[]

    """
    logger.debug('parse_result  judge_result:%s' % judge_result)
    success = []
    failed = []
    not_handled = []
    try:
        if not judge_result:
            return [], [], []
        else:
            for res in judge_result:
                if (judge_result[res]['data'] & 2) == 2:
                    success.append(judge_result[res]['name'])
                elif (judge_result[res]['data'] & 1) == 1:
                    failed.append(judge_result[res]['name'])
                else:
                    not_handled.append(judge_result[res]['name'])
        logger.debug('parse_result success:%s, failed:%s, not_handled:%s' % (success, failed, not_handled))
        return success, failed, not_handled
    except Exception:
        logger.debug('parse_result error:%s' % traceback.format_exc())
        logger.debug("parse_result error success:%s, failed:%s, not_handled:%s" % (success, failed, not_handled))
        return success, failed, not_handled


def parse_result_fc(judge_result):
    """
    parse result
    Args:
        judge_result: {"dev1": 2, "dev2": 1, "dev3": 0}

    Returns:success[], failed[], not_handled[]

    """
    logger.debug('parse_result_fc  judge_result:%s' % judge_result)
    success = []
    failed = []
    not_handled = []
    try:
        if not judge_result:
            return [], [], []
        else:
            for res in judge_result:
                if judge_result[res] == 1:
                    success.append(res)
                else:
                    failed.append(res)
        logger.debug('parse_result success:%s, failed:%s, not_handled:%s' % (success, failed, not_handled))
        return success, failed, not_handled
    except Exception:
        logger.debug('parse_result error:%s' % traceback.format_exc())
        logger.debug("parse_result error success:%s, failed:%s, not_handled:%s" % (success, failed, not_handled))
        return success, failed, not_handled


def get_email_to_list(username, address="email_address"):
    """
    according username, get email_address list
    Args:
        username: the user of custom
        address:

    Returns:

    """
    result = ""
    try:
        result = db.email_management.find_one({"custom_name": username})
        logger.debug("get username:%s success, result:%s" % (username, result))
    except Exception:
        logger.debug('autodesk_failed_task_dev get_email_to_list error:%s' % traceback.format_exc())
    if result:
        email_address = result.get(address)
        if email_address:
            return email_address
    return None

def trans_timestamp_to_str(timestamp):
    """
    trans timestamp to str
    Args:
        timestamp:

    Returns:

    """


    try:
        datetime_temp = datetime.fromtimestamp(timestamp)
        print(datetime_temp)
        str = datetime_temp.strftime("%Y_%m_%d_%H_%M_%S_%f")
        print("str:%s" % str)
        logger.debug("timestamp:%s, str:%s" % (timestamp, str))
        return str
    except Exception:
        logger.debug("trans timestamp error:%s" % traceback.format_exc())
        return timestamp


def combine_success_content(username, created_time):
    """

    Returns:

    """
    content = "Hi,ALL:<br/>本次下发全部成功<br/>"
    content += "用户名称:" + username + "<br/>"
    content += "刷新开始时间:" + created_time + "<br/>"
    return content


def get_final_result(result_r):
    """
    analysis results return results
    :param result_r: { url1:["a", "b", "c"], url2:[], url3:["d", "f"]}
    :return: {url1:["a", "b", "c"], url3:["d", "f"]}
    """
    result_new = {}
    if not result_r:
        return {}
    else:
        for res in result_r:
            if result_r[res]:
                # delete result_r[res] == []
                result_new[res] = result_r[res]
    return result_new


def get_dev_final_result(parse_return_r):
    """
    equipment latitude
    :param parse_return_r:
    :return:
    """
    result = {}
    if not parse_return_r:
        return {}
    else:
        for par in parse_return_r:
            for pa in parse_return_r[par]:
                if pa in result:
                    result[pa].append(par)
                else:
                    result[pa] = []
                    result[pa].append(par)
    return result


def get_content_string(return_r, username, created):
    """

    :param parse_return_r:
    {dev_name:{'name':xxx, 'ip': xxx, 'type_name': xxx,'urls': [xx,xxx,xx,...], 'dirs': [xxx,xxx,xxx]},
    'dev_name1': {'name':xxx, 'ip': xxx, 'type_name': xxx, 'urls': [{'url':xxx, 'code': xxx},{'url':xxx, 'code':xx},...],
    'dirs': [{'dir':xxx, 'code':xxx},...]}}
    :return:
    """
    content = "Hi,ALL:<br/>下面是出现问题设备和url:<br/>"
    content += "用户名称:" + username + "<br/>"
    content += "刷新开始时间:" + created + "<br/>"
    content += "r_code 如果等于502,说明机器上的刷新进程已经挂了，需要重启进程，然后执行刷新命令" + "<br/>"
    try:
        for res in return_r:
            content += "<br/>"
            name = return_r[res].get('name')
            host = return_r[res].get('host')
            content += name + "    "
            content += host + ":<br/>"
            # dev ,  host
            urls = return_r[res].get('urls')
            dirs = return_r[res].get('dirs')
            if urls:
                for url_t in urls:
                    # content += url_t.get('url') + "  " + str(url_t.get('code')) + "<br/>"
                    content += url_t.get('url') + "  " + "code:" + str(url_t.get('code')) + " " + \
                               "a_code:" + str(url_t.get('a_code')) + " " + "r_code:" + str(url_t.get('r_code'))+ "<br/>"
            if dirs:
                for dir_t in dirs:
                    # content += dir_t.get('dir') + "  " + str(dir_t.get('code')) + "<br/>"
                    content += dir_t.get('dir') + "  " + "code:" + str(url_t.get('code')) + " " + \
                               "a_code:" + str(url_t.get('a_code')) + " " + "r_code:" + str(url_t.get('r_code')) + "<br/>"
    except Exception:
        logger.debug("get_content_string  error:%s" % traceback.format_exc())
        return "email error"
    logger.debug("get_content_string get_content_string content:%s" % content)
    return content


def store_failed_urls(content, timestamp):
    """
    the name fo file failed_+timestamp.txt
    Args:
        content: the content of failed dev dict  [dev_name:{'name':xxx, 'ip': xxx, 'urls': [xx,xxx,xx,...], 'dirs': [xxx,xxx,xxx]},
    'dev_name1': {'name':xxx, 'ip': xxx, 'urls': [{'url':xxx, 'code': xxx},{'url':xxx, 'code':xx},...], 'dirs': [{'dir':xxx, 'code':xxx},...]}]
        timestamp: timestamp

    Returns:

    """
    try:
        if not os.path.exists(LOG_DIR_FAILED):
            os.makedirs(LOG_DIR_FAILED)
        with open('%sfailed_%s.txt' % (LOG_DIR_FAILED, timestamp), 'a+') as file_w:
            for res in content:
                temp = content[res]
                file_w.write(temp['name'] + "  ")
                file_w.write(temp['host'] + '\r\n')
                set_temp = set()
                urls = temp.get('urls')
                dirs = temp.get('dirs')
                if temp.get('type_name') == 'FC':

                    if urls:
                        for url in urls:
                            command = combination_refresh_command_fc_url(url.get('url'))
                            if command not in set_temp:
                                file_w.write(command + '\r\n')
                                set_temp.add(command)
                    if dirs:
                        for dir in dirs:
                            command = combination_refresh_command_fc_dir(dir.get('dir'))
                            if command not in set_temp:
                                file_w.write(command + '\r\n')
                elif temp.get('type_name') == 'HPCC':
                    if urls:
                        for url in urls:
                            command = combination_refresh_command_hpcc_url(url.get('url'))
                            if command not in set_temp:
                                file_w.write(command + '\r\n')
                                set_temp.add(command)
                    if dirs:
                        for dir in dirs:
                            command = combination_refresh_command_hpcc_dir(dir.get('dir'))
                            if command not in set_temp:
                                file_w.write(command + '\r\n')
                else:
                    if urls:
                        for url in urls:
                            command_1 = combination_refresh_command_hpcc_url(url.get('url'))
                            command_2 = combination_refresh_command_fc_url(url.get('url'))
                            if command_1 not in set_temp:
                                file_w.write(command_1 + '\r\n')
                                set_temp.add(command_1)
                            if command_2 not in set_temp:
                                file_w.write(command_2 + '\r\n')
                                set_temp.add(command_2)
                    if dirs:
                        for dir in dirs:
                            command_1 = combination_refresh_command_hpcc_dir(dir.get('dir'))
                            command_2 = combination_refresh_command_fc_dir(dir.get('dir'))
                            if command_1 not in set_temp:
                                file_w.write(command_1 + '\r\n')
                                set_temp.add(command_1)
                            if command_2 not in set_temp:
                                file_w.write(command_2 + '\r\n')
                                set_temp.add(command_2)

                # # assembly order
                # for dev in content[res]:
                #     str_command_temp = combination_refresh_command_hpcc_url(dev)
                #     if str_command_temp not in set_temp:
                #         file_w.write(combination_refresh_command_hpcc_url(dev) + '\r\n')
                #         set_temp.add(str_command_temp)
                set_temp.clear()

    except Exception:
        logger.debug('store_failed_urls error:%s' % traceback.format_exc())
        return


def store_all_urls(content, timestamp):
    """
    the name of file all_+timestamp.txt
    Args:
        content: ['url1', 'url2', 'url3']
        timestamp: timestamp

    Returns:

    """
    if not os.path.exists(LOG_DIR_ALL):
        os.makedirs(LOG_DIR_ALL)
    try:
        with open('%sall_%s.txt' % (LOG_DIR_ALL, timestamp), 'a+') as file_w:
            for content_temp in content:
                file_w.write(content_temp + "\r\n")
    except Exception:
        logger.debug('store_all_urls error:%s' % traceback.format_exc())
        return


def combination_refresh_command_hpcc_url(url):
    """
    url
    parse url and combination refresh command
    Args:
        url: https://dl-test.appstreaming.autodesk.com/production-update-latency-test/954/23726.json

    Returns:curl -svo /dev/null http://127.0.0.1:770/delete/dl-test.appstreaming.autodesk.com:443/production-update-latency-test/954/23726.json

    """
    if url:
        array_url = url.split('/', 3)
        if len(array_url) < 3:
            return ''
        else:
            temp = array_url[2].split(':')
            array_url[2] = temp[0]
        return 'curl -svo /dev/null "http://127.0.0.1:770/delete/%s:443/%s"' % (array_url[2], array_url[3])
    else:
        return ''


def combination_refresh_command_hpcc_dir(url):
    """

    Args:
        url:

    Returns: hpcc refresh dir

    """
    if url:
        array_url = url.split('/', 2)
        if len(array_url) < 2:
            return ''

    if url:
        return 'curl -sv refreshd  -d "<?xml version=\\"1.0\\" encoding=\\"UTF-8\\"?><method name=\\"dir_purge\\" sessionid=\\"1\\"><dir>%s</dir></method>" -x  127.0.0.1:21108' % array_url[2]
    return ''



def combination_refresh_command_fc_dir(url):
    """

    Args:
        url:

    Returns: fc refresh url

    """
    if url:
        return 'refresh_cli -d "%s"' % url
    return ''


def combination_refresh_command_fc_url(url):
    """

    Args:
        url:

    Returns:

    """
    if url:
        url_t1 = 'refresh_cli -f "%s@@@Accept-Encoding:gzip"' % url
        url_t2 = 'refresh_cli -f "%s"' % url

        return url_t1 + "\r\n" + url_t2
    else:
        return ''


# 发邮件
def send(from_addr, to_addrs, subject, content, timestamp, type_flag=1):
    msg = MIMEMultipart()
    try:
        # all url accessories
        att1 = MIMEText(open('%sall_%s.txt' % (LOG_DIR_ALL, timestamp), 'rb').read(), \
                        'base64', 'utf-8')
        att1['Content-Type'] = 'application/octet-stream'
        att1['Content-Disposition'] = 'attachment;filename="all_%s.txt"' %  timestamp
        msg.attach(att1)

        # all failed url accessories
        if type_flag == 1:
            att2 = MIMEText(open('%sfailed_%s.txt' % (LOG_DIR_FAILED, timestamp), 'rb').read(), \
                            'base64', 'utf-8')
            att2['Content-Type'] = 'application/octet-stream'
            att2['Content-Disposition'] = 'attachment;filename="failed_%s.txt"' % timestamp
            msg.attach(att2)
    except Exception:
        logger.debug('send email, acquisition attachment error:%s' % traceback.format_exc())
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
            logger.debug('send email error:%s' % traceback.format_exc())
        # s.login('noreply', 'SnP123!@#')
        s.sendmail(from_addr, to_addrs, msg.as_string())
        s.quit()


def get_r_id_from_request(timestamp, status='FAILED'):
    """

    :param timestamp:the timestamp of now
    :param status: default FAILED
    :return:
    """
    try:
        # result = db.request.find_one_and_update({'failed_flag': {"$exists": False},
        #                 'executed_end_time_timestamp': {'$gte': timestamp, '$lt': timestamp + 180}, 'status': status},
        #                 {'$set': {'failed_flag': 1}})
        result = db.request.find_one_and_update({'failed_flag': {"$exists": False},
                        'executed_end_time_timestamp': {'$gte': timestamp, '$lt': timestamp + 180}},
                        {'$set': {'failed_flag': 1}})
        # # test
        # result = db.request.find_one_and_update({'failed_flag': {"$exists": False},
        #                 'executed_end_time_timestamp': {'$gte': timestamp, '$lt': timestamp + 260}},
        #                 {'$set': {'failed_flag': 1}})
        logger.debug("get_r_id_from_request find data from request success")
    except Exception:
        logger.debug('get_r_id_from_request get data from request error:%s' % e)
        return None, None, None
    if result:
        logger.debug('get_r_id_from_request _id:%s' % result.get('_id'))
        created_time = result.get('created_time')
        created_time_str = created_time.strftime('%Y-%m-%d %H:%M:%S')
        id = str(result.get('_id'))
        username = result.get('username')
        return id, username, created_time_str
    return None, None, None


def get_r_id_from_request_refresh(timestamp, status='FAILED'):
    """

    :param timestamp:the timestamp of now
    :param status: default FAILED
    :return:
    """
    try:
        # result = db.request.find_one_and_update({'failed_flag': {"$exists": False},
        #                 'executed_end_time_timestamp': {'$gte': timestamp, '$lt': timestamp + 180}, 'status': status},
        #                 {'$set': {'failed_flag': 1}})

        result = db.request.find_one_and_update({'failed_flag': {"$exists": False},
                        'executed_end_time_timestamp': {"$exists": False},
                        "created_time": {"$lte":datetime.fromtimestamp(timestamp - 180), "$gt": datetime.fromtimestamp(timestamp - 3600)}},
                        {'$set': {'failed_flag': 1}})
        logger.debug("get_r_id_from_request find data from request success")
    except Exception:
        logger.debug('get_r_id_from_request get data from request error:%s' % e)
        return None, None, None
    if result:
        logger.debug('get_r_id_from_request _id:%s' % result.get('_id'))
        created_time = result.get('created_time')
        created_time_str = created_time.strftime('%Y-%m-%d %H:%M:%S')
        id = str(result.get('_id'))
        username = result.get('username')
        return id, username, created_time_str
    return None, None, None


def get_r_id_from_request_refresh_last_hpcc(timestamp, status='FAILED'):
    """

    :param timestamp:the timestamp of now
    :param status: default FAILED
    :return:
    """
    try:
        # result = db.request.find_one_and_update({'failed_flag': {"$exists": False},
        #                 'executed_end_time_timestamp': {'$gte': timestamp, '$lt': timestamp + 180}, 'status': status},
        #                 {'$set': {'failed_flag': 1}})

        result = db.request.find_one_and_update({'last_hpcc_report_flag': {"$exists": False},
                        "created_time": {"$lte": datetime.fromtimestamp(timestamp - 240), "$gt": datetime.fromtimestamp(timestamp - 3600)}},
                        {'$set': {'last_hpcc_report_flag': 1}})
        logger.debug("get_r_id_from_request find data from request success")
    except Exception:
        logger.debug('get_r_id_from_request get data from request error:%s' % e)
        return None, None, None
    if result:
        logger.debug('get_r_id_from_request _id:%s' % result.get('_id'))
        created_time = result.get('created_time')
        created_time_str = created_time.strftime('%Y-%m-%d %H:%M:%S')
        id = str(result.get('_id'))
        username = result.get('username')
        return id, username, created_time_str
    return None, None, None


def start_end_time():
    """

    :return:
    """
    time_now = datetime.now()
    start_time = time_now - timedelta(days=1)
    return start_time, time_now




if __name__ == "__main__":
    url1 = combination_refresh_command_hpcc_dir('http://www.baidu.com/123.html')
    url4 = combination_refresh_command_hpcc_url('http://www.baidu.com/123.html')
    url2 = combination_refresh_command_fc_dir('http://www.baidu.com/123.html')
    url3 = combination_refresh_command_fc_url('http://www.baidu.com/123.html')
    print('url1:%s' % url1)
    print('url4 hpcc url:%s' % url4)
    print('url2:%s' % url2)
    print('url3:%s' % url3)
    pass
    # parse_data()
    # send(email_from, email_to, 'test', 'testname')