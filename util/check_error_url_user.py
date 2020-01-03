#!/usr/bin/env python
# coding=utf-8
# Created by vance on 2015-02-27.

__author__ = 'vance'
__doc__ = """统计制定用户的失败任务及设备列表,并发邮件通知"""
__ver__ = '1.0'


import datetime, sys
import logging
import traceback, json
from core import database
from core import sendEmail

LOG_FILENAME = '/Application/bermuda3/logs/fail_details_user.log'
logging.basicConfig(filename=LOG_FILENAME,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger('fail_url_task')

conn = database.db_session()

class details_fails_urls(object):

    def __init__(self, conn, begin_date, end_date, username, to_add):
        super(details_fails_urls, self).__init__()
        self.begin_date = begin_date
        self.end_date = end_date
        self.connect = conn
        self.username = username
        self.to_add = to_add
        self.collection_url = ''
        self.collection_dev = ''

    def get_fail_urls(self):
        find_url_dic = {"parent":self.username,"status": "FAILED","created_time": {"$gte": self.begin_date, "$lt": self.end_date},
                         "finish_time": {"$exists": "true"}}
        field_dic = {"username": 1, "_id": 1, "dev_id": 1, "created_time": 1, "parent": 1, "url":1}
        self.collection_url = self.connect['url']
        return self.collection_url.find(find_url_dic, field_dic)

    def run(self):
        fail_list = []
        for url in self.get_fail_urls():
            try:
                u_dic = {}
                u_dic['uid'] = str(url.get("_id"))
                u_dic['created_time'] = url.get("created_time").strftime('%Y-%m-%d %H:%M:%S')
                u_dic['url'] = url.get("url")
                u_dic['failed'] = get_fail_url_device(self.connect['device'], url.get("dev_id"))
                fail_list.append(u_dic)
            except Exception:
                logger.error('run error: %s' % traceback.format_exc())
        try:
            if fail_list:
                sendEmail.send(self.to_add, '%s error task alarm' %self.username, getEmail(self.username, self.end_date, fail_list))
        except Exception:
            logger.error(traceback.format_exc())
        logger.info('process insert :{0}'.format(len(fail_list)))

def getEmail(username, date, fail_list):
    emailResult ='%s 用户 %s 10分钟内失败任务\n\n%s ' %(username, date.strftime('%Y-%m-%d %H:%M:%S'), json.dumps(fail_list, indent=2))
    return emailResult

def get_fail_url_device(collection_dev, dev_id):
    dev_obj = collection_dev.find_one({"_id":dev_id}, {"devices":1})
    dev_dic={}
    for dev in dev_obj['devices']:
        code = str(dev_obj['devices'][dev]['code'])
        name = dev_obj['devices'][dev]['name']
        host = dev_obj['devices'][dev]['host']
        if code not in ['200', '204']:
            dev_dic.setdefault(code,[]).append({name: host})
    dev_list = [{'code': c_key, 'devices': dev_dic[c_key]} for c_key in dev_dic ]
    return dev_list

if __name__ == '__main__':
    username = 'kongzhong'
    to_add = ['hongan.zhang@chinacache.com']
    minutes = 10
    try:
        if len(sys.argv) == 2:
            minutes = int(sys.argv[1])
    except Exception:
            logger.error(traceback.format_exc())
    now = datetime.datetime.now()
    start_str = 'start script on {datetime}'.format(datetime=now)
    logger.info(start_str)
    cur_time = datetime.datetime.combine(now.date(), now.time().replace(second=0, microsecond=0))
    pre_time = cur_time - datetime.timedelta(minutes=minutes)
    df = details_fails_urls(conn, pre_time, cur_time, username, to_add)
    df.run()
    end_time = datetime.datetime.now()
    end_str = 'finish script on {datetime}, use {time}'.format(datetime=end_time, time=end_time-now)
    logger.info(end_str)
    exit()
