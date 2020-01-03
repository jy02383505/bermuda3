#! -*- coding=utf-8 -*-
"""
@version: ??
@author: rubin
@license:
@contact: longjun.zhao@chinacache.com
@site: 
@software: PyCharm
@file: preload_webluker.py
@time: 17-8-4 下午3:31
"""
from celery.task import task
from core import redisfactory, database
from core.config import config
from util import log_utils
logger = log_utils.get_preload_Logger()
import traceback
from datetime import datetime
import simplejson as json
import urllib.request, urllib.error, urllib.parse

s1_db = database.s1_db_session()
# USERNAME_URL_CACHE = redisfactory.getDB(14)
#
# PREFIX = 'WEBLUKER_USERNAME_URL_'

@task(ignore_result=True, default_retry_delay=10, max_retries=3)
def task_forward(data, username):
    '''
    任务转发第三方
    '''
    try:
        forward_url = config.get('task_forward', 'forward_ip_preload')

        username = username
        tasks = data
        urls = []
        task_ids = []
        records = []
        post_data = {}
        post_data['username'] = username
        post_data['tasks'] = data


        for k in tasks:
            # if not k.get('id'):
            #     raise
            # if not k.get('url'):
            #     raise
            task_ids.append(str(k.get('id')))
            urls.append(k.get('url'))
            records.append({'type':'preload','created_time':datetime.now(), 'task_id': k.get('id'), 'url': k.get('url'),
                            'username': username, 'both': k.get('both')})

        # if not task_ids or not urls:
        #     raise
        try:
            # post_data {"username": xxxx, "tasks": [{"id":xxx, "url": xxxx}]}
            res = None
            headers = {"Content-type":"application/json"}
            data = json.dumps(post_data)
            logger.debug('task_forward  post data to webluker data:%s' % data)
            req = urllib.request.Request(forward_url, data, headers)
            response = urllib.request.urlopen(req, timeout=10)
            res = response.read()
        except Exception:
            logger.debug('task_forward communicate webluker error:%s' % traceback.format_exc())

        for r in records:
            r['res'] = res

        s1_db.task_forward.insert_many(records)

        logger.debug('trans res %s'%(res))
        return res

    except Exception:
        logger.debug('trans error %s'%(e))


if __name__ == "__main__":
    pass