#!/usr/bin/env python
# coding=utf-8
# Created by vance on 2015-02-27.
import copy

__author__ = 'vance'
__doc__ = """统计用户的失败任务及设备列表"""
__ver__ = '1.0'


import datetime
#from pymongo import ReplicaSetConnection, ReadPreference, Connection
import logging
import traceback
from core import database
import sys
from core.database import db_session
import os

LOG_FILENAME = '/Application/bermuda3/logs/fail_details.log'
logging.basicConfig(filename=LOG_FILENAME,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger('fail_url_task')
logger.setLevel(logging.DEBUG)

# conn = database.db_session()
# conn = ReplicaSetConnection('%s:27017,%s:27017,%s:27017' % ('172.16.12.136', '172.16.12.135', '172.16.12.134'), replicaSet ='bermuda_db')['bermuda']
conn =db_session()
# conn = Connection("223.202.52.135", 27017)['bermuda']

class details_fails_urls(object):
    """TTL: db.ref_err.ensureIndex( { "datetime": -1 }, { expireAfterSeconds: 60*60*24*7 })
        db.ref_err.ensureIndex({"uid":1 },{"unique":true})
        db.ref_err.ensureIndex({"channel_code":1})
        db.ref_err.ensureIndex({"failed.code":1})
        db.ref_err.ensureIndex({"username":1})
    """
    def __init__(self, conn, begin_date, end_date):
        super(details_fails_urls, self).__init__()
        self.begin_date = begin_date
        self.end_date = end_date
        self.connect = conn
        self.collection_url = ''
        self.collection_dev = ''
        self.collection_err = ''

    def get_fail_urls(self):
        # "status": "FAILED","created_time": {"$gte": ISODate("2015-03-10T13: 00: 34.93Z"), "$lt": ISODate("2015-03-10T14: 00: 34.93Z"),},
        #                  "finish_time": {"$exists": "true"}
        #
        find_url_dic = {"status": "FAILED","created_time": {"$gte": self.begin_date, "$lt": self.end_date},
                         "finish_time": {"$exists": "true"}}
        field_dic = {"username": 1, "_id": 1, "dev_id": 1, "channel_code": 1, "parent": 1, "url":1}
        self.collection_url = self.connect['url']
        return self.collection_url.find(find_url_dic, field_dic)

    def insert(self, data):
        self.collection_err = self.connect['ref_err']
        if sys.getsizeof(data) > 4*1024*1024:
            raise Exception("Data size of inserted doc(s) is too big")
        self.collection_err.insert(data)
        # self.collection_err.update(data, {'$set': {'salary' : 10000}}, upsert=True, multi=True)

    def exist_modify(self, uid, u_dic):
        self.collection_err = self.connect['ref_err']
        ret = self.collection_err.find_and_modify({"uid": uid}, update={"$set": {"failed": u_dic['failed'], "f_devs": u_dic['f_devs'], "firstLayer": u_dic['firstLayer']}})
        if ret:
            return True
        else:
            return False

    def get_uid(self,uid):
        pass

    def run(self):
        fail_list = []
        total = 0
        modify = 0
        fail_num=0
        for url in self.get_fail_urls():
            try:
                insert_time= datetime.datetime.now()
                uid = url.get("_id")
                u_dic = {}
                u_dic['username'] = url.get("parent")#取主账户
                u_dic['uid'] = uid
                u_dic['channel_code'] = url.get("channel_code")
                #u_dic['datetime'] = self.end_date
                u_dic['datetime'] = insert_time
                logger.info('insert time is {datetime}'.format(datetime=insert_time))
                logger.info('insert fail id is %s' % (uid))
                u_dic['dev_id'] = url.get("dev_id")
                u_dic['url'] = url.get("url")
                try:
                    u_dic['failed'], u_dic['f_devs'], u_dic['firstLayer'], u_dic['devices'] = get_fail_url_device(self.connect['device'], url.get("dev_id"))
                except Exception:
                    logger.error('run error: %s' % traceback.format_exc())
                    logger.error('run error devid: %s %s' %(url.get("dev_id"),uid))
                if not self.exist_modify(uid, u_dic):
                    fail_list.append(u_dic)
                else:
                    modify += 1
                if len(fail_list) > 10000:
                    fail_num=fail_num+10000
                    self.insert(fail_list)
                    fail_list=[]
            except Exception:
                logger.error('run error: %s' % traceback.format_exc())

            total += 1

        try:
            if fail_list:
                fail_num=fail_num+len(fail_list)
                self.insert(fail_list)
        except Exception:
            logger.error(traceback.format_exc())
        logger.info('process num :{0}'.format(total))
        #logger.info('process insert :{0}'.format(len(fail_list)))
        logger.info('process insert :{0}'.format(fail_num))
        logger.info('process modify :{0}'.format(modify))


def get_fail_url_device(collection_dev, dev_id):
        # self.collection_dev = self.connect['device']
        dev_obj = collection_dev.find_one({"_id":dev_id}, {"devices":1})
        dev_dic={}
        dev_s_layer = []
        dev_f_fail = {}
        firstLayer = False
        devs_list = []
        for dev in dev_obj['devices']:
            d_dic = {}
            code = str(dev_obj['devices'][dev]['code'])
            name = dev_obj['devices'][dev]['name']
            firstL = dev_obj['devices'][dev]['firstLayer']
            host = dev_obj['devices'][dev]['host']
            if code not in ['200', '204']:
                if code not in dev_dic:
                    dev_dic[code] = []
                if firstL:
                    dev_f_fail[name] = host
                else:
                    dev_dic[code].append({name: host})
                d_dic['hostname'] = name
                d_dic['ip'] = host
                d_dic['code'] = code
                d_dic['firstLayer'] = firstL
                devs_list.append(d_dic)

            elif code in ['200'] and not firstL:
                dev_s_layer.append({name: host})

        # dev_f_fail = list(set(dev_f_layer).intersection(set(dev_fail)))
        dev_list = [{'code': c_key, 'devices': dev_dic[c_key]} for c_key in dev_dic ]
        if dev_f_fail:
            dev_list.extend([{'code': '200', 'devices': dev_s_layer}])
            firstLayer = True


        return dev_list, dev_f_fail, firstLayer,devs_list

def get_date():
    global now, today, begin_date, end_date
    now = datetime.datetime.now()
    today = now.date()
    begin_date = today - datetime.timedelta(days=1)
    begin_date = datetime.datetime.combine(begin_date, datetime.time())
    end_date = datetime.datetime.combine(today, datetime.time())
    return begin_date, end_date

def main():
    # for h in range(24):
    now = datetime.datetime.now()
    today = now.date()
    begin_date = today - datetime.timedelta(days=1)
    begin_date = datetime.datetime.combine(begin_date, datetime.time())
    end_date = datetime.datetime.combine(today, datetime.time())
    cur_time = begin_date
    while cur_time <= end_date:
            next_time = cur_time+datetime.timedelta(hours=1)
            df = details_fails_urls(conn,cur_time, next_time)
            df.run()
            cur_time = next_time

def run():
    now = datetime.datetime.now()
    start_str = 'start script on {datetime}'.format(datetime=now)
    logger.info(start_str)
    print(start_str)
    # main()
    # cur_time = datetime.datetime.combine(now.date(), now.time().replace(minute=0, second=0, microsecond=0))
    cur_time = datetime.datetime.combine(now.date(), now.time().replace(second=0, microsecond=0))
    # pre_time = cur_time - datetime.timedelta(hours=1)
    pre_time = cur_time - datetime.timedelta(minutes=31)
    # pre_time = cur_time - datetime.timedelta(minutes=1)
    df = details_fails_urls(conn, pre_time, cur_time)
    df.run()
    end_time = datetime.datetime.now()
    end_str = 'finish script on {datetime}, use {time}'.format(datetime=end_time, time=end_time-now)
    print(end_str)
    logger.info(end_str)
    os._exit(0)


if __name__ == '__main__':
    now = datetime.datetime.now()
    start_str = 'start script on {datetime}'.format(datetime=now)
    logger.info(start_str)
    print(start_str)
    # main()
    # cur_time = datetime.datetime.combine(now.date(), now.time().replace(minute=0, second=0, microsecond=0))
    cur_time = datetime.datetime.combine(now.date(), now.time().replace(second=0, microsecond=0))
    # cur_time = cur_time - datetime.timedelta(hours=6)
    # pre_time = cur_time - datetime.timedelta(hours=1)
    pre_time = cur_time - datetime.timedelta(minutes=31)
    # pre_time = cur_time - datetime.timedelta(minutes=1)
    df = details_fails_urls(conn, pre_time, cur_time)
    df.run()
    end_time = datetime.datetime.now()
    end_str = 'finish script on {datetime}, use {time}'.format(datetime=end_time, time=end_time-now)
    print(end_str)
    logger.info(end_str)
    os._exit(0)

