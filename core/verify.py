#-*- coding:utf-8 -*-
"""
Created on 2013-2-28

@author: li.chang peng.zhou
"""
import sys
import simplejson as json
from datetime import datetime
from bson.objectid import ObjectId
from core.update import db_update
from core.query_result import get_search_result_by_rid
import logging
from . import queue
import http.client
import urllib.request
import urllib.parse
import urllib.error
import base64
from . import database
import urllib.request
import urllib.error
import urllib.parse
import traceback
import hashlib
from . import sendEmail
from .models import NTESE_DOMAIN, NTEST_PORT, PASSWORD_NTESE, USERNAME_NTESE, STATUS_UNPROCESSED
from util import log_utils
import time
from core.async_device_result import async_devices
from core import redisfactory
CALLBACK_CACHE = redisfactory.getDB(14)
prefix_callback_email_username = "CALLBACK_EMAIL_"

# logger = logging.getLogger('url_refresh')
# logger.setLevel(logging.DEBUG)

logger = log_utils.get_celery_Logger()

query_db_session = database.query_db_session()


def verify(urls, db, status='FINISHED', devs={}):
    url_status = {}
    for url in urls:
        try:
            try:
                if status == "CONFLICT":
                    new_status = "FINISHED"
                    old_status = "FAILED"
                else:
                    new_status = status
                    old_status = status
                db_update(db.url, {"_id": ObjectId(url.get("id"))},
                          {"$set": {'status': new_status, 'old_status': old_status, 'finish_time': datetime.now()}})
                url_status[url.get("id")] = new_status
            except Exception:
                logger.error('db_update error url id %s :%s' %
                             (ObjectId(url.get("id")), traceback.format_exc()))
            logger.debug("verify url successed, url_id = %s status = %s " % (url.get("id"), status))
            r_id = ObjectId(url.get("r_id"))
            db_update(db.request, {"_id": r_id}, {"$inc": {'unprocess': -1}})
            db_request = query_db_session.request.find_one({"_id": r_id})
            if not db_request.get("unprocess"):
                request_status = 'FAILED' if query_db_session.url.find(
                    {'r_id': r_id, 'status': 'FAILED'}).count() else 'FINISHED'
                try:
                    db_update(db.request, {"_id": r_id},
                              {"$set": {'status': request_status, 'finish_time': datetime.now()}})
                except Exception:
                    logger.error('db_update error request rid %s :%s' %
                                 (r_id, traceback.format_exc()))
                logger.debug("verify db successed, r_id = %s request_status = %s " %
                             (url.get("r_id"), request_status))
                if db_request.get('callback'):
                    if url.get('parent') == 'snda':
                        snda_callback(db_request.get('callback'),
                                      url.get("r_id"), url.get('username'))
                    else:
                        db_request["finish_time"] = datetime.now()
                        callback(db_request, query_db_session)
        except Exception:
            logger.debug("verify db error!, url_id = %s status = %s" % (url.get("id"), status))
    try:
        if devs:
            logger.debug("async verify")
            async_devices.delay(devs, urls, url_status)
    except Exception:
        logger.error(traceback.format_exc())


def snda_callback(callback_info, r_id, username):
    '''
    盛大回调
    '''
    try:
        callback_url = callback_info.get('url')
        if not callback_url:
            logger.debug("snda callback error not url!")
            return
        result = get_search_result_by_rid(r_id, username)

        data = {}
        data['username'] = 'snda'
        data['data'] = json.dumps(result)
        data['time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        data['password'] = hashlib.md5('snda' + 'qetsfh!3' + data.get('time')).hexdigest()

       # logger.debug('snda callback encode data %s' %(urllib.urlencode(data)))
       # logger.debug('snda callback url %s' %(callback_url))

        r = urllib.request.urlopen(callback_url, urllib.parse.urlencode(data))
        logger.debug('snda callback res %s' % (r.read()))
    except Exception:
        logger.debug("snda callback error!,  %s" % (traceback.format_exc()))


def callback(request, db):
    try:
        urlResult, emailResult = get_callback(request, db)
        logger.debug('request : %s do callback.' % request.get('_id'))
        callback = request.get('callback')
        if not CALLBACK_CACHE.exists(prefix_callback_email_username + request.get('username')):
            if callback.get('email'):
                email = [
                    {"username": request.get('username'), "to_addrs": callback.get('email'), "title": 'refresh callback',
                     "body": emailResult}]
                queue.put_json2('email', email)
                logger.debug('email :%s put email_queue!' % callback.get('email'))
        if callback.get('url'):
            status = doPost(callback.get('url'), urlResult)
            logger.debug('request : %s ,urlcallback status:%s.' % (request.get('_id'), status))
            if status != 200:
                for i in range(3):
                    status = doPost(callback.get('url'), urlResult)
                    logger.debug('request : %s ,urlcallback retry count:%s ,status:%s.' %
                                 (request.get('_id'), i, status))
                    if status == 200:
                        break
        if callback.get('ntease_itemid'):
            result = '<?xml version=\"1.0\" encoding=\"utf-8\" ?><fwif><item_id>%s</item_id><op_result>SUCCESS</op_result><detail>SUCCESS</detail></fwif>' % callback.get(
                'ntease_itemid')
            headers = {"Content-type": "application/x-www-form-urlencoded", "Accept": "text/xml",
                       "Authorization": "Basic " + str.strip(base64.encodestring(USERNAME_NTESE + ':' + PASSWORD_NTESE))}
            hc = http.client.HTTPConnection(NTESE_DOMAIN, NTEST_PORT, timeout=4)
            params = urllib.parse.urlencode({'content': result.encode('utf-8')})
            hc.request('POST', '/cdnreport/', params, headers)
            hc.close()
    except:
        logger.debug("r_ud:%s do callback error, callback body :%s." %
                     (request.get("_id"), request.get("callback")))


def doPost(url, urlResult):
    headers = {'content-type': 'application/json'}
    try:
        request = urllib.request.Request(url, urlResult, headers=headers)
        response = urllib.request.urlopen(request)
        logger.debug("do_post_json url:%s data: %s, code :%s." %
                     (url, urlResult, response.getcode()))
        return response.getcode()
    except Exception:
        logger.debug("do_post_json url:%s error: %s. " % (url, traceback.format_exc()))
        return 0


def get_callback(request, db):
    urls = [url for url in db.url.find({"r_id": request.get("_id")})]
    emailResult = '\nThis message is to confirm that your content purge request has been processed successfully.The details of your request are as follows:\n\tCustID:%s\n\tSubmission time:%s\n\tCompletion time:%s\n\tURL count: %s\n\n\tContent purged:\n' % (
        request.get("username"), request.get("created_time"), request.get("finish_time"), len(urls))
    urlResult = {"request_id": str(request.get('_id')), "CustID": request.get("username"), "Submission time": str(request.get(
        "created_time")), "Completion time": str(request.get("finish_time")), "URL count": len(urls), "Content purged": {"urls": []}}
    for url in urls:
        status = getmsg(getStatus(url.get("dev_id"), db))
        emailResult += '\t%s:%s\n' % (url.get("url"), status)
        urlResult["Content purged"]["urls"].append('%s:%s\n' % (url.get("url"), status))
    emailResult += '''\n\tNote that the above list will be truncated if the full list is particularly long.\n\tPlease contact us ( globalsupport@chinacache.com ) if you have any questions or require further assistance.\n\tThank you from ChinaCache Customer Support.'''
    return json.dumps(urlResult), emailResult


def getmsg(ret):
    if ret < 0:
        return 'FAIL'
    if not ret:
        return 'SUCCESS'


def getStatus(dev_id, db):
    device = db.device.find_one({"_id": dev_id})
    if not device:
        return -100
    devices = device['devices']
    status = 0
    for dev in devices:
        if devices[dev]['code'] >= 400 and devices[dev]['code'] == 0:
            status -= 1
    return status


def get_method(url):
    a, _, b = url.partition('://')
    if b:
        domain, _, method = b.partition('/')
    else:
        domain, _, method = a.partition('/')
    return domain, method


def create_dev_dict(devs, old_dev_dict={}):
    dev_dict = old_dev_dict if old_dev_dict else {}
    for dev in devs:
        dev['code'] = STATUS_UNPROCESSED
        dev_dict[dev['name']] = dev
    return dev_dict
