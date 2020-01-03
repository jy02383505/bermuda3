#! -*- coding=utf-8 -*-
"""
@version: ??
@author: rubin
@license:
@contact: longjun.zhao@chinacache.com
@site: 
@software: PyCharm
@file: webluker_tools.py
@time: 17-7-17 下午8:50
"""

import simplejson as json
from core.config import config
from util import log_utils
logger = log_utils.get_receiver_Logger()
import traceback
import urllib.request, urllib.error, urllib.parse
from datetime import datetime
import time
from core import database
from core import redisfactory
from core.generate_id import ObjectId
# import copy
# import logging

db_s1 = database.s1_db_session()
db = database.query_db_session()


# LOG_FILENAME = '/Application/bermuda3/logs/webluker_tools.log'
# # logging.basicConfig(filename=LOG_FILENAME, format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s', level=logging.INFO)
# formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s")
# fh = logging.FileHandler(LOG_FILENAME)
# fh.setFormatter(formatter)
#
# logger = logging.getLogger('webluker')
# logger.addHandler(fh)

USERNAME_URL_CACHE = redisfactory.getDB(14)

PREFIX = 'WEBLUKER_USERNAME_URL_'

def post_data_to_webluker(data, task_all, r_id):
    """

    Args:
        data: {"username": xxxx,
               'urls': ['asdf', 'http://www.baidu.com/1.html'],
               'dirs': ['http://www.baidu.com/', 'http://www.baidu.com/2/']}

    Returns:message{'r_id': '12342342342safsfd'}
    """
    import random
    message = {}
    res = None
    # send_data = copy.deepcopy(data)

    data_post = json.dumps(data)
    try:
        requrl = config.get('task_forward', 'forward_ip_refresh')
        logger.debug("post_data_to_webluker requrl:%s" % requrl)
    except Exception:
        logger.debug('get config error:%s' % traceback.format_exc())
        #requrl = 'http://223.202.202.37/nova/domain/refresh/'#
        requrl = 'http://api.novacdn.com/nova/domain/refresh/'


    try:
        # requrl = url_domain + "/nova/domain/refresh/"
        req = urllib.request.Request(url=requrl, data=data_post, headers={'Content-type': 'application/json'})
        res_data = urllib.request.urlopen(req, timeout=10)
        res = res_data.read()
        logger.debug("post data to webluker  data:%s, res:%s" % (data, res))
    except Exception:
        logger.debug('webluker urlopen  error:%s' % traceback.format_exc())

    if res:
        try:
            task_id_web = json.loads(res).get('result_desc').get('requestID')
            logger.debug('post_data_to_webluker  get data success r_id:%s' % message.get('r_id'))
        except Exception:
            logger.debug('post_data_to_webluker error %s' % traceback.format_exc())
            task_id_web = str(ObjectId())
    else:
        logger.debug('post data to webluker error, can  not get data from webluker')
        task_id_web = str(ObjectId())
    # insert data into mongo
    mongo_data = {}
    mongo_data['task_id'] = task_id_web
    mongo_data['urls'] = task_all.get('urls')
    if task_all.get('update_urls'):
        mongo_data['urls'].extend(task_all.get('update_urls'))
    mongo_data['dirs'] = task_all.get('dirs')
    if task_all.get('purge_dirs'):
        mongo_data['dirs'].extend(task_all.get('purge_dirs'))
    mongo_data['urls_webluker'] = data.get('urls')
    mongo_data['dirs_webluker'] = data.get('dirs')
    mongo_data['username'] = data.get('username')
    mongo_data['created_time'] = datetime.now()
    mongo_data['type'] = 'refresh'
    mongo_data['res'] = res

    mongo_data['finish_time'] = datetime.fromtimestamp(time.time() +
                            random.randint(15, 30))

    try:
        db_s1.task_forward.insert(mongo_data)
        if not r_id:
            insert_data = {}
            insert_data['username'] = mongo_data['username']
            insert_data['task_id'] = mongo_data['task_id']
            insert_data['created_time'] = datetime.now()
            insert_data['_id'] = ObjectId()
            message['r_id'] = str(insert_data['_id'])
            db.request.insert(insert_data)
        else:
            message['r_id'] = str(r_id)
            # import time
            # time.sleep(3)
            db.request.update_one({"_id": ObjectId(r_id)}, {'$set': {'task_id': mongo_data['task_id']}})

        logger.debug('insert task_forward  success task_id %s' % mongo_data['task_id'])
    except Exception:
        logger.debug('insert task_forward error task_id:%s, error:%s' %(message.get('r_id'), traceback.format_exc()))
    return message


def get_domain_from_url(url):
    """

    Args:
        url: http://www.baidu.com/123.html

    Returns:

    """
    if not url:
        return ""
    try:
        array_url = url.split('/')
        if len(array_url) >= 3:
            return array_url[0] + "//" + array_url[2]
    except Exception:
        logger.debug('get_domain_from_url error:%s, url:%s' % (traceback.format_exc(), url))
        return ""



def get_urls(username, urls):
    """

    Args:
        username: the name of user
        urls: ['http://www.baiud.com/123.html', 'http://www.baidu1.com/1234.html']

    Returns:['xxxxxxx', 'xxxxxxxx'], ['xxxxx', 'xxxxxx']

    """
    if not urls:
        return [], []
    if len(urls) <= 0:
        return [], []
    urls_cc = []
    urls_web = []
    for url in urls:
        domain = get_domain_from_url(url)
        # opts = USERNAME_URL_CACHE.hget(PREFIX + username, domain)
        opts = USERNAME_URL_CACHE.get(PREFIX + domain)
        logger.debug("get_urls  keys:%s, values:%s" % (PREFIX + domain, opts))
        #if not opts :#20180426
        if not opts or 'CC' == opts:
            urls_cc.append(url)
        elif 'CC' in opts.split(','):
            urls_cc.append(url)
            urls_web.append(url)
        else:
            urls_web.append(url)
    return urls_cc, urls_web


def get_urls_preload(username, urls):
    """

    Args:
        username: the name of user
        urls: [{'url': xxx, 'id': xxxx}]

    Returns:[{'url':xxx, 'id': xxx}, {'url': xxx, 'id': xxxx}], [{'url':xxx, 'id': xxx}, {'url': xxx, 'id': xxxx}]

    """
    if not urls:
        return [], []
    urls_cc = []
    urls_web = []
    for url_t in urls:
        url = url_t.get('url')
        if not url:
            continue
        domain = get_domain_from_url(url)
        opts = USERNAME_URL_CACHE.get(PREFIX + domain)
        logger.debug(" webluker_tools get_urls_preload get_urls   domain:%s, values:%s" % (domain, opts))
        
        if not opts or opts.strip() == 'CC':
            urls_cc.append({'url': url, 'id': url_t.get('id')})
        elif 'CC' in opts.split(','):
            urls_cc.append({'url': url, 'id': url_t.get('id')})
            urls_web.append({'url': url, 'id': url_t.get('id'), 'both': True})
        else:
            urls_web.append({'url': url, 'id': url_t.get('id'), 'both': False})
    return urls_cc, urls_web



if __name__ == "__main__":
    pass
