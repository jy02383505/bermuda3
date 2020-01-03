# -*- coding:utf-8 -*-
"""
Created on 2016-6-17

@author: rubin
"""
import os
from xml.dom.minidom import parseString
# from pymongo import MongoClient


import uuid, asyncore, traceback, datetime, time

from .asyncpostal_r import HttpClient_r
import logging
import core.redisfactory as redisfactory
from  util.tools import get_active_devices
from core import database

# connect 82 server
# con83 = MongoClient('mongodb://bermuda:bermuda_refresh@223.202.52.82:27018/bermuda')
# db = con83.bermuda

db = database.query_db_session()

redis_name_id = redisfactory.getDB(7)


LOG_FILENAME = '/Application/bermuda3/logs/postal_r.log'
# LOG_FILENAME = '/home/rubin/logs/rubin_postal.log'

# logging.basicConfig(filename=LOG_FILENAME,
#                     format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s',
#                     level=logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s")
fh = logging.FileHandler(LOG_FILENAME)
fh.setFormatter(formatter)

logger = logging.getLogger('postal_r')
logger.addHandler(fh)
logger.setLevel(logging.DEBUG)


def doloop(devs, command, connect_timeout=2, response_timeout=2):
    """
     调用asyncore，创建信道，与FC 通过socket连接,端口21108
    :param devs:
    :param command:
    :return:
    """
    clients = []
    result = []
    my_map = {}
    port = 21108
    for dev in devs:
        clients.append(HttpClient_r(dev.get('name'), dev.get('host'), dev.get('provinceName'), dev.get('ispName'), port, command, len(devs) * 200,\
                                    my_map, connect_timeout, response_timeout))
    print("loop start")
    logger.debug('LOOP STARTING.')
    # asyncore.loop(timeout=response_timeout, map=my_map)#select()或poll()调用设置超时，以秒为单位，默认为30秒
    asyncore.loop(timeout=0.1, use_poll=True, map=my_map)
    logger.debug('LOOP DONE.')
    print("loop end")
    for c in clients:
        # dev_name the name of device,  response_body response content from dev
        # total_cost connect start to end cost,
        dev_name, response_body, total_cost, connect_cost, response_cost, response_code, provinceName, ispName = c.dev_name, \
                            c.read_buffer.getvalue(), c.total_cost, c.connect_cost, c.response_cost, c.response_code,\
                                                                                          c.provinceName, c.ispName

        result.append(c.dev_name + '\r\n%s\r\n%d\r\n%.2f\r\n%.2f\r\n%.2f\r\n%s\r\n%s' % (c.host, response_code, total_cost, \
                                                connect_cost, response_cost, provinceName, ispName))
    return result


def getUrlCommand(url):
    """
    按接口格式，格式化url
    :param urls:
    :return:
    """
    sid = uuid.uuid1().hex
    # content = parseString('<method name="url_expire" sessionid="%s"><recursion>0</recursion></method>' % sid)
    # if urls[0].get('action') == 'purge':
    #     content = parseString('<method name="url_purge" sessionid="%s"><recursion>0</recursion></method>' % sid)
    content = parseString('<method name="url_purge" sessionid="%s"><recursion>0</recursion></method>' % sid)
    url_list = parseString('<url_list></url_list>')
    tmp = {}
    logger.debug('urls information')
    qurl = url.get("url").lower() if url.get('ignore_case', False) else url.get("url")
    uelement = content.createElement('url')
    uelement.setAttribute('id', url.get("id", str(0))) #store url.id  in id
    logger.debug('send url.id:%s' % url.get("id"))
    uelement.appendChild(content.createTextNode(qurl))
    url_list.documentElement.appendChild(uelement)
    content.documentElement.appendChild(url_list.documentElement)
    return content.toxml('utf-8')


def get_device_info_from_redis(arr, redis_db):
    """

    :param arr: list of device name
    :param redis_db: key is hostname, value is host ip
    :return:
    """
    result_list = []
    if not arr:
        return result_list
    else:
        for dev_name in arr:
            logger.debug('dev_name:%s, type:%s' % (dev_name, type(dev_name)))
            dev_temp = {}
            dev_temp['name'] = dev_name
            if redis_db.exists(dev_name):
                logger.debug('dev_name:%s at redis 7' % dev_name)
                ip_provicenName = redis_db.get(dev_name)
                arr_temp = ip_provicenName.split(',')
                dev_temp['host'] = arr_temp[0]
                dev_temp['provinceName'] = arr_temp[1]
                dev_temp['ispName'] = arr_temp[2]
                result_list.append(dev_temp)
            else:
                try:
                    dev_info = db.device_app.find_one({'name':dev_name})
                except Exception:
                    logger.debug("get_device_info_from_redis query error:%s" % e)
                    continue
                if dev_info:
                    ip = dev_info.get('host', '--')
                    provinceName = dev_info.get('provinceName', '--')
                    ispName = dev_info.get('ispName', '--')
                    ip_provicenName = ip + ',' + provinceName + ',' + ispName
                    logger.debug('name:%s, ip_provinceName:%s' % (dev_name, ip_provicenName))
                    redis_db.set(dev_name, ip_provicenName)
                    dev_temp['host'] = ip
                    dev_temp['provinceName'] = provinceName
                    dev_temp['ispName'] = ispName
                    result_list.append(dev_temp)
                else:
                    logger.debug('dev_info is null')
                    continue
        return result_list

#
# def remove_dup(devices):
#     """
#      remove duplicate information, now we think that the device name is globally unique,
#      and that the host is one to one relationship
#     :param devices: [{host:xxx, name:xxx}, {host:xxxx, name:xxx}]
#     :return: [{name:xxx, host:xxx}, {name:xxx, host:xxx}]
#     """
#     result = {}
#     device_remove_dup = []
#     if devices:
#         for dev in devices:
#             hostname = dev.get('hostname', None)
#             host = dev.get('host', None)
#             if not hostname or not host:
#                 continue
#             result[hostname] = host
#     # re assembly equipment information
#     if result:
#         for key, value in result.items():
#             dev_tem = {}
#             dev_tem['name'] = key
#             dev_tem['host'] = value
#             device_remove_dup.append(dev_tem)
#     return device_remove_dup


def get_date_time():
    """
    record the current time
    :return: the current date  and current time
    """
    current_time =  datetime.datetime.now()
    current_date = datetime.datetime.combine(current_time, datetime.time())
    current_date = current_date.date().strftime('%Y-%m-%d')
    # formatting the time, precise to minutes
    current_time_str = current_time.strftime("%Y-%m-%d %H:%M")
    current_time_minutes = datetime.datetime.strptime(current_time_str, "%Y-%m-%d %H:%M")
    logger.debug("postal_r get_data_time current_time_minutes:%s" % current_time_minutes)
    return current_time_minutes, current_date


def parse_result(res):
    """
    parse string, split the str use '\r\n'
    :param res: str
    :return:
    """
    result = {}
    try:
        dev_name, host, code, total_cost, connect_cost, response_cost, provinceName, ispName= res.split('\r\n')
    except Exception:
        logger.debug("parse_result error:%s" % e)
        return result
    result['name'] = dev_name
    result['ip'] = host
    result['code'] = code
    result['total_cost'] = total_cost
    result['connect_cost'] = connect_cost
    result['response_cost'] = response_cost
    result['provinceName'] = provinceName
    result['ispName'] = ispName
    return result


def link_entrance():
    """
    get data from mongo, send teh appropriate message to the destination host port
    :return:
    """
    arr_name = get_active_devices()
    logger.debug("link_entrance arr_name:%s" % arr_name)

    devices_no_dup = get_device_info_from_redis(arr_name, redis_name_id)
    result =doloop(devices_no_dup, getUrlCommand({"url": "http://www.test.com", "id": '123'}))
    # doloop(devices, "")
    devices = []
    if result:
        # get detect_date  detect_time
        detect_time, detect_date = get_date_time()
        logger.debug("postal_r detect_time:%s, detect_date:%s" % (detect_time, detect_date))
        for res in result:
            devices.append(parse_result(res))
    # packing final result
    result_r = {}
    result_r["detect_time"] = detect_time
    result_r["detect_date"] = detect_date
    result_r["devices"] = devices
    # insert result into mongo
    try:
        db.device_link.insert(result_r)
    except Exception:
        logger.debug(" insert data into mongo error:%s" % e)


if __name__ == "__main__":
    link_entrance()
    os._exit(0)
















