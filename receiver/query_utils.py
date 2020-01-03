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
import simplejson as json





logger = log_utils.get_receiver_Logger()


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





def process_thread_results(threads_result, failed_rate=0.9):
    """

    Args:
        threads_result: [{'urls': [], 'dirs': []}, {'urls': [], 'dirs': []}]

    Returns:{
           'msg': 'ok',
           'failed_num': 123,
           'failed_list': {
             'urls': ['xxx', 'xxx', 'xxx'],
             'dirs': ['xxx', 'xxx', 'xxx']
           }
        }

    """
    set_urls = set()
    set_dirs = set()
    for threads_res in threads_result:
        set_urls.update(threads_res.get('urls'))
        set_dirs.update(threads_res.get('dirs'))
    list_urls = list(set_urls)
    list_dirs = list(set_dirs)
    list_urls_result = list_urls[:int(len(list_urls) * failed_rate)]
    list_dirs_result = list_dirs[:int(len(list_dirs) * failed_rate)]
    failed_num = len(list_urls_result) + len(list_dirs_result)
    return {'msg': 'ok', 'failed_num': failed_num, 'failed_list': {'urls': list_urls_result, 'dirs': list_dirs_result}}




def get_failed_result(task_new, interval=300):
    """
    300 seconds, one thread
    Args:
        task_new: {'username': xxxxxx, 'start_time': (datetime), 'end_time': (datetime),
                'dev_failed_rate': 0.05, 'failed_rate': 0.9}

    Returns:


    """
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
        threads.append(thread_t_f(task_new.get('username'), start_time, end_time, task_new.get('dev_failed_rate')))
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    threads_result = []
    for t in threads:
        threads_result.append(t.get_list_result())
    result = process_thread_results(threads_result, failed_rate=task_new.get('failed_rate'))
    return result


def query_all_result(condition):
    """

    Args:
        condition: {'channel_name': xxxx, 'url':xxx , 'created_time': {'$gte':xxxx, '$lt': xxxx}}

    Returns:{
          'msg': 'ok',
        data: [{
         'username':xxxx,
         'url':xxxx,
         'isdir': False or True,
         'status': FAILED OR FINISHED OR PROGRESS OR INVALID OR TIMER,
         'created_time': xxxxx,
         'finish_time': xxxxx,
         'devices':  [
                   {
                   'name': xxxxx, 'status': OPEN or SUSPEND OR ..., 'type': FC or HPCC or unknown,
                   'code':xxx, 'a_code':xxxx, 'r_code': xxxxx, 'host':'127.53.32.23', 'firstLayer': False or True
                   }
                     ],
         'sub_center_devices':[
                         {
                         'name': 'xxxx', 'status': 'xxxx', 'type': HPCC or FC or unknown,'branch_code':xxxx, (int)
                         'host': xxxxx, 'firstLayer': xxxx, 'sub_center_ip': xxx, 'create_time': xxxxxx,
                         'subcenter_return_time': xxxx
                         }
                        ]
        }]
        }

    """
    data = []

    try:
        url_result = db.url.find(condition)
    except Exception:
        logger.debug('find url error:%s' % traceback.format_exc())
        return json.dumps({'msg': 'error', 'info': 'find mongodb error'})
    if not url_result:
        return json.dumps({'msg': 'ok', 'data': data})
    for url_t in url_result:
        url_temp = {}
        url_temp['username'] = url_t.get('username')
        url_temp['url'] = url_t.get('url')
        url_temp['isdir'] = url_t.get('isdir')
        url_temp['status'] = url_t.get('status')
        url_temp['created_time'] = url_t.get('created_time').strftime('%Y-%m-%d %H:%M:%S') if url_t.get('created_time') else None
        url_temp['finish_time'] = url_t.get('finish_time').strftime('%Y-%m-%d %H:%M:%S') if url_t.get('finish_time') else None
        dev_id = url_t.get('dev_id')
        url_temp['devices'] = query_device_depend_id(dev_id)
        url_temp['sub_center_devices'] = query_retry_device_depend_id(url_t.get('retry_branch_id'))
        data.append(url_temp)
    return json.dumps({'msg': 'ok', 'data': data})



def query_device_depend_id(dev_id):
    """

    Args:
        dev_id:

    Returns:[
                   {
                   'name': xxxxx, 'status': OPEN or SUSPEND OR ..., 'type': FC or HPCC or unknown,
                   'code':xxx, 'a_code':xxxx, 'r_code': xxxxx, 'host':'127.53.32.23', 'firstLayer': False or True
                   }
                     ]

    """
    logger.debug('query_device_depend_id  dev_id:%s' % dev_id)
    devices = []
    if not dev_id:
        return devices
    try:
        devices_result = db.device.find_one({'_id': ObjectId(dev_id)})
    except Exception:
        logger.debug('query_device_depend_id find device error:%s' % traceback.format_exc())
        return devices
    if devices_result:
        devices_devs = devices_result.get('devices')
        if devices_devs:
            for dev in list(devices_devs.values()):
                data_temp = {}
                data_temp['name'] = dev.get('name')
                data_temp['status'] = dev.get('status')
                data_temp['type'] = dev.get('type')
                data_temp['code'] = dev.get('code')
                data_temp['a_code'] = dev.get('a_code')
                data_temp['r_code'] = dev.get('r_code')
                data_temp['host'] = dev.get('host')
                data_temp['firstLayer'] = dev.get('firstLayer')
                devices.append(data_temp)
    return devices



def query_retry_device_depend_id(retry_branch_id):
    """

    Args:
        dev_id:

    Returns:[
             {
             'name': 'xxxx', 'status': 'xxxx', 'type': HPCC or FC or unknown,'branch_code':xxxx, (int)
             'host': xxxxx, 'firstLayer': xxxx, 'sub_center_ip': xxx, 'create_time': xxxxxx,
             'subcenter_return_time': xxxx
             }
            ]

    """
    logger.debug('query_retry_device_depend_id  retry_branch_id:%s' % retry_branch_id)
    devices = []
    if not retry_branch_id:
        return devices
    try:
        devices_result = db.retry_device_branch.find_one({'_id': ObjectId(retry_branch_id)})
    except Exception:
        logger.debug('query_retry_device_depend_id find device error:%s' % traceback.format_exc())
        return devices
    if devices_result:
        create_time = devices_result.get('create_time').strftime('%Y-%m-%d %H:%M:%S') if devices_result.get('create_time') else None
        devices_devs = devices_result.get('devices')
        if devices_devs:
            for dev in devices_devs:
                data_temp = {}
                data_temp['name'] = dev.get('name')
                data_temp['status'] = dev.get('status')
                data_temp['type'] = dev.get('type')
                data_temp['code'] = dev.get('branch_code')

                data_temp['host'] = dev.get('host')
                data_temp['firstLayer'] = dev.get('firstLayer')
                data_temp['create_time'] = create_time
                data_temp['subcenter_return_time'] = dev.get('subcenter_return_time').strftime('%Y-%m-%d %H:%M:%S') if dev.get('subcenter_return_time') else None
                data_temp['sub_center_ip'] = dev.get('sub_center_ip')
                devices.append(data_temp)
    return devices








if __name__ == "__main__":
    pass