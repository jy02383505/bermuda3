#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Created by vance on 8/8/14.
import copy
import imp

__author__ = 'vance'
__doc__ = """
    测试脚本，转发正式环境下的任务，批量测试服务器接收处理能力，生成两个日志文件；
    将结果存入redis 7 库
    159) "2015051508uid"
    160) "2015051317rid"

    redis 127.0.0.1:6379[7]> get "2015051508uid"
"['555536c84fb79a6cf94a18c9', '555536c84fb79a6cf94a18c8', '555536c84fb79a6cf94a18c7',
'555536c84fb79a6cf94a18c6', '555536c84fb79a6cf94a18c5', '555536c84fb79a6cf94a18c4',
 '555536c84fb79a6cf94a18c3', '555536c84fb79a6cf94a18c2', '555536c84fb79a6cf94a18c1',
 '555536c84fb79a6cf94a18c0', '555536c84fb79a6cf94a18bf', '555536c84fb79a6cf94a18be',
  '555536c84fb79a6cf94a18bd', '555536c84fb79a6cf94a18bc']"

    transfer_url.log:发送内容的记录日志
    trans_url.log:处理能力的记录日志


    Start Time:2014-12-03 11:22:16                      开始时间
    send to:http://101.251.97.251/content/refresh       发送接口
    send total urls: 10                                 发送条数
    create process:5                                    创建进程数
    code:num
    200:6                                               返回状态码及相应次数（也可以体现出发送的包数，同一用户放一个包）
    500:1
    error list:                                          错误列表
    total time:0:00:02.289800                            耗时

"""
__ver__ = '1.0'

import urllib.request, urllib.parse, urllib.error
import logging
import sys
# from core import database
import multiprocessing
import simplejson as json
import string
import datetime
import collections
import os
#from pymongo import ReplicaSetConnection, ReadPreference, Connection
from core import redisfactory
import traceback
# try:
#     from pymongo import Connection as mongo
# except:
#     from pymongo import MongoClient as mongo
from core import database





imp.reload(sys)
sys.setdefaultencoding('utf8')

LOG_FILENAME = '/Application/bermuda3/logs/transfer_url.log'
COUNT_LOG_FILENAME = '/Application/bermuda3/logs/trans_url.log'
logging.basicConfig(filename=LOG_FILENAME,format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s',
                    level=logging.INFO)
# SEND_URL = "http://101.251.97.251/internal/refresh"
SEND_URL_LIST = ["http://101.251.97.251/content/refresh"]#, "http://101.251.97.214/content/refresh"
#SEND_URL_LIST = ["http://223.202.52.83/content/refresh"]
#SEND_URL_LIST = ["http://223.202.52.43/content/refresh"]

LIMIT = 500
logger = logging.getLogger('transfer_url')
logger.setLevel(logging.DEBUG)
BATCH_SIZE = 100
STRLEN = 18
#db = ReplicaSetConnection('%s:27017,%s:27017,%s:27017' % ('172.16.12.136', '172.16.12.135', '172.16.12.134'), replicaSet ='bermuda_db')['bermuda']
# db = mongo('%s:27017,%s:27017,%s:27017' % ('172.16.12.136', '172.16.12.135', '172.16.12.134'), replicaSet ='bermuda_db')['bermuda']
db = database.query_db_session()
# db = database.query_db_session()
# db = mongo("223.202.52.134", 27017)['bermuda']
json_file = "/Application/bermuda3/user.json"
uid_queue = multiprocessing.Queue()
rid_queue = multiprocessing.Queue()
rid_list = []
uid_list = []

temp_cache = redisfactory.getDB(7)


def init_user():
    #涉及到验证，线上不能直访问接口，需要单独在本地运行，写入库内用户信息
    try:
        logger.debug("init_user begining...")
        CUSTOMERS_URL = "http://portal.chinacache.com/api/internal/account/getAllAccount.do"
        users = json.loads(urllib.request.urlopen(CUSTOMERS_URL).read())
        db.user_password.remove()
        db.user_password.insert([{"name":user.get('name'), 'apipwd':user.get('apipwd'),"status":user.get('status'),"user_id":user.get('customerCode'),"accountType":user.get('accountType')} for user in users])
        logger.debug("init_user end.")
    except Exception:
        logger.warning('init_user work error:%s' % traceback.format_exc())


def write_count_log(content):
    log_file = COUNT_LOG_FILENAME
    f = file("%s" % log_file, "a")
    f.write(str(content) + "\r\n")
    f.flush()
    f.close()


# def process_return(code, content):
#     try:
#         co = json.loads(content)
#         if "invalid_urls" in co.keys():
#             fail_queue.put(co["error_urls"])
#     except Exception, ex:
#         logger.debug(ex)
#         logger.debug(content)
#         co = content
#     code_queue.put(code)
#
#     return code, content


def do_post(query, user_dic, send_url):
    """
    发送任务
    :param query: 结果集
    :param user_dic: 用户字典
    """
    username_dic = {}
    logger.debug('process to :%s ' % (query.count(True)))
    for u in query:
        if u['username'] not in list(user_dic.keys()):
            logger.debug('{0} not in user.json'.format(u['username']))
            # fail_queue.put(u['url'])
            continue
        # uid_list.append(u['_id'])
        uid_queue.put(str(u['_id']))
        if u['username'] not in list(username_dic.keys()):
            username_dic[u['username']] = ["%s" % u['url']]
        else:
            url_list = username_dic[u['username']]
            if len(url_list) < 100:
                url_list.append("%s" % u['url'])
                username_dic[u['username']] = url_list
            else:
                logger.debug('send to :%s ' % (len(username_dic[u['username']])))
                logger.debug(username_dic[u['username']])
                params = urllib.parse.urlencode({'username': u['username'],
                                           'password': user_dic[u['username'].encode('utf8')],
                                           'isSub': 'True',
                                           'task': '{"urls":["%s"]}' % '","'.join(username_dic[u['username']])})
                f = urllib.request.urlopen(send_url, params)
                # logger.debug(params)
                # logger.debug(process_return(f.code, f.read()))
                res = f.read()
                if f.code == 200:
                    re = eval(res)
                    rid_list.append(re['r_id'])
                    rid_queue.put(re['r_id'])
                username_dic.pop(u['username'])
    for key, value in list(username_dic.items()):
        logger.debug('send to {0}'.format(len(value)))
        logger.debug(value)
        params = urllib.parse.urlencode({'username': key, 'password': user_dic[key.encode('utf8')], 'isSub': 'True',
                                   'task': '{"urls":["%s"]}' % '","'.join(value)})
        # logger.debug(params)
        response  = urllib.request.urlopen(send_url, params)
        # logger.debug(process_return(response.code, response.read()))
        res = response.read()
        if response.code == 200:
            re = eval(res)
            rid_queue.put(re['r_id'])


def format_string(sstrs):
    return string.ljust(sstrs, STRLEN)


class Transfer(object):
    def __init__(self, collection, limit, filter):
        self.collection = collection
        self.limit = limit
        self.filter = filter
        self.querys = ''
        # self.end_date = datetime.datetime.combine(end_date, datetime.time())
        self.u_dic = {}
        self.user_dic = {}


    def get_users_from_filse(self):
        """
        读取JSON文件内的用户

        """
        with open(json_file, 'r+') as f_user:
            self.user_dic = json.loads(f_user.read())
        # print USER_DIC

    def get_users(self):
        users = db.user_password.find({},{'name':1,'apipwd':1})
        for user in users:
            self.user_dic[user['name']]=user['apipwd']


    def get_urls(self):
        """
        获取URLS

        """
        logger.debug('get task :%s ' % (self.limit))
        self.querys = self.collection.find({"status":{"$in":["FINISHED", "FAILED"]}}, {'username': 1, 'url': 1, '_id': 1}).sort("created_time", -1).limit(
            self.limit)

    def merg_urls(self):
        pass

    def send_url(self, send_url):
        """
        发送任务到指定的URL
        :param send_url: 指定的URL
        """
        username_dic = {}  # 合并任务包，一个包不超过100条url
        # print dir(self.querys)
        querys = copy.copy(self.querys)
        self.code_dic = collections.defaultdict(int)
        # print id(self.querys)
        # print id(querys)
        total = querys.count(True)
        logger.debug('send to %s :%s ' % (send_url, total))
        cpus = multiprocessing.cpu_count()
        if cpus > 1:
            pc = cpus - 1
            batch_size = total /pc
        else:
            pc = total / BATCH_SIZE
            batch_size = BATCH_SIZE
        # print total, batch_size, pc
        now = datetime.datetime.now()
        for i in range(0, pc):
            skip_query = querys.skip(i * batch_size).limit(batch_size)
            # do_post(skip_query, self.user_dic)
            p = multiprocessing.Process(target=do_post, args=(skip_query, self.user_dic, send_url))
            p.start()
            p.join()
        rid_list, uid_list = self.process_queue()
        print(rid_list, uid_list)
        temp_cache.set('{0}uid'.format(datetime.datetime.now().strftime("%Y%m%d%H")), uid_list)
        temp_cache.set('{0}rid'.format(datetime.datetime.now().strftime("%Y%m%d%H")), rid_list)
        logger.debug(multiprocessing.active_children())
        logger.debug(multiprocessing.cpu_count())
        write_count_log('\r\n')
        start_content = "Start Time:{0}".format(
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        write_count_log(start_content)
        write_count_log("send to:{0}".format(send_url))
        send_content = "send total urls: {0}".format(total)
        write_count_log(send_content)
        write_count_log("create process:{0}".format(pc))
        write_count_log('total time:{0}'.format(datetime.datetime.now() - now))


    def process_queue(self):
        while not uid_queue.empty():
            uid_list.append(uid_queue.get())
            # if get_data not in self.code_dic.keys():
            # self.code_dic[get_code_data] += 1
        # write_count_log("code:num")
        # for key, value in self.code_dic.items():
        #     content = '{0}:{1}'.format(key, value)
        #     write_count_log(content)
        #
        # write_count_log("error list:")
        while not rid_queue.empty():
            # get_error_data = rid_queue.get()
            # write_count_log(get_error_data)
            rid_list.append(rid_queue.get())
        return rid_list, uid_list


def run(limit, filer_str):
    now = datetime.datetime.now()
    print('start:', now, limit, filer_str)
    logger.debug('run start:%s - %s -  %s' % (now, limit, filer_str))
    rc = Transfer(db.url, limit, filer_str)
    rc.get_urls()
    rc.get_users()
    for url in SEND_URL_LIST:
        rc.send_url(url)
    print('run end:', datetime.datetime.now() - now)
    logger.debug('run end:%s' % (datetime.datetime.now() - now))
    os._exit(0)


if __name__ == '__main__':
    filerstr = {}
    limit = LIMIT
    if len(sys.argv) > 2:
        limit = int(sys.argv[1])
        username = sys.argv[2]
        filerstr = {'username': username}
    elif len(sys.argv) > 1:
        limit = int(sys.argv[1])
    else:
        pass

    run(limit, filerstr)
    # init_user()
