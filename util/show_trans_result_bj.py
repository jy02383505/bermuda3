#! /usr/bin/env python
# -*- coding: utf-8 -*-
__author__ = 'vance'
__date__ = '5/8/15'
__doc__='''
自动化获取转发的任务结果，并进行分析
20150515: bj
 count:31365
finish:22352
fail:9013
avg:34.61
 fail per:29.00%
20150515:
 sh
 count:47598
finish:29005
fail:18593
avg:49.81
 fail per:39.00%
'''

import datetime
try:
    from pymongo import Connection as mongo
except:
    from pymongo import MongoClient as mongo
from core import redisfactory
import os
import string
import simplejson as json
from bson.objectid import ObjectId

'''
show transfer_url.py test result

'''
STRLEN = 30
temp_cache = redisfactory.getDB(7)


def format_string(strs):
    return string.ljust(strs, STRLEN)

class show_data(object):
    def __init__(self):
        self.conn_bj = self.con_mongo_bj()
        self.conn_sh = self.con_mongo_sh()
        self.uid_keys = []
        self.rid_keys = []
        self.get_redis_keys()

    def con_mongo_bj(self):
        return mongo("223.202.52.134", 27017)['bermuda']
    def con_mongo_sh(self):
        return mongo("101.251.97.145", 27017)['bermuda']

    def get_redis_keys(self):
        keys = list(temp_cache.keys())
        for k in keys:
            if 'uid' in k:
                self.uid_keys.append(k)
            else:
                self.rid_keys.append(k)

    def get_url_data(self):
        # now = datetime.datetime.now()
        # leftend = datetime.datetime.strptime(now.strftime('%Y%m%d%H'),"%Y%m%d%H")
        # rightend = leftend + datetime.timedelta(hours=1)
        connect = self.conn_bj['url']
        count = 0
        fail_num= 0
        finish_num = 0
        take_times = 0

        datastr=datetime.datetime.now().strftime("%Y%m%d")
        # uids = temp_cache.get('{0}uid'.format(datastr))
        for uu in self.uid_keys:
            uids = temp_cache.get(uu)
            uids_list = [ObjectId("%s"%uid) for uid in eval(uids)]
            # for uid in uids_list:
            for doc in connect.find({'_id': {"$in": uids_list}}):
                # doc = connect.find_one({"_id":uid})
                count += 1
                print(doc)
                if 'finish_time' in doc:
                    take_time = (doc['finish_time']-doc['created_time']).seconds
                else:
                    take_time = 0
                if doc['status'] in ['FINISHED']:
                    finish_num +=1
                else:
                    fail_num +=1
                take_times += take_time
        message = '{0}:\r\n bj \r\n count:{1}\r\nfinish:{2}\r\nfail:{3}\r\navg:{4:.2f}\r\n fail per:{5:.2f}%'.format(datastr,count,finish_num,fail_num,round(take_times/float(count),2),round(fail_num/float(count),2)*100)
        self.write_txt(message)

    def get_rid_data(self):
        connect = self.conn_sh['url']
        count = 0
        fail_num= 0
        finish_num = 0
        take_times = 0
        datastr=datetime.datetime.now().strftime("%Y%m%d")
        # rids = temp_cache.get('{0}rid'.format(datastr))
        for uu in self.rid_keys:
            rids = temp_cache.get(uu)
            # print rids,type(rids)
            rids_list = [ObjectId("%s"%rid) for rid in eval(rids)]
            # for uid in uids_list:
            for doc in connect.find({'r_id': {"$in": rids_list}}):
                print(doc)
                count += 1
                if 'finish_time' in doc:
                    take_time = (doc['finish_time']-doc['created_time']).seconds
                else:
                    take_time = 0
                if doc['status'] in ['FINISHED']:
                    finish_num +=1
                else:
                    fail_num +=1
                take_times += take_time
        message = '{0}:\r\n sh \r\n count:{1}\r\nfinish:{2}\r\nfail:{3}\r\navg:{4:.2f}\r\n fail per:{5:.2f}%'.format(datastr,count,finish_num,fail_num,round(take_times/float(count),2),round(fail_num/float(count),2)*100)
        self.write_txt(message)

    def write_txt(self, content):
        file_name = datetime.datetime.now().strftime("%Y%m%d.log")
        log_dir = '/Application/bermuda3/logs/'
        if not os.path.exists(log_dir):
            os.mkdir(log_dir)
        log_file = '{0}/show_trans{1}'.format(log_dir, file_name)
        f = file("%s" % log_file, "a")
        # for k,v in url_dic.items():
        #     if len(v['new'])>0 and len(v['old'])>0:
        #         content = '{0}    {1}    {2}'.format(format_string(k), v['new'], v['old'])
        f.write(content + "\r\n")
        f.flush()
        f.close()


if __name__ == '__main__':
    show = show_data()
    show.get_url_data()
    show.get_rid_data()