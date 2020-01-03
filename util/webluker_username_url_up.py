#! -*- coding=utf-8 -*-
"""
@version: ??
@author: rubin
@license:
@contact: longjun.zhao@chinacache.com
@site: 
@software: PyCharm
@file: webluker_username_url_up.py
@time: 17-7-31 下午3:51
"""



import logging
import traceback
from core.config import config
import simplejson as json
import urllib.request, urllib.error, urllib.parse
import datetime
# import redis

from core import database


from core import redisfactory

# logger = log_utils.get_receiver_Logger()
# LOG_FILENAME = '/Application/bermuda3/logs/webluker_username_url.log'
# LOG_FILENAME = '/home/rubin/logs/webluker_username_url.log'
# logging.basicConfig(filename=LOG_FILENAME,
#                     format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s',
#                     level=logging.INFO)
#
# logger = logging.getLogger('webluker_username_url')
# logger.setLevel(logging.DEBUG)

LOG_FILENAME = '/Application/bermuda3/logs/webluker_username_url_up.log'
# logging.basicConfig(filename=LOG_FILENAME, format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s', level=logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s")
fh = logging.FileHandler(LOG_FILENAME)
fh.setFormatter(formatter)

logger = logging.getLogger('webluker')
logger.addHandler(fh)
logger.setLevel(logging.DEBUG)



db = database.query_db_session()



# def getMDB(db):
#     '''
#     monitor redis
#     '''
#     pool = redis.ConnectionPool(host='223.202.203.52', port=6379, db=db, password='bermuda_refresh')
#     return redis.Redis(connection_pool=pool)



USERNAME_URL_CACHE = redisfactory.getDB(14)
# USERNAME_URL_CACHE = getMDB(14)

PREFIX = 'WEBLUKER_USERNAME_URL_'

try:
    webluker_url = config.get('webluker_username_url', 'username_url')
except Exception:
    logger.debug('content query_failed error:%s' % traceback.format_exc())
    #webluker_url = 'http://223.202.202.37/nova/get/domain/info/'
    webluker_url = 'http://api.novacdn.com/nova/get/domain/info/'


def get_data():
    """
    communicate to webluker, get data of username  url  opts
    Returns:
         {"http://m.xiu.com": {"username": "m-xiu", "channelID": "92015", "opts": ["CC", "AZURE", "TENCENT"]},
         "http://lxdqncdn.miaopai.com": {"username": "mp", "channelID": "87971", "opts": ["CC", "AZURE", "TENCENT"]}}

    """
    s_data = {}
    test_data_urlencode = json.dumps(s_data)
    requrl = webluker_url
    try:
        req = urllib.request.Request(url=requrl, data=test_data_urlencode, headers={'Content-type': 'application/json'})
        res_data = urllib.request.urlopen(req, timeout=100)
        res = res_data.read()
        logger.debug('get data from webluker res:%s' % res)
        return json.loads(res)
    except Exception:
        logger.debug('get data from webluker error:%s' % traceback.format_exc())
        return {}
    # print res


# def redis_test():
#     """
#
#     Returns:
#
#     """
#     USERNAME_URL_CACHE.hset(PREFIX + 'username1', 'url1', 'cc')
#     USERNAME_URL_CACHE.hset(PREFIX + 'username2', 'url2', 'cc')
#     print USERNAME_URL_CACHE.hgetall(PREFIX + 'username1')
#     print USERNAME_URL_CACHE.hgetall(PREFIX + 'username2')
#     print USERNAME_URL_CACHE.keys(PREFIX + '*')
#     for key in USERNAME_URL_CACHE.keys(PREFIX + '*'):
#
#         USERNAME_URL_CACHE.delete(key)



def parse_data(webluker_data):
    """

    Args:
        webluker_data:
        {"http://m.xiu.com": {"username": "m-xiu", "channelID": "92015", "opts": ["CC", "AZURE", "TENCENT"]},
         "http://lxdqncdn.miaopai.com": {"username": "mp", "channelID": "87971", "opts": ["CC", "AZURE", "TENCENT"]}}

    Returns:
        before:
        set data into redis  redis structure  username  channel  values
        set data into mongo  mongo structure   {"username": xxxx, 'domain': xxxx, 'channelID':xxxx, 'opts': xxxxx}
        now:
        set data into redis  redis structure  channel  values
        set data into mongo  mongo structure   {"username": xxxx, 'domain': xxxx, 'channelID':xxxx, 'opts': xxxxx}
    """
    if not webluker_data:
        return
    # USERNAME_URL_CACHE.delete(USERNAME_URL_CACHE + '*')
    for key in USERNAME_URL_CACHE.keys(PREFIX + '*'):
        logger.debug('parse_data redis 14 del key:%s' % key)
        USERNAME_URL_CACHE.delete(key)
    insert_mongo_data = []
    created_time = datetime.datetime.now()
    try:
        for data_t in webluker_data:
            data_temp = {}
            data_temp['created_time'] = created_time
            data_temp['domain'] = data_t
            data_temp['username'] = webluker_data.get(data_t).get('username')
            data_temp['channelID'] = webluker_data.get(data_t).get('channelID')
            data_temp['opts'] = ','.join(webluker_data.get(data_t).get('opts'))
            logger.debug("parse_data data_t:%s" % data_temp)
            #USERNAME_URL_CACHE.hset(PREFIX + data_temp['username'], data_temp['domain'], data_temp['opts'])
            USERNAME_URL_CACHE.set(PREFIX + data_t, data_temp['opts'])
            insert_mongo_data.append(data_temp)
            if len(insert_mongo_data) > 20:
                db.webluker_username_domain.insert(insert_mongo_data)
                insert_mongo_data = []
        if len(insert_mongo_data) > 0:
            db.webluker_username_domain.insert(insert_mongo_data)
    except Exception:
        logger.debug('parse_data  error:%s' % traceback.format_exc())


def main_fun():
    """

    Returns:

    """
    webluker_data = get_data()
    parse_data(webluker_data)


if __name__ == "__main__":
    # print get_data()
    # redis_test()
    pass