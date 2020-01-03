#! -*- coding=utf-8 -*-
"""
@version: ??
@author: rubin
@license:
@contact: longjun.zhao@chinacache.com
@site: 
@software: PyCharm
@file: autodesk_url_id.py
@time: 16-10-24 下午4:30
"""
from celery.task import task
import logging
from core.generate_id import ObjectId
# try:
#     from pymongo import ReplicaSetConnection as MongoClient
# except:
#     from pymongo import MongoClient
from datetime import datetime
import time
from core.update import db_update
import traceback
from core.database import db_session
from util.autodesk_postal import entrance
from util.autodesk_failed_task_dev import parse_data, parse_data_last



LOG_FILENAME = '/Application/bermuda3/logs/autodesk.log'
# LOG_FILENAME = '/home/rubin/logs/check_url_autodesk.log'
# logging.basicConfig(filename=LOG_FILENAME, format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s', level=logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s")
fh = logging.FileHandler(LOG_FILENAME)
fh.setFormatter(formatter)

logger = logging.getLogger('autodesk_url_id')
logger.addHandler(fh)
logger.setLevel(logging.DEBUG)


# conn = MongoClient('mongodb://bermuda:bermuda_refresh@223.202.52.82:27018/bermuda')
# db = conn.bermuda
db = db_session()



@task(ignore_result=True, default_retry_delay=10, max_retries=3)
def update_url_autodesk(id):
    """
    autodesk_id  queue
    rabbitmq message queue, udpate url_autodesk  status, finish_time
    :param id: the _id of url_autodesk , the _id of url
    :return:
    """
    logger.debug('update_url_autodesk id:%s' % id)
    try:
        url_result = db.url.find_one({'_id': ObjectId(id)})
        logger.debug('check_url_autodesk update_url_autodesk get data success, id:%s' % id)
    except Exception:
        logger._log('check_url_autodesk update_url_autodesk error, id:%s, %s' % (id, e))
        return
    if not url_result:
        return
    # finish url_autodesk state alter
    finish_time = datetime.now()
    finish_time_timestamp = time.mktime(finish_time.timetuple())
    try:
        db.url_autodesk.update_one({'_id': ObjectId(id)}, {'$set': {'status': url_result.get('status'), 'finish_time': finish_time,
                                'finish_time_timestamp': finish_time_timestamp, 'dev_id': url_result.get('dev_id', None),
                            'retry_branch_id': url_result.get('retry_branch_id', None)}})
        db_update(db.request, {'_id': ObjectId(url_result.get('r_id'))}, {'$inc': {'check_unprocess': -1}})
        logger.debug('update_url_autodes  request r_id:%s' % url_result.get('r_id'))
        request_result = db.request.find_one({'_id': ObjectId(url_result.get('r_id'))})
        logger.debug('update_url_autodesk request_result:%s' % request_result)
        if not request_result.get('check_unprocess'):
            finish_time_request = datetime.now()
            finish_time_request_timestamp = time.mktime(finish_time_request.timetuple())

            db_update(db.request, {'_id': ObjectId(url_result.get('r_id'))}, {'$set': {'finish_time_autodesk': finish_time_request,
                                'finish_time_autodesk_timestamp': finish_time_request_timestamp}})
        logger.debug('check_url_autodesk update_url_autodesk success id:%s' % id)
    except Exception:
        logger.debug("check_url_autodesk update_url_autodesk error, id:%s, %s" % (id, traceback.format_exc()))
        return


@task(ignore_result=True, default_retry_delay=10, max_retries=3)
def udpate_url_dev_autodesk(id, different_time):
    """

    :param id:
    :param different_time:
    :return:
    """
    logger.debug('update_url_autodesk id:%s, different_time:%s' % (id, different_time))
    try:
        url_result = db.url.find_one({'_id': ObjectId(id)})
        logger.debug('check_url_autodesk update_url_autodesk get data success, id:%s' % id)
    except Exception:
        logger._log('check_url_autodesk update_url_autodesk error, id:%s, %s' % (id, e))
        return
    if not url_result:
        return
    entrance(url_result, different_time)


@task(ignore_result=True, default_retry_delay=10, max_retries=3)
def failed_task_email(id, username, created_time):
    """

    :param id: request _id
    :param username: the name of user
    :param created_time:
    :return:
    """
    try:
        parse_data(id, username, created_time)
    except Exception:
        logger.debug('failed_task_email parse_data error:%s' % traceback.format_exc())


@task(ignore_result=True, default_retry_delay=10, max_retries=3)
def failed_task_email_other(id, username, created_time):
    """

    :param id: request _id
    :param username: the name of user
    :param created_time:
    :return:
    """
    try:
        parse_data(id, username, created_time)
    except Exception:
        logger.debug('failed_task_email parse_data error:%s' % traceback.format_exc())


@task(ignore_result=True, default_retry_delay=10, max_retries=3)
def refresh_last_hpcc_report(id, username, created_time):
    """

    :param id: request _id
    :param username: the name of user
    :param created_time:
    :return:
    """
    try:
        parse_data_last(id, username, created_time)
    except Exception:
        logger.debug('failed_task_email parse_data error:%s' % traceback.format_exc())

if __name__ == "__main__":
    pass