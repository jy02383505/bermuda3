#! -*- coding=utf-8 -*-
"""
@version: ??
@author: rubin
@license:
@contact: longjun.zhao@chinacache.com
@site: 
@software: PyCharm
@file: preload_url_timer_redis_handled.py
@time: 16-10-13 下午3:23
"""
import logging
from util.preload_url_timer_redis_handle import process_redis_1_minute, process_redis_7_minute
from datetime import datetime
import time
import threading


LOG_FILENAME = '/Application/bermuda3/logs/preload_url_timer.log'
# logging.basicConfig(filename=LOG_FILENAME, format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s', level=logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s")
fh = logging.FileHandler(LOG_FILENAME)
fh.setFormatter(formatter)

logger = logging.getLogger('preload_url_timer')
logger.addHandler(fh)


def main():
    result = timestamp_now()
    threads = []
    logger.debug("preload_url_timer_redis_handle 1 minute start")
    process_redis_1_minute()
    logger.debug('preload_url_timer_redis_handle 1 minute end')
    if result:
        logger.debug('preload_url_timer_redis_handle 7 minute start')
        process_redis_7_minute()
        logger.debug('preload_url_timer_redis_handle 7 minute end')


def timestamp_now():
    """

    :return:
    """
    time_now_str = datetime.now().strftime('%Y-%m-%d %H:%M')
    time_now = datetime.strptime(time_now_str, '%Y-%m-%d %H:%M')
    count = time.mktime(time_now.timetuple())
    remainder = (count % 420) < 60
    logger.debug('time_now:%s, count:%s, remainder:%s' % (time_now, count, remainder))
    if remainder:
        return True
    else:
        return False


if __name__ == "__main__":
    timestamp_now()