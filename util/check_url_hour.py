#!/usr/bin/env python
# coding=utf-8
# Created by vance on 2015-02-27.
import copy

__author__ = 'vance'
__doc__ = """统计用户的失败任务及设备列表"""
__ver__ = '1.0'

import datetime

try:
    from pymongo import ReplicaSetConnection as MongoClient, Connection
except:
    from pymongo import MongoClient as MongoClient
import logging
import traceback
# from core import database
import sys
import os
import threading
from multiprocessing import Process
from multiprocessing import Pool
from multiprocessing.dummy import Pool as ThreadPool
import redis
from queue import Queue
# from collections import Counter

LOG_FILENAME = '/Application/bermuda3/logs/check_url_day.log'
logging.basicConfig(filename=LOG_FILENAME,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger('check_url_day')
logger.setLevel(logging.DEBUG)

# conn = database.db_session()
# conn_url = MongoClient('%s:27017,%s:27017,%s:27017' % ('172.16.12.136', '172.16.12.135', '172.16.12.134'),
#                        replicaSet='bermuda_db')['bermuda']
uri ='mongodb://bermuda:bermuda_refresh@%s:27017,%s:27017,%s:27017/bermuda?replicaSet=bermuda_db' % ('172.16.12.136', '172.16.12.135', '172.16.12.134')
conn_url = MongoClient(uri)['bermuda']
# # conn = ReplicaSetConnection('%s:27017,%s:27017,%s:27017' % ('172.16.12.136', '172.16.12.135', '172.16.12.134'), replicaSet ='bermuda_db')['bermuda']
try:
    uri = 'mongodb://bermuda:bermuda_refresh@%s:27017/bermuda' %('172.16.21.205')
    # conn_target = MongoClient("172.16.21.205", 27017)['bermuda']
    conn_target = MongoClient(uri)['bermuda']
except:
    # conn_target = Connection("172.16.21.205", 27017)['bermuda']
    conn_target = Connection(uri)['bermuda']
# # conn = MongoClient("223.202.52.134", 27017)['bermuda']
# conn_target = MongoClient("223.202.52.82", 27017)['bermuda']

# pool = redis.ConnectionPool(host='%s'%'172.16.21.205', port=6379, db=9)
# REDIS_CLIENT = redis.Redis(connection_pool=pool)
REDIS_CLIENT = redis.StrictRedis(host='%s' % '172.16.21.205', port=6379, db=9, password= 'bermuda_refresh')
DAY_KEY = "%s_%s"
count = 0
queue = Queue()

"""TTL: db.ref_err_day.ensureIndex( { "datetime": -1 }, { expireAfterSeconds: 60*60*24*7 })
        db.ref_err_day.ensureIndex({"uid":1 },{"unique":true})
        db.ref_err_day.ensureIndex({"channel_code":1})
        db.ref_err_day.ensureIndex({"devices.code":1})
        db.ref_err_day.ensureIndex({"username":1})
    """


def get_fail_url_device(collection_dev, dev_id):
    # self.collection_dev = self.connect['device']
    dev_obj = collection_dev.find_one({"_id": dev_id}, {"devices": 1})
    curdate = datetime.datetime.now() - datetime.timedelta(hours=1)
    datestr = curdate.strftime('%Y%m%d')
    devs_list = []
    for dev in dev_obj['devices']:
        d_dic = {}
        code = str(dev_obj['devices'][dev]['code'])
        name = dev_obj['devices'][dev]['name']
        firstL = dev_obj['devices'][dev]['firstLayer']
        host = dev_obj['devices'][dev]['host']

        d_dic['hostname'] = name
        d_dic['ip'] = host
        d_dic['code'] = code
        d_dic['firstLayer'] = firstL

        a_code = str(dev_obj['devices'][dev].get('a_code', 0))
        r_code = str(dev_obj['devices'][dev].get('r_code', 0))
        d_dic['a_code'] = a_code
        d_dic['r_code'] = r_code

        devs_list.append(d_dic)

        code_key = DAY_KEY % (datestr, name)
        if code in ['503']:
            REDIS_CLIENT.hincrby(code_key, r_code)
            REDIS_CLIENT.expire(code_key, 259200)
        else:
            REDIS_CLIENT.hincrby(code_key, code)

            REDIS_CLIENT.expire(code_key, 259200)

    return devs_list


def get_urls(process_date):
    cur_time = datetime.datetime.combine(process_date.date(), datetime.time())
    # # pre_time = pre_time + datetime.timedelta(hours=h)
    cur_time = cur_time + datetime.timedelta(hours=process_date.hour)
    # cur_time = process_date

    # # # #00:00-00:15
    end_time = cur_time - datetime.timedelta(minutes=45)
    pre_time = cur_time - datetime.timedelta(hours=1)

    # #00:15-01:00
    # end_time = cur_time
    # pre_time = cur_time - datetime.timedelta(minutes=45)

    logger.debug("{0}-{1}".format(pre_time, end_time))
    print(pre_time, end_time)
    find_url_dic = {"created_time": {"$gte": pre_time, "$lt": end_time},
                    "status": {"$ne": "INVALID"}}
    field_dic = {"username": 1, "_id": 1,
                 "dev_id": 1, "channel_code": 1, "parent": 1, "url": 1, "status": 1,
                 "created_time": 1}

    try:
        collection_url = conn_url['url']
    except Exception:
        logger.error(traceback.format_exc())

    return collection_url.find(find_url_dic, field_dic, no_cursor_timeout=True)


def insert_refresh(data):
    global count
    try:
        collection_err = conn_target['ref_err_day']
    except Exception:
        logger.error(traceback.format_exc())
    # logger.debug('process {0}'.format(data['uid']))
    # self.collection_err.insert(data)
    result = collection_err.insert(data)
    count += 1
    logger.debug('process {0}-{1} end'.format(data['uid'], count))
    # self.collection_err.update(data, {'$set': {'salary' : 10000}}, upsert=True, multi=True)


def process_url(url):
    uid = url.get("_id")
    u_dic = {}
    u_dic['username'] = url.get("parent")  # 取主账户
    u_dic['uid'] = uid
    u_dic['channel_code'] = url.get("channel_code")
    u_dic['datetime'] = url.get("created_time")
    u_dic['dev_id'] = url.get("dev_id")
    u_dic['url'] = url.get("url")
    u_dic['status'] = url.get("status")
    try:
        if not url.get("dev_id", None):
            logger.error('devid is None: %s' % (uid))
            return
        u_dic['devices'] = get_fail_url_device(conn_url['device'], url.get("dev_id"))
    except Exception:
        logger.error('run error: %s' % traceback.format_exc())
        logger.error('run error devid: %s %s' % (url.get("dev_id"), uid))
    insert_refresh(u_dic)


def run(process_date):
    thread_list = []
    plist = []
    now = datetime.datetime.now()
    #########################
    pool = ThreadPool(100)
    # # Open the urls in their own threads
    # # and return the results
    url_obj = get_urls(process_date)
    print(url_obj.count())
    logger.debug('start map thread pool %s' % url_obj.count())
    # h_list = [i for i in range(24)]
    results = pool.map(process_url, url_obj)
    # #close the pool and wait for the work to finish
    pool.close()
    pool.join()
    logger.debug('map threaad end')

    end_time = datetime.datetime.now()
    end_str = 'finish script on {datetime}, use {time}'.format(datetime=end_time, time=end_time - now)
    print(end_str)
    logger.info(end_str)
    os._exit(0)


if __name__ == '__main__':
    now = datetime.datetime.now()
    start_str = 'start script on {datetime}'.format(datetime=now)
    logger.info(start_str)
    print(start_str)
    run(now)
