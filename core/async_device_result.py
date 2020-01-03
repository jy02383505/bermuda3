#!/usr/bin/env python
# coding=utf-8
# Created by vance on 2016-06-20.

__author__ = 'vance'

from celery.task import task
from util import log_utils
from core import database
import datetime , time
import copy, traceback, redis
# from bson.objectid import ObjectId
from core.generate_id import ObjectId
from core.rcmsapi import get_channelname_from_url
from core.models import MONITOR_DEVICE_STATUS, MONITOR_DEVICE_STATUS_FAILED
from util.tools import get_current_date_str
from core import redisfactory
from pymongo.errors import BulkWriteError
from .config import config
# from core import generate_id
#db = database.db_session()

db = database.s1_db_session()
logger = log_utils.get_celery_Logger()
CACHERECORD = redisfactory.getMDB(7)

@task(ignore_result=True, default_retry_delay=10, max_retries=3)
def async_devices(devs,urls, url_status):
    ''' {
        "CHN-BZ-2-3H2" : {
            "status" : "OPEN",
            "code" : 200,
            "name" : "CHN-BZ-2-3H2",
            "total_cost" : "0.25",
            "connect_cost" : "0.23",
            "serialNumber" : "01054323H2",
            "host" : "222.174.239.172",
            "response_cost" : "0.02",
            "firstLayer" : false,
            "port" : 21108
        },
        "CHN-BZ-2-3H1" : {
            "status" : "OPEN",
            "code" : 200,
            "name" : "CHN-BZ-2-3H1",
            "total_cost" : "0.28",
            "connect_cost" : "0.23",
            "serialNumber" : "01054323H1",
            "host" : "222.174.239.171",
            "response_cost" : "0.05",
            "firstLayer" : false,
            "port" : 21108
        }
    }
    device_urls_day:
    {
    "_id" : ObjectId("555993f71d41c82ebccd7360"),
    "date" : ISODate("2015-05-18T00:00:00.000Z"),
    "firstL" : false,
    "host" : "122.228.87.18",
    "hostname" : "CHN-LN-a-3SE",
    "urls" : [
        {
            "username" : "cqnews",
            "dev_id" : ObjectId("55598df316cfb2060a27343e"),
            "code" : "200",
            "uid" : ObjectId("55598deb2489db2a80541a16"),
            "url" : "http://www.cqnews.net/",
            "status" : "FINISHED",
            "created_time" : ISODate("2015-05-18T14:59:55.703Z"),
            "channel_code" : "10833"
        }
    }
    device_result:
    {
    "_id" : ObjectId("55384dcd78ecdf77a207191e"),
    "created_time" : ISODate("2015-04-23T09:41:33.731Z"),
    "finish_time" : ISODate("2015-04-23T09:41:33.854Z"),
    "devices" : [
        {
            "status" : "OPEN",
            "r_cost" : 0,
            "code" : 200,
            "name" : "CMN-HB-1-3SI",
            "total_cost" : "0.06",
            "connect_cost" : "0.03",
            "a_code" : 200,
            "r_code" : 200,
            "host" : "218.203.13.189",
            "response_cost" : "0.03",
            "firstLayer" : false
        }
    }
'''

    logger.info("async_devices start")
    urls_day = {}
    url_list = []
    # device_result = {}
    dev=[]
    dev_map_list = []
    monitor_map = {i:{} for i in MONITOR_DEVICE_STATUS}
    logger.debug('monitor_map is %s' %(monitor_map))
    # device_result["created_time"]=devs.get("created_time")
    # device_result["finish_time"]=devs.get("finish_time")
    devices = devs.get("devices")
    for key,value in list(devices.items()):
        #logger.debug('##code is %s type is %s'%(value["code"], type(value["code"])))
        if value['code'] in monitor_map:
            monitor_map[value['code']].setdefault(value['name'], 0)
            monitor_map[value['code']][value['name']] += len(urls)
        if value['code'] == 200:
            continue
        dev.append(value)
        is_firstLayer = value['firstLayer']
        for url in urls:
            username = url.get("username")
            if username != 'vipshop':
                if not is_firstLayer:
                    continue
            uu = {}
            dev_map = {}
            dev_map["_id"] = ObjectId()
            dev_map["firstL"] = value["firstLayer"]
            dev_map["host"] = value["host"]
            dev_map["hostname"] = value["name"]
            dev_map["datetime"] = datetime.datetime.now()
            uu["uid"] = url.get("id")
            uu["username"] = url.get("username")
            uu["dev_id"] = url.get("dev_id")
            uu["code"] = value["code"]
            uu["url"] = url.get("url")
            uu["status"] = url_status.get(url.get("id"))
            uu["channel_code"] = url.get("hannel_code")
            uu["channel_name"] = get_channelname_from_url(url.get("url"))
            uu["action"] = url.get("action")
            uu["isdir"] = url.get("isdir")
            # url_list.append(uu)
            dev_map["url"] = uu
            #dev_map["set_key"] = {'url':url.get("url"),'action':url.get("action"),'isdir':url.get("isdir")}
            #db.device_urls_day.insert(dev_map)
            dev_map_list.append(dev_map)

    # to save mongo
    #logger.debug('monitor_map last is %s' %(monitor_map))
    try:
        logger.debug('dev_map_list is %s' %(len(dev_map_list)))
        if dev_map_list:
            db.device_urls_day.insert_many(dev_map_list)
            logger.debug('dev_map_list insert ok')
    except BulkWriteError as bwe:
        #logger.error(traceback.format_exc())
        logger.error(bwe.details)

    # to monitor save
    if monitor_map:
        update_device_count(monitor_map)

    # device_result["devices"] = dev
    # db.device_result.insert(device_result)
    logger.info("async_devices end")


def update_device_count(monitor_map):
    '''
    对设备相应code记数量
    {
      200:{'hostname': 2}
      503: xxxxx
    }

    '''
    try:
        day_key = get_current_date_str()
        r_failed_sort_key = "%s_failed" %(day_key)
        r_failed_sort_first_key = "%s_failed_first" %(day_key)
        expire_seconds = 24*3600*15

        for _code , _info in list(monitor_map.items()):
            r_key = '%s_%s' %(day_key, _code)
            r_first_key = '%s_%s_first' %(day_key, _code)
            for _hostname, _count in list(_info.items()):
                CACHERECORD.hincrby(r_key, _hostname, _count)
                if CACHERECORD.setnx(r_first_key, int(time.time())):
                    #第一次
                    CACHERECORD.expire(r_key,expire_seconds)
                    CACHERECORD.expire(r_first_key, expire_seconds+2)
                if _code in MONITOR_DEVICE_STATUS_FAILED:
                    #失败排序计数
                    CACHERECORD.zincrby(r_failed_sort_key, _hostname, _count)
                else:
                    CACHERECORD.zincrby(r_failed_sort_key, _hostname, 0)

                if CACHERECORD.setnx(r_failed_sort_first_key, int(time.time())):
                    #第一次失败排序
                    CACHERECORD.expire(r_failed_sort_key,expire_seconds)
                    CACHERECORD.expire(r_failed_sort_first_key, expire_seconds+2)
    except Exception:
        logger.error(traceback.format_exc())

