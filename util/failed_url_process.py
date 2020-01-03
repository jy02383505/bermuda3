#! -*- coding=utf-8 -*-
"""
@version: ??
@author: rubin
@license:
@contact: longjun.zhao@chinacache.com
@site: 
@software: PyCharm
@file: query_utils.py
@time: 17-7-27 下午3:07
"""
from util import log_utils
import traceback
import threading
from bson import ObjectId
import time
import datetime
from core.config import config
import logging





# logger = log_utils.get_receiver_Logger()
# LOG_FILENAME = '/Application/bermuda3/logs/failed_url_process.log'
# logging.basicConfig(filename=LOG_FILENAME,
#                     format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s',
#                     level=logging.INFO)
#
# logger = logging.getLogger('failed_url_process')
# logger.setLevel(logging.DEBUG)


LOG_FILENAME = '/Application/bermuda3/logs/failed_url_process.log'
# LOG_FILENAME = '/home/rubin/logs/update_redis_channel_customer.log'
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s")
fh = logging.FileHandler(LOG_FILENAME)
fh.setFormatter(formatter)

logger = logging.getLogger('failed_url_process')
logger.addHandler(fh)
logger.setLevel(logging.DEBUG)


from core import database


db = database.query_db_session()



class thread_t_f(threading.Thread):
    def __init__(self, username, start_time, end_time):
        threading.Thread.__init__(self)
        self.list_result = {'urls': [], 'dirs': []}
        self.username = username
        self.start_time = start_time
        self.end_time = end_time
        # self.failure_rate = dev_failed_rate


    def get_list_result(self):
        return self.list_result


    def run(self):
        try:
            result_all_failed = db.url.find({'username': self.username,
                                  'created_time': {"$gte": self.start_time, "$lt": self.end_time}, 'status': "FAILED"})
        except Exception:
            logger.debug("find url error:%s" % traceback.format_exc())
            result_all_failed = []
        if result_all_failed:
            list_insert = []
            for res in result_all_failed:
                dev_info = {}
                dev_id = res.get('dev_id')
                devices_t = db.device.find_one({'_id': ObjectId(dev_id)})
                devices = list(devices_t.get('devices').values())
                all = 0
                suspend = 0
                failed = 0
                success = 0
                if devices:
                    for dev in devices:
                        if dev.get('code') == 200:
                            success += 1
                        elif dev.get('code') == 204:
                            suspend += 1
                        else:
                            failed += 1
                        all += 1
                dev_failed_rate = failed / (all * 1.0)
                dev_info['username'] = self.username
                dev_info['isdir'] = res.get('isdir')
                dev_info['url'] = res.get('url')
                dev_info['created_time'] = res.get('created_time')
                dev_info['failed_rate'] = dev_failed_rate
                dev_info['dev_all'] = all
                dev_info['dev_failed'] = failed
                dev_info['success'] = success
                dev_info['suspend'] = suspend
                list_insert.append(dev_info)
                try:
                    if len(list_insert) >= 30:
                        db.failed_task.insert(list_insert)
                        list_insert = []
                except Exception:
                    logger.debug('failed_task insert error:%s' % traceback.format_exc())
                    logger.debug("failed_task insert list_insert:%s" % list_insert)
                    list_insert = []
            if len(list_insert) > 0:
                try:
                    db.failed_task.insert(list_insert)
                except Exception:
                    logger.debug('last insert list_insert failed_task error:%s' % traceback.format_exc())
                    logger.debug('last insert list_insert failed_task  list_insert:%s' % list_insert)

            logger.debug('run over  insert into failed_task finished!')




#
# def process_thread_results(threads_result, failed_rate=0.9):
#     """
#
#     Args:
#         threads_result: [{'urls': [], 'dirs': []}, {'urls': [], 'dirs': []}]
#
#     Returns:{
#            'msg': 'ok',
#            'failed_num': 123,
#            'failed_list': {
#              'urls': ['xxx', 'xxx', 'xxx'],
#              'dirs': ['xxx', 'xxx', 'xxx']
#            }
#         }
#
#     """
#     set_urls = set()
#     set_dirs = set()
#     for threads_res in threads_result:
#         set_urls.update(threads_res.get('urls'))
#         set_dirs.update(threads_res.get('dirs'))
#     list_urls = list(set_urls)
#     list_dirs = list(set_dirs)
#     list_urls_result = list_urls[:int(len(list_urls) * failed_rate)]
#     list_dirs_result = list_dirs[:int(len(list_dirs) * failed_rate)]
#     failed_num = len(list_urls_result) + len(list_dirs_result)
#     return {'msg': 'ok', 'failed_num': failed_num, 'failed_list': {'urls': list_urls_result, 'dirs': list_dirs_result}}




def get_failed_result(task_new, interval=300):
    """
    300 seconds, one thread
    Args:
        task_new: {'username': xxxxxx, 'start_time': (datetime), 'end_time': (datetime),
                'dev_failed_rate': 0.05, 'failed_rate': 0.9}

    Returns:


    """
    process_begin = time.time()
    start_time = task_new.get('start_time')
    end_time = task_new.get('end_time')
    start_timestamp = time.mktime(start_time.timetuple())
    end_timestamp = time.mktime(end_time.timetuple())
    time_stamp_list = []
    temp_timestamp = start_timestamp
    while(temp_timestamp < end_timestamp):
        temp_time_dict = {}
        temp_time_dict['start'] = temp_timestamp
        if temp_timestamp + interval < end_timestamp:
            temp_time_dict['end'] = temp_timestamp + interval
        else:
            temp_time_dict['end'] = end_timestamp
        temp_timestamp += interval
        time_stamp_list.append(temp_time_dict)
    threads = []
    for time_dict in time_stamp_list:

        start_time, end_time = datetime.datetime.fromtimestamp(time_dict.get('start')), datetime.datetime.fromtimestamp(time_dict.get('end'))
        print(start_time, end_time)
        threads.append(thread_t_f(task_new.get('username'), start_time, end_time))
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    logger.debug("success time consume:%s seconds" % (time.time() - process_begin))
    # threads_result = []
    # for t in threads:
    #     threads_result.append(t.get_list_result())
    # result = process_thread_results(threads_result, failed_rate=task_new.get('failed_rate'))
    # return result


def main_fun():
    """

    Returns:

    """
    try:
        usernames = eval(config.get('failed_query_rate', 'usernames'))
    except Exception:
        logger.debug("get usernames error:%s" % traceback.format_exc())
        usernames = []
    if usernames:
        for username in usernames:
            end_time = datetime.datetime.now()
            start_time = end_time + datetime.timedelta(minutes=-10)


            dict_t = {'username': username, 'start_time': start_time, 'end_time': end_time}
            get_failed_result(dict_t)


if __name__ == "__main__":
    pass