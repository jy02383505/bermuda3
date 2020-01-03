#!/usr/bin/env python
# -*- coding:utf-8 -*-
'''
Created on 2016-3-17

@author: rubin
完成的目标：修改系统中预加载任务中，超过两个小时　　预加载任务的状态仍为progress   把其状态修改为failed
@modify time  2016/6/21
'''

import datetime
from core.preload_worker import set_finished
from util import log_utils
import simplejson as json
from core import redisfactory, database
import os
from core.models import PRELOAD_STATUS_NOT_REPORT

# 链接mongo 句柄
db = database.s1_db_session()
# 链接redis句柄
PRELOAD_CACHE = redisfactory.getDB(1)
logger = log_utils.get_pcelery_Logger()


def get_preload_url_info():
    """
    从preload_url 表中获得状态(status)为  PROGRESS, create_time　before two hours
    修改相应的预加载信息，使其status 变为FAILED
    """
    # greater than yesterday's start time  less than the current time of two hours
    now = datetime.datetime.now()
    yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
    yesterday_begin = datetime.datetime.combine(yesterday, datetime.time())
    # print yesterday_begin
#    result = db.preload_url.find({"status": "PROGRESS", "created_time": {"$lt": (datetime.datetime.now() - datetime.timedelta(hours=2)),
#                                                                         "$gt": yesterday_begin}})

    result = db.preload_url.find({"status": "PROGRESS", "created_time": {"$lte": now - datetime.timedelta(hours=1), "$gte": now - datetime.timedelta(hours=2)}})

    #test
    #result = db.preload_url.find({"status": "PROGRESS", "username": "msft-novacdn"})

    for pre in result:
        # 修改数据库中的状态
        # db.test_rubin.update({"_id":pre["_id"]}, {"$set": {"status": "FAILED"}})
        handle_progress(pre["_id"])
        logger.debug("pre['id'] content:%s" % pre["_id"])


def handle_progress(url_id):
    """
    url_id 为preload_url中的_id
    :param url_id:
    :return:
    """
    cache_body = PRELOAD_CACHE.get(url_id)
    if cache_body:
        try:
            cache_body = json.loads(cache_body)
        except Exception:
            logger.debug("parse cache_body error:%s" % cache_body)
            return
        handle_error_task_update(url_id, cache_body)
        logger.debug("execute handle_error_task_update")
    else:
        logger.debug("in the redis, the catche_body of url_id is null")


def handle_error_task_update(url_id, cache_body):
    """
    根据preload_url中，status 为progress的内容进行更新　使其变为状态为failed
    :param url_id:
    :param cache_body:
    :return:
    """
    dev_dict = cache_body.get('devices', None)
    if not dev_dict:
        return
    #暂时不修改 dev status
    finished_count = 0
    for dev in list(dev_dict.values()):
        if dev.get("preload_status", 0) == 200:
            finished_count += 1
   # for dev in dev_dict.values():
   #     if dev.get("preload_status", 0) == 0:
   #         # preload_status initial value is 0, if not receive the information from the edge of the device
   #         # to report the change, set value 504
   #         dev["preload_status"] = PRELOAD_STATUS_NOT_REPORT
    # 更新redis　中的内容
    #PRELOAD_CACHE.set(url_id, json.dumps(cache_body))
    logger.debug("handle_error_task reset cache status FAILED  finished url_id: %s:" % url_id)
    # 修改数据库中信息
    if finished_count/float(len(dev_dict)) > 0.5:
        set_finished(url_id, cache_body, 'FINISHED')
    else:
        set_finished(url_id, cache_body, 'FAILED')

if __name__ == "__main__":
    get_preload_url_info()
    os._exit(0)
