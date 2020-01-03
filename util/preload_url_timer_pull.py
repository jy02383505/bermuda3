#! -*- coding=utf-8 -*-
"""
@version: ??
@author: rubin
@license:
@contact: longjun.zhao@chinacache.com
@site: 
@software: PyCharm
@file: preload_url_timer_pull.py
@time: 16-10-12 上午9:18
@content:pull task which will be performed (within half an hour)from database preload_url_timer,
 and then process the information and put into redis
"""
from datetime import datetime, timedelta
from core import database
import logging
from core import redisfactory
from util.tools import datetime_convert_timestamp
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

db =database.s1_db_session()
redis_preload_timer = redisfactory.getMDB(7)

def get_start_end_time(second_diff=1800):
    """
    depending on the current time, plus the time difference(second_diff   second)
    :param second_diff: time difference
    :return: the begin time and the end end of time
    """
    begin_time = datetime.now()
    end_time = begin_time + timedelta(seconds=second_diff)
    return begin_time, end_time


def get_data_from_preload_url_timer(begin_time, end_time):
    """
    according begin_time, end_time,   type timer, get data from preload_url_timer,
    :param begin_time:
    :param end_time:
    :return:
    """
    try:
        result = db.preload_url.find({'start_time': {'$gte': begin_time, '$lt': end_time}, 'status': 'TIMER'}).batch_size(50)

    except Exception:
        logger.debug('find data from preload_url_timer error:%s' % e)
        return None
    return result


def put_data_to_redis(result):
    """
    according result which is cursor returned by query database, assemble data put into redis
    two queue in redis,
    :param result: cursor returned by query database
    :return:
    """
    if result:
        try:
            pip = redis_preload_timer.pipeline()
            batch_size = 1000
            count = 0
            id_list = []
            for res in result:
                id = res.get('_id', None)
                start_time = res.get('start_time', None)
                if id and start_time:
                    timestamp_start_time = datetime_convert_timestamp(start_time)
                    timestamp_now = datetime_convert_timestamp(datetime.now())
                    timestamp_diff = timestamp_start_time - timestamp_now
                    if timestamp_diff < 60:
                        id_list.append(ObjectId(id))
                    elif timestamp_diff >= 60 and timestamp_diff < 420:
                        logger.debug('preload_url_timer_pull put_data_to_redis, put to redis 1 key:%s' % id)
                        # set in redis
                        pip.set("timer_1_" + str(id), timestamp_start_time)
                    else:
                        logger.debug('preload_url_timer_pull put_data_to_redis, put to redis 7 key:%s' % id)
                        # set in redis
                        pip.set("timer_7_" + str(id), timestamp_start_time)
                    count += 1
                    if not count % batch_size:
                        pip.execute()
                        count = 0
            # send the last batch
            pip.execute()
            if id_list:
                logger.debug('preload_url_timer_pull put_data_to_redis id_list: %s' % id_list)
                commit_preload_timer_task.delay(id_list)
        except Exception:
            logger.debug("operator error trace:%s" % traceback.format_exc())


def main():
    """

    :return:
    """

    begin_time, end_time = get_start_end_time()
    print('begin_time:%s, end_time:%s' % (begin_time, end_time))
    result = get_data_from_preload_url_timer(begin_time, end_time)
    print("result:%s" % result)
    put_data_to_redis(result)




if __name__ == "__main__":
    main()