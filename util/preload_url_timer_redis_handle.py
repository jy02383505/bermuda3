#! -*- coding=utf-8 -*-
"""
@version: ??
@author: rubin
@license:
@contact: longjun.zhao@chinacache.com
@site: 
@software: PyCharm
@file: preload_url_timer_redis_handle.py
@time: 16-10-12 上午9:21
"""
import logging
from core import redisfactory
from datetime import datetime
import time
import traceback
from core.generate_id import ObjectId
from util.preload_url_timer_task_commit import commit_preload_timer_task

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

redis_preload_timer = redisfactory.getMDB(7)


def process_redis_7_minute():
    """
    every 7 minute process the function
    :return:
    """
    try:
        minute_7_list = redis_preload_timer.keys('timer_7_*')
        if minute_7_list:
            id_list = []
            for key in minute_7_list:
                timer_seconds = float(redis_preload_timer.get(key))
                timestamp_now = time.mktime(datetime.now().timetuple())
                time_diff = timer_seconds - timestamp_now
                if time_diff < 60:
                    redis_preload_timer.delete(key)
                    id_list.append(get_id(key))
                elif time_diff >= 60 and time_diff < 420:
                    redis_preload_timer.delete(key)
                    redis_preload_timer.set('timer_1_' + get_id(key), timer_seconds)
                else:
                    pass
            if id_list:
                commit_preload_timer_task.delay(id_list)
                logger.debug('process_redis_7_minute id_list:%s' % key)
    except Exception:
        logger.debug('operator error:%s' % traceback.format_exc())


def process_redis_1_minute():
    """
    every 1 minute process the function
    :return:
    """
    try:
        minute_1_list = redis_preload_timer.keys('timer_1_*')
        if minute_1_list:
            id_list = []
            for key in minute_1_list:
                timer_seconds = float(redis_preload_timer.get(key))
                logger.debug('process_redis_1_minute timer_seconds:%s, type:%s' % (timer_seconds, type(timer_seconds)))
                timestamp_now = time.mktime(datetime.now().timetuple())
                logger.debug('process_redis_1_minute timestamp_now:%s' % timestamp_now)
                time_diff = timer_seconds - timestamp_now
                logger.debug('process_redis_1_minute time_diff:%s' % time_diff)
                if time_diff < 60:
                    id_list.append(ObjectId(get_id(key)))
                    redis_preload_timer.delete(key)
                    logger.debug('process_redis_1_minute delete key:%s' % key)
                else:
                    pass
            if id_list:
                commit_preload_timer_task.delay(id_list)
                logger.debug('process_redis_1_minute id_list:%s' % key)
    except Exception:
        logger.debug('operator error 1 mintuate:%s' % traceback.format_exc())


def get_id(key):
    """
    parse key timer_(int)_str, return str
    :param key:timer_7_123, timer_1_234
    :return: 123
    """
    return key.split('_')[2]


if __name__ == "__main__":
    process_redis_1_minute()