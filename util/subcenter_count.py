#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Created by vance on 16/7/21.

__author__ = 'vance'
__doc__ = """分中央处理效果统计脚本"""
__ver__ = '1.0'


from core import database
import datetime
import logging
import os

LOG_FILENAME = '/Application/bermuda3/logs/subcenter_count.log'
logging.basicConfig(filename=LOG_FILENAME,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger('subcenter_count')
logger.setLevel(logging.DEBUG)

db = database.db_session()
q_db = database.query_db_session()


class SubcenterCount(object):
    def __init__(self, begin_date, end_date):
        self.begin_date = begin_date
        self.end_date = end_date
        self.result = {}
        self.subcenters = {}

    def get_url_data(self):
        find_dic = {"created_time": {"$gte": self.begin_date, "$lt": self.end_date}}
        fail_dic = {"status": "FAILED"}
        # st_dic = {'new_status': {'$exists': True}}
        f_dic = {'new_status':"FINISHED"}
        url_obj = db.url
        total = url_obj.find(find_dic).count()
        fail_dic.update(find_dic)
        fail_num = url_obj.find(fail_dic).count()
        # st_dic.update(find_dic)
        # send_num = url_obj.find(st_dic).count()
        f_dic.update(find_dic)
        send_success_num = url_obj.find(f_dic).count()
        url_status_per =  '{0:.2%}'.format(round(send_success_num/ float(total), 4))
        self.result["date"] = self.begin_date
        self.result["total"] = total
        self.result["fail_num"] = fail_num
        # self.result["send_subcenter_num"] = send_num
        self.result["url_success_num"] = send_success_num
        self.result["url_per"] = url_status_per

    def get_device_branch(self):
        find_dic = {"create_time": {"$gte": self.begin_date, "$lt": self.end_date}}
        device_obj = db.retry_device_branch
        total = device_obj.find(find_dic).count()
        # d_dic = {"devices.branch_code": 200}
        # d_dic.update(find_dic)
        # device_send_sucess = device_obj.find(d_dic).count()
        # devices_status_per = '{0:.2%}'.format(round(device_send_sucess/ float(total), 4))
        self.result["need_process_num"] = total

        #self.result["devices_status_per"] = devices_status_per
        # print d_dic
        bran_obj = device_obj.find(find_dic)
        nn = 0
        fn = 0
        sn = 0
        for dobj in bran_obj:
            objs = dobj["devices"]#[0]
            for obj in objs:
                try:
                    if obj["sub_center_ip"] in self.subcenters:
                        if str(obj["branch_code"]) in self.subcenters[obj["sub_center_ip"]]:
                            self.subcenters[obj["sub_center_ip"]][str(obj["branch_code"])] += 1
                        else:
                            self.subcenters[obj["sub_center_ip"]][str(obj["branch_code"])] = 1
                    else:
                        self.subcenters[obj["sub_center_ip"]]={str(obj["branch_code"]): 1}
                    nn +=1
                    if obj["branch_code"] == 200: sn+=1
                except Exception:
                    fn +=1
                    # print ex
                    # print obj
        print(nn,fn)
        self.result["device_success_num"] = sn
        self.result["device_send_num"] = nn
        self.result["subcenters"] = self.subcenters

    def insertDB(self):
        logger.debug(self.result)
        db.statistical_subcenter.insert(self.result, check_keys=False)

def run():
    now = datetime.datetime.now()
    today = now.date()
    begin_date = today - datetime.timedelta(days=1)
    begin_date = datetime.datetime.combine(begin_date, datetime.time())
    end_date = datetime.datetime.combine(today, datetime.time())
    result = {}
    sc = SubcenterCount(begin_date, end_date)
    sc.get_url_data()
    sc.get_device_branch()
    sc.insertDB()
    os._exit(0)

if __name__ == '__main__':
    now = datetime.datetime.now()
    today = now.date()
    begin_date = today - datetime.timedelta(days=1)
    begin_date = datetime.datetime.combine(begin_date, datetime.time())
    end_date = datetime.datetime.combine(today, datetime.time())
    result = {}
    sc = SubcenterCount(begin_date, end_date)
    sc.get_url_data()
    sc.get_device_branch()
    sc.insertDB()
    os._exit(0)
