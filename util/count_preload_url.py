#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Created by vance on 7/29/14.

__author__ = 'vance'
__doc__ = ''
__ver__ = '1.0'

import datetime
import logging
import sys

from core import database
import imp


imp.reload(sys)
sys.setdefaultencoding('utf8')

LOG_FILENAME = '/Application/bermuda3/logs/count_preload.log'
logging.basicConfig(filename=LOG_FILENAME,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger('preload_count')
logger.setLevel(logging.DEBUG)

db = database.query_db_session()


def write_log(end_date, content):
    file_name = end_date.strftime("%Y%m%d.log")
    log_file = '/Application/bermuda3/logs/preload_count_%s' % file_name
    f = file("%s" % (log_file), "a")
    f.write(content + "\r\n")
    f.flush()
    f.close()


class Preload_Count(object):
    def __init__(self, collection, begin_date, end_date):
        self.collection = collection
        self.begin_date = datetime.datetime.combine(begin_date, datetime.time())
        self.end_date = datetime.datetime.combine(end_date, datetime.time())
        self.u_dic = {}

    def count_query(self):
        self.find_dic = {"created_time": {"$gte": self.begin_date, "$lt": self.end_date},
        }
        self.querys = self.collection.find(self.find_dic)
        for query in self.querys:
            u_name = query.get("username")
            # status = query.get("status")
            # dic = {'created_time':c_time,'finish_time':f_time,'status':status}
            # {'duwan':1,'duwan1':1}
            if u_name not in list(self.u_dic.keys()):
                self.u_dic[u_name] = 1
            else:
                self.u_dic[u_name] += 1


if __name__ == '__main__':
    now = datetime.datetime.now()
    today = now.date()
    # begin_date = today - datetime.timedelta(days=30)
    #begin_date = datetime.datetime.combine(begin_date, datetime.time())
    end_date = datetime.datetime.combine(today, datetime.time())
    head_list = []
    head_list.append('{0:10}'.format(''))
    content_dic = {}
    u_list = []
    for i in range(30):
        end_date = today - datetime.timedelta(days=i)
        begin_date = end_date - datetime.timedelta(days=1)
        head_list.append('{0:10}'.format(begin_date.strftime('%Y%m%d')))
        pc = Preload_Count(db.preload_url, begin_date, end_date)
        pc.count_query()
        get_dic = pc.u_dic
        content_dic[begin_date.strftime('%Y%m%d')] = get_dic
        u_list.extend(list(get_dic.keys()))

    uname_list = set(u_list)
    write_log(today, ' '.join(head_list))
    for u in uname_list:
        w_list = ['{0:10}'.format(u)]
        print(u)
        for i in range(30):
            begin_date = today - datetime.timedelta(days=i + 1)
            u_date = content_dic[begin_date.strftime('%Y%m%d')]
            w_list.append('{0:10}'.format(u_date[u] if u in u_date else 0))
        write_log(today, ' '.join(w_list))
    exit()