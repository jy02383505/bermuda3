#! -*- coding=utf-8 -*-
"""
@version: ??
@author: rubin
@license:
@contact: longjun.zhao@chinacache.com
@site: 
@software: PyCharm
@file: preload_url_timer_task_commit.py
@time: 16-10-12 上午9:22
"""
from celery.task import task
from datetime import datetime, timedelta
from core import database
import logging
from core import redisfactory
from util.tools import datetime_convert_timestamp
import traceback
from core.generate_id import ObjectId
import time
from core import preload_worker_new
from hashlib import md5
import json


LOG_FILENAME = '/Application/bermuda3/logs/preload_url_timer.log'
# LOG_FILENAME = '/home/rubin/logs/rubin_postal.log'

# logging.basicConfig(filename=LOG_FILENAME,
#                     format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s',
#                     level=logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s")
fh = logging.FileHandler(LOG_FILENAME)
fh.setFormatter(formatter)

logger = logging.getLogger('preload_url_timer')
logger.addHandler(fh)
logger.setLevel(logging.DEBUG)
db_s1 = database.s1_db_session()
PACKAGE_SIZE = 50

@task(ignore_result=True, default_retry_delay=10, max_retries=3)
def commit_preload_timer_task(id_list):
    """
    according preload_id get data from preload_url, and put data to rabbit , then execute the pre loading process
    :param preload_id:
    :return:
    """
    try:
        results = db_s1.preload_url.find({"_id": {'$in': [ObjectId(i) for i in id_list]}})
        results = [asssemble_data(i) for i in results]
        if results:
            logger.debug('commit_preload_timer_task results:%s' % results)
            url_dict = {}
            for r in results:
                logger.debug('commit_preload_timer_task r:%s' % r)
                logger.debug('commit_preload_timer_task type(r):%s' % type(r))
                if r.get('devices'):
                    d_md5 = md5(json.dumps(r['devices'])).hexdigest()
                    url_dict.setdefault(d_md5, []).append(r)
                    logger.debug('commit_preload_timer_task d_md5: %s' % d_md5)
                    if len(url_dict[d_md5]) > PACKAGE_SIZE:
                        preload_worker_new.dispatch.delay(url_dict.pop(d_md5))

                else:
                    url_dict.setdefault(r.get('channel_code'), []).append(r)
                    if len(url_dict.get(r.get('channel_code'), {})) > PACKAGE_SIZE:
                        preload_worker_new.dispatch.delay(url_dict.pop(r.get('channel_code')))
            logger.debug('commit_preload_timer_task url_dict: %s' % url_dict)
            for urls in list(url_dict.values()):
                preload_worker_new.dispatch.delay(urls)
                logger.debug('commit_preload_timer_task delay(urls): %s, type(urls): %s' % (urls, type(urls)))
            logger.debug('commit_preload_timer_task delay(urls) finished!')
    except Exception:
        logger.error('commit_preload_timer_task error: %s' % trackback.format_exc())
        return


def asssemble_data(result):
    """
    assemble result which from mongo preload_url, dict
    :param result:
    :return:
    """
    logger.debug('asssemble_data result: %s' % result)
    try:
        if result:
            datetime_now = datetime.now()
            start_time = result.get('start_time')
            start_time_timestamp = time.mktime(start_time.timetuple())
            task = {'md5': result.get('md5', ''), 'task_id': result.get('task_id'), 'username': result.get('username'),
                    'user_id': result.get('user_id', ''),'_id': str(result.get('_id', '')),
                    'channel_code': result.get('channel_code', ''), 'status': result.get('status'),
                    'url': result.get('url', ''), 'parent': result.get('parent'),
                    'get_url_speed': result.get("get_url_speed", ""),
                    # 'created_time': datetime_now.strftime('%Y-%m-%d %H:%M:%S'),
                    'created_time': result.get('created_time'),
                    'created_time_timestamp': time.mktime(datetime_now.timetuple()),
                    'check_type': result.get('check_type', "BASIC"),
                    'start_time': start_time, 'start_time_timestamp': start_time_timestamp,
                    'action': result.get('action', ''), 'is_multilayer': result.get('is_multilayer'),
                    'priority': result.get('priority'), 'nest_track_level': result.get('nest_track_level'),
                    'preload_address': result.get('preload_address'), 'type': result.get('preload_address'),
                    'compressed': result.get('compressed'),
                    'remote_addr': result.get('remote_addr'),
                    'devices': result.get('devices'), 'header_list': result.get('header_list', [])
                    }
            logger.debug('timer task get task id:%s' % result.get("_id"))
            return task
        return None
    except Exception:
        logger.error('preload_url_timer_task_commit assemble_data error:%s' % traceback.format_exc())
        return None



def test_insert_mongo():
    """

    :return:
    """
    data = [{'a': 1, 'b': 2}, {'a': 2, 'b': 3}]
    db_s1.test_update.insert_many(data)
    print("insert success!")


def test_update_mongo():
    """

    :return:
    """
    data = [{"_id": ObjectId("57ff206d2b8a6831b5c2f9b8"), 'a': 3, 'b': 4},
            {"_id": ObjectId("57ff206d2b8a6831b5c2f9b9"), 'a': 5, 'b': 6}]
    db_s1.test_update.insert_many({'$in': {"_id": ObjectId("57ff206d2b8a6831b5c2f9b8"),
                                        "_id": ObjectId("57ff206d2b8a6831b5c2f9b9")}}, data)
    print('insert success!')


if __name__ == "__main__":
    # test_insert_mongo()
    test_update_mongo()