#!/usr/bin/env python
# -*- coding:utf-8 -*-

# put this script into project bermuda.
# if table.field 'preload_dev._id' == 'preload_url.dev_id' means the task sending code is 200.
# After that you can maually call receiver/preload_worker_new.py:
# save_fc_report(report_body) to change the status into 'PROGRESS'

from pymongo import MongoClient
from bson.objectid import ObjectId
from core.preload_worker_new import set_finished
import datetime
import time
import json
from sys import exit
import traceback
import re
from core import redisfactory, database
from core import preload_worker_new, rcmsapi

# 链接mongo 句柄
db = database.s1_db_session()
PRELOAD_CACHE = redisfactory.getDB(1)
# logger = log_utils.get_pcelery_Logger() # print is ok


def get_preload_urls(username='zyhq'):
# def get_preload_urls(username='zyhq', offset_start=60 * 35, offset_end=60 * 30):
    """
    从preload_url 表中获得状态(status)为  PROGRESS, create_time　before 10 minutes
    修改相应的预加载信息，使其status 变为FINISHED
    以上两部分的两个条件均满足之后，直接调用set_finished
    """
    # try:
    print('\n-----begin...-----\n')
    the_begin_date = time.strptime('2017-07-16 19:00:00', '%Y-%m-%d %H:%M:%S')
    the_begin_date_stamp = time.mktime(the_begin_date)
    the_end_date = time.strptime('2017-07-16 20:00:00', '%Y-%m-%d %H:%M:%S')
    the_end_date_stamp = time.mktime(the_end_date)
    # print '\n-----thedate_stamp-----\n', thedate_stamp

    # preload_urls = db.preload_url.find({"status": "PROGRESS", "username": username, "created_time_timestamp": {
    #     "$gt": (thedate_stamp - offset_seconds)}}).limit(1) # cut off the limit
    # preload_urls = db.preload_url.find({"status": "PROGRESS", "username": username, "created_time_timestamp": {
    #     "$gte": the_begin_date_stamp, '$lte': the_end_date_stamp}, 'url': re.compile('.*\.mxf')})
    preload_urls = db.preload_url.find({"status": "PROGRESS", "username": username, "created_time_timestamp": {
        "$gte": the_begin_date_stamp, '$lte': the_end_date_stamp}})
        # "$gte": (time.time() - offset_start), '$lte': (time.time() - offset_end)}})
    print('\n-----preload_urls.count()-----\n', preload_urls.count())
    if not preload_urls.count():
        print('\n-----There is no suitable colletion found.-----\n')
        exit()
    for preload_url in preload_urls:
        status_progress2finished(preload_url)
    return preload_urls
    # except Exception, e:
    #     print "status_progress2finished get_preload_urls:%s" % traceback.format_exc()
    #     return


def status_progress2finished(preload_url):
    """    
    process one url
    """
    # test
    #result = db.preload_url.find({"status": "PROGRESS", "username": "msft-novacdn"})

    # dev_list = set()
    # dispatch part
    dispatch_success = is_dispatch_success(preload_url)
    print("status_progress2finished dispatch_success:%s" % dispatch_success)

    report_success = is_report_success(preload_url)
    url_id = str(preload_url['_id'])  # for redis
    cache_body = PRELOAD_CACHE.get(url_id)
    print('\n-----url_id-----\n', url_id)
    print('\n-----cache_body-----\n', cache_body)
    if cache_body:
        cache_body = json.loads(cache_body)
    print("status_progress2finished report_success:%s" % report_success)
    print('\n-----cache_body-----\n', cache_body)
    if dispatch_success and report_success:
        set_finished(url_id, cache_body, 'FINISHED')
    else:
        set_finished(url_id, cache_body, 'FAILED')


def is_dispatch_success(preload_url, onlyFirst=True):
    """    
    下发部分
     200 和 501的status就认为是下发成功了
    条件一：下发部分全部成功
    onlyFirst {True: 只考虑上层, False: 除了上层还要考虑下层}
    """
    return True
    # try:
    # 修改数据库中的状态
    # db.test_rubin.update({"_id":pre["_id"]}, {"$set": {"status": "FAILED"}})
    # the number of dev which receive successfully.
    dev_success_count_first = 0
    first_dev_count = 0
    # the number of dev which receive successfully.
    dev_success_count_not_first = 0
    dev_count = 0  # the total number of dev
    preload_dev = db.preload_dev.find_one(
        {'_id': ObjectId(preload_url['dev_id'])})
    print('\n-----preload_dev-----\n', preload_dev)
    # exit()
    for dev in list(preload_dev['devices'].values()):
        # dev_list.add(dev)
        dev_count += 1
        if dev['firstLayer'] in ['true', 'True', True]:
            first_dev_count += 1
        if dev['firstLayer'] in ['true', 'True', True] and (dev['code'] in [501, 200, '501', '200']):
            dev_success_count_first += 1
        elif dev['firstLayer'] in ['false', 'False', False] and (dev['code'] in [501, 200, '501', '200']):
            dev_success_count_not_first += 1
            onlyFirst = False
        else:
            pass
    if onlyFirst:
        print('\n-----dev_success_count_first-----\n', dev_success_count_first)
        print('\n-----dev_count-----\n', dev_count)
        # exit()
        if dev_success_count_first / float(dev_count) >= 0.8:
        # if dev_success_count_first == dev_count:
            return True
        return False
    else:
        print('\n-----dev_count-----\n', dev_count)
        if not dev_count:
            return False
        # if (dev_success_count_first + dev_success_count_not_first) / float(dev_count) >= 0.5:
        if dev_success_count_first == first_dev_count:
            return True
        return False
    # except Exception:
    #     print "status_progress2finished is_dispatch_success:%s" % traceback.format_exc()
    #     return False


def is_report_success(preload_url):
    """
    汇报部分
    条件二：
     上层汇报完成80%
     下层汇报完成50%
    """
    # try:
    return True

    url_id = str(preload_url['_id'])  # for redis
    cache_body = PRELOAD_CACHE.get(url_id)
    if cache_body:
        cache_body = json.loads(cache_body)
    print('\n-----cache_body-----\n', cache_body)
    _, dev_cache = preload_worker_new.get_preload_dev_cache(url_id, cache_body)

    total = 0
    first_layer_count = 0
    un_first_layer_count = 0
    first_success_count = 0
    un_first_success_count = 0
    for dev in list(dev_cache.values()):
        if dev['firstLayer'] in [True, 'true', 'True']:
            first_layer_count += 1
            if dev.get('preload_status') in [200]:
                first_success_count += 1
        else:
            un_first_layer_count += 1
            if dev.get('preload_status') in [200]:
                un_first_success_count += 1

    # first: must; un_first: maybe
    is_all_layer = False
    if un_first_layer_count:
        is_all_layer = True

    print('\n-----first_layer_count-----\n', first_layer_count)
    print('\n-----un_first_layer_count-----\n', un_first_layer_count)
    # if not first_layer_count or not un_first_layer_count:
    #     return False
    if is_all_layer:
        if un_first_success_count / float(un_first_layer_count) >= 0.5:
        # if (first_success_count / float(first_layer_count) >= 0.8) and (un_first_success_count / float(un_first_layer_count) >= 0.5):
            return True
    else:
        print('\n-----only first-----\n')
        print('\n-----first_success_count-----\n', first_success_count)
        if (first_success_count / float(first_layer_count) >= 0.5):
            global report_success_count
            report_success_count += 1
            return True
    return False
    # except Exception:
    #     print "status_progress2finished is_report_success:%s" % traceback.format_exc()
    #     return False


if __name__ == "__main__":
    print(time.strftime('%Y-%m-%d %H:%M:%S'))
    username = 'zyhq'
    # report_success_count = 0
    # offset_start = 60 * 35
    # offset_end = 60 * 30
    get_preload_urls(username)
    # print '\n-----report_success_count-----\n', report_success_count
    # get_preload_urls(username, offset_start, offset_end)
    print('---over---')
