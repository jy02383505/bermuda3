#-*- coding:utf-8 -*-
"""
Created on 2011-6-24

@author: li.chang
"""

import simplejson as json
from datetime import datetime
ISOTIMEFORMAT = '%Y%m%d%H%M%S'
from bson import ObjectId

import logging
logger = logging.getLogger('result_tencent')


def get_result(db_session, begin_time, end_time , username):
    urlResult = '{"ret":"0","msg":"下列是URL 更新状态列表"}\n'
    resultBody = ''
    try:
        i = 0
        for request in db_session.request.find({"username": username, "created_time": {"$gte": datetime.strptime(begin_time, ISOTIMEFORMAT), "$lte": datetime.strptime(end_time, ISOTIMEFORMAT)}}).limit(1000):
            for url in db_session.url.find({"r_id": request.get('_id')}):
                ret = getStatus(url)
                strs = '%s\t%s\t%s\t%s\t%s\t%s\t%s' % (request.get('created_time'), request.get('serial_num'), request.get('remote_addr'), url.get('url'), url.get("finish_time"), ret, getmsg(ret))
                resultBody += strs + '\n'
                i += 1
        if i == 1000:
            urlResult = '{"ret":"102","msg":"下列是URL 更新状态列表"}\n'
        urlResult += resultBody
    except Exception:
        logger.error(e)
    return urlResult


def getmsg(ret):
    if ret < 0:
        return  '未完成'
    if not ret:
        return '完成'


def getStatus(url):
    if url["status"] == 'FINISHED':
        status = 0
    else:
        status = -1
    return status
