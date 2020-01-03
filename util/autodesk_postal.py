# -*- coding:utf-8 -*-
"""
Created on 2016-6-17

@author: rubin
"""
import os
# from xml.dom.minidom import parseString
# from pymongo import MongoClient


import asyncore, traceback, datetime, time

from .autodesk_asyncpostal import HttpClient
import logging
# try:
#     from pymongo import ReplicaSetConnection as MongoClient
# except:
#     from pymongo import MongoClient

from bson import ObjectId
from util.autodesk_parse_response_header import ParseHeader
from core.update import db_update
from core.database import db_session, query_db_session
db = query_db_session()
# conn = MongoClient('mongodb://bermuda:bermuda_refresh@223.202.52.135:27017/bermuda')
# db = conn.bermuda

# import core.redisfactory as redisfactory
# from  util.tools import get_active_devices
# from core import database

# connect 82 server
# con83 = MongoClient('mongodb://bermuda:bermuda_refresh@223.202.52.82:27018/bermuda')
# db = con83.bermuda

# db = database.query_db_session()

# redis_name_id = redisfactory.getDB(7)


LOG_FILENAME = '/Application/bermuda3/logs/autodesk.log'
# LOG_FILENAME = '/home/rubin/logs/autodesk_postal1_1.log'

# logging.basicConfig(filename=LOG_FILENAME,
#                     format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s',
#                     level=logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s")
fh = logging.FileHandler(LOG_FILENAME)
fh.setFormatter(formatter)

logger = logging.getLogger('autodesk_postal')
logger.addHandler(fh)
logger.setLevel(logging.DEBUG)


def doloop(devs, url, different_time, connect_timeout=0.5, response_timeout=0.5):
    """
     调用asyncore，创建信道，与FC 通过socket连接,端口21108
    :param devs:
    :param command:
    :return:
    """
    clients = []
    result = []
    my_map = {}
    port = 80
    for dev in devs:
        clients.append(HttpClient(dev.get('host'), dev, port, url, len(devs) * 200,\
                                    my_map, connect_timeout, response_timeout))
    print("loop start")
    logger.debug('LOOP STARTING.')
    # asyncore.loop(timeout=response_timeout, map=my_map)#select()或poll()调用设置超时，以秒为单位，默认为30秒
    asyncore.loop(timeout=0.1, use_poll=True, map=my_map)
    logger.debug('LOOP DONE.')
    print("loop end")
    have_body_list = []
    not_have_body_list = []
    all_list = []
    set_code = set()
    for c in clients:
        all_list.append(c.host)

        response_body = c.read_buffer.getvalue()
        logger.debug('host:%s' % c.host)
        logger.debug('resonse_code:%s' % c.response_code)
        logger.debug("resonse_body:%s" % response_body[:1000])
        print('host:%s' % c.host)
        print('response_code:%s' % c.response_code)
        print("resonse_body:%s" % response_body[:1000])

        # code = 600
        if response_body:
            auto_body = ParseHeader(response_body, different_time)
            http_code = auto_body.get_code()
            logger.debug('host:%s, auto_body.get_dict:%s' % (c.host, auto_body.get_dict()))
            http_age =  auto_body.get_age()
            http_cc_cache = auto_body.get_cc_cache()
            http_refresh_result = auto_body.refresh_result()
            c.dev['http_code'] = http_code
            c.dev['age'] = http_age
            c.dev['http_cc_cache'] = http_cc_cache
            c.dev['http_refresh_result'] = http_refresh_result

            have_body_list.append(c.host)
            code = response_body.split(' ')[1]
            logger.debug('code:%s' % code)
            # print code
            set_code.add(code)
            result.append(c.host + '\r\n%s\r\n%s' % (c.response_code, code))
            logger.debug('autodes_postal doloop last device content:%s' % c.dev)
    not_have_body_list = list(set(all_list) ^ set(have_body_list))
    logger.debug('not_have_body_list,len:%s,content:%s' % (len(not_have_body_list), not_have_body_list))
    logger.debug('result, len:%s, content:%s' % (len(result), result))
    logger.debug('code list:%s' % set_code)
    # print 'not_have_body_list,len:%s,content:%s' % (len(not_have_body_list), not_have_body_list)
    # print 'result, len:%s, content:%s' % (len(result), result)
    # print 'code list:%s' % set_code
    return result


def entrance(url_result, different_time):
    """

    :param url_result: the result of url
    :param different_time:
    :return:
    """
    url = url_result.get('url')
    id = url_result.get('_id')
    logger.debug('autodesk_postal entrance id:%s' % id)

    devices = db.device.find_one({'_id': url_result.get('dev_id')}).get('devices')
    logger.debug('autodesk_postal entrance devices:%s' % devices)
    if devices:
        result = doloop(list(devices.values()), url, different_time)
    insert_content = {}
    insert_content['devices'] = devices
    insert_content['created_time'] = datetime.datetime.now()
    insert_content['created_time_timestamp'] = time.mktime(insert_content['created_time'].timetuple())
    logger.debug('entrance insert_content:%s' % insert_content)
    try:
        insert_result = db.device_autodesk.insert_one(insert_content)
        logger.debug('autodesk_postal insert_result id :%s' % (insert_result.inserted_id))
        db_update(db.url_autodesk, {'_id': ObjectId(id)}, {'$set': {'dev_id_autodesk': insert_result.inserted_id}})
        logger.debug('insert device_autodesk and update dev_autodesk success! insert_result:%s' % insert_result)
    except Exception:
        logger.debug('insert device_autodesk and udpate dev_autodesk error:%s' % traceback.format_exc())


def test_entrance():
    """

    :return:
    """
    devices = db.device.find_one({'_id': ObjectId('58197eb82b8a6838f5f03447')}).get('devices')
    url = 'http://www.gamersky.com/review/201610/827156.shtml'
    if devices:
        result = doloop(list(devices.values()), url, 300)

if __name__ == "__main__":
    test_entrance()
    os._exit(0)
















