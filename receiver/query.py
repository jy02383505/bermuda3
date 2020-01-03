# -*- coding:utf-8 -*-
import logging
import time
from datetime import datetime

from flask import Blueprint, request, make_response, jsonify
import simplejson as json
import pymongo
from bson import ObjectId
from werkzeug.exceptions import NotFound, Forbidden
from util import log_utils
from core import redisfactory, authentication, database
from core.query_result import get_search_result_by_rid, get_urlStatus, get_search_result_by_rid_autodesk_new
from .query_utils import query_all_result
from . import adapters
from core.config import config
import traceback


# logger = logging.getLogger('receiver')
# logger.setLevel(logging.DEBUG)
logger = log_utils.get_receiver_Logger()
query = Blueprint('query', __name__, )

result_cache = redisfactory.getDB(3)
query_db_session = database.query_db_session()


@query.route("/content/refresh/<rid>", methods=['GET'])
def search(rid):
    username = request.args.get('username', '')
    password = request.args.get('password', '')
    ticket = authentication.verify(
        username, password, request.remote_addr)
    # try:
    #     user_list = eval(config.get('task_forward', 'usernames'))
    # except Exception, e:
    #     logger.debug('splitter_new submit error:%s' % traceback.format_exc())
    #     user_list = []
    logger.debug("/content/refresh/  search rid:%s, username:%s, remote_addr:%s" % (rid, username, request.remote_addr))
    results = get_search_result_by_rid(rid, username)


    return make_response(json.dumps(results))

@query.route("/content/refresh/search_api", methods=['POST'])
def refresh_Search_Api():

    openapi_flag = request.headers.get('X-Forwarded-Host').strip() if request.headers.get('X-Forwarded-Host') else ''
    request_data = request.args.to_dict()
    username = request_data.get('cloud_user_name', '')  # 用户名（portal中的用户名）
    user_type = request_data.get('cloud_user_type','')  # 用户类型（MAIN 为主帐户(0)，INTERNAL 为内部帐户（1），GROUP 为集团帐户(2)，FEATURE 为功能帐户(3)）
    cloud_client_name = request_data.get('cloud_client_name', '')  # 客户名（主账户）
    logger.debug('query_task_api data: %s|| remote_addr: %s|| openapi_flag: %s' % (
    request.data, request.remote_addr, openapi_flag))
    task = json.loads(request.data)
    rid = task.get('r_id')
    logger.debug("/content/refresh/  search rid:%s, username:%s, remote_addr:%s" % (rid, username, request.remote_addr))

    results = get_search_result_by_rid(rid, username)
    return make_response(json.dumps(results))

@query.route("/content/refresh_dev/<rid>", methods=['GET'])
def search_dev(rid):
    username = request.args.get('username', '')
    password = request.args.get('password', '')
    # ticket = authentication.verify(
    #     username, password, request.remote_addr)
    results = get_search_result_by_rid(rid, username)
    return make_response(json.dumps(results))


@query.route("/content/refresh_custom/<rid>", methods=['GET'])
def search_autodesk(rid):
    username = request.args.get('username', '')
    password = request.args.get('password', '')
    logger.debug('query autodesk rid:%s, request.args:%s' % (rid, request.args))
    ticket = authentication.verify(
        username, password, request.remote_addr)
    results = get_search_result_by_rid_autodesk_new(rid, username)
    return make_response(json.dumps(results))

@query.route("/refresh/result/<rid>", methods=['GET'])
def refresh_query(rid):
    username = request.args.get('username', '')
    password = request.args.get('password', '')
    ticket = authentication.verify(
        username, password, request.remote_addr)
    results = get_search_result_by_rid(rid, username)
    res = make_response(json.dumps(results))
    res.headers['Content-Type'] = 'application/json'
    return res

@query.route("/adapter/snda_refresh/<rid>", methods=['GET', 'POST'])
def snda_search(rid):
    '''
    盛大查询
    '''
    username = request.form.get('username', '')
    password = request.form.get('password', '')
    time = request.form.get('time', '')

    p_password = adapters.verify_snda(username,password, time)
    if not p_password:
        return jsonify({"success": False, "message": "WRONG_PASSWORD"}),403

    #TODO 测试
    #p_password = 'ptyy@snda.com'
    ticket = authentication.verify(
        username, p_password, request.remote_addr)

    results = get_search_result_by_rid(rid, username)
    return make_response(json.dumps(results))


@query.route("/content/refresh", methods=['GET'])
def search_by_request():
    ticket = authentication.verify(
        request.args.get('username'), request.args.get('password'), request.remote_addr)
    result = []
    if ticket.get('isSub', False):
        query = {'username': ticket.get("name")}
    else:
        query = {'parent': ticket.get("parent")}
    for refresh_request in query_db_session.request.find(query).sort('created_time', pymongo.DESCENDING).limit(20):
        totalTime = (refresh_request.get('finish_time', datetime.now())
                     - refresh_request.get('created_time')).seconds
        urlStatus = [get_urlStatus(u)
                     for u in query_db_session.url.find({"r_id": refresh_request.get('_id')})]
        successCount = len([u for u in urlStatus if u.get('code') == 200])
        result.append({
            'r_id': str(refresh_request.get('_id')),
            'status': 'UNKNOWN' if refresh_request.get('status') == 'PROGRESS' else 'SUCCESS',
            'createdTime': str(refresh_request.get('created_time')),
            'finishedTime': str(refresh_request.get('finish_time')) if refresh_request.get('finish_time') else None,
            'successRate': 1 if successCount == len(urlStatus) else float(successCount) / len(urlStatus),
            'totalTime': totalTime,
            'username': request.args.get('username', ''),
            'urlStatus': urlStatus
        })
    return make_response(json.dumps(result))


@query.route("/content/refresh/search", methods=['GET'])
def search_by_condition():
    ticket = authentication.verify(
        request.args.get('username'), request.args.get('password'), request.remote_addr)
    condition = json.loads(request.args.get('condition', {}))
    if ticket.get('isSub', False):
        query = {'username': ticket.get("name"), "created_time": {}}
    else:
        query = {'parent': ticket.get("parent"), "created_time": {}}
    if condition.get('begin'):
        query["created_time"]["$gte"] = datetime.strptime(
            condition.get('begin'), '%Y%m%d%H%M%S')
    if condition.get('end'):
        query["created_time"]["$lte"] = datetime.strptime(
            condition.get('end'), '%Y%m%d%H%M%S')
    result = []
    for refresh_request in query_db_session.request.find(query).limit(100):
        totalTime = (refresh_request.get('finish_time', datetime.now())
                     - refresh_request.get('created_time')).seconds
        urlStatus = [get_urlStatus(u) for u in query_db_session.url.find(
            {"url": {"$regex": condition.get('url', '')}, "r_id": refresh_request.get('_id')})]
        if not urlStatus:
            continue
        successCount = len([u for u in urlStatus if u.get('code') == 200])
        result.append({
            'r_id': str(refresh_request.get('_id')),
            'status': 'UNKNOWN' if refresh_request.get('status') == 'PROGRESS' else 'SUCCESS',
            'createdTime': str(refresh_request.get('created_time')),
            'finishedTime': str(refresh_request.get('finish_time')) if refresh_request.get('finish_time') else None,
            'successRate': 1 if successCount == len(urlStatus) else float(successCount) / len(urlStatus),
            'totalTime': totalTime,
            'username': request.args.get('username', ''),
            'urlStatus': urlStatus
        })
    return make_response(json.dumps(result))


@query.route("/adapter/encrypt/<rid>", methods=['GET'])
def adapter_encrypt_search(rid):
    if adapters.is_verify_encrypt_search_failed(rid, request.args.get("v")):
        raise Forbidden("verify failed.")
    else:
        result = result_cache.get(rid)
        if not result:
            refresh_request = query_db_session.request.find_one(
                {'_id': ObjectId(rid)})
            if refresh_request:
                totalTime = (refresh_request.get('finish_time', datetime.now())
                             - refresh_request.get('created_time')).seconds
                urlStatus = [get_urlStatus(u)
                             for u in query_db_session.url.find({"r_id": ObjectId(rid)})]
                successCount = len(
                    [u for u in urlStatus if u.get('code') == 200])
                result = {
                    'r_id': rid,
                    'status': 'UNKNOWN' if refresh_request.get('status') == 'PROGRESS' else 'SUCCESS',
                    'createdTime': str(refresh_request.get('created_time')),
                    'finishedTime': str(refresh_request.get('finish_time')) if refresh_request.get(
                        'finish_time') else None,
                    'successRate': 1 if successCount == len(urlStatus) else float(successCount) / len(urlStatus),
                    'totalTime': totalTime,
                    'username': refresh_request.get('username', ''),
                    'urlStatus': urlStatus
                }
                if result.get('status') == 'SUCCESS':
                    result_cache.set(rid, json.dumps(result))
                    result_cache.expire(rid, 300)
            else:
                raise NotFound('%s not found.' % rid)
        else:
            result = json.loads(result)
        return jsonify(result)


def get_request_task(db_request, url_str):
    db_urls = [url for url in query_db_session.url.find(
        {"r_id": db_request.get("_id"), 'url': {'$regex': url_str}}).sort('created_time', pymongo.DESCENDING)]
    if not db_urls:
        return {}
    progress = len([url for url in db_urls if url.get("status") in ["FINISHED", "FAILED"]]) * \
               100 / len(db_urls)
    if db_request.get("finish_time"):
        elapsedTime = int(time.mktime(db_request.get("finish_time").timetuple())
                          - time.mktime(db_request.get("created_time").timetuple()))
    else:
        elapsedTime = 0
    ##change stauts by ma
    no_finish_url = [url for url in db_urls if url.get("status") not in ["FINISHED"]]
    req_status = db_request.get('status')
    if not no_finish_url:
        req_status = "FINISHED"
    #########################
    task = {
        "id": str(db_request.get('_id')), "status": req_status, "progress": progress,
        "customerName": db_request.get("username"),
        "submitTime": db_request.get("created_time").strftime('%Y-%m-%d %H:%M:%S'),
        "finishTime": db_request.get("finish_time").strftime('%Y-%m-%d %H:%M:%S') if elapsedTime else '',
        "elapsedTime": elapsedTime,
        "urls": [{"urlID": str(url.get("_id")), "url": url.get("url")} for url in db_urls if not url.get("isdir")],
        "dirs": [{"urlID": str(url.get("_id")), "url": url.get("url")} for url in db_urls if url.get("isdir")]}
    return task


@query.route("/internal/search", methods=['GET', 'POST'])
def internal_search():
    """
    提供给portal获取任务的接口
    {"customerName":"Zhezi",
    "endTime":"2014-07-23 23:59",
    "limitCount":15,
    "startCount":1,
    "startTime":"2014-07-23 00:00",
    "status":null,
    "url":"http://www.zhezi.com/index.html"}
        :return:

        "taskList":[
    {
    "status":"FINISHED",
    "submitTime":"2014-07-23 19:01:56",
    "elapsedTime":1695,
    "finishTime":"2014-07-23 19:30:11",
    "customerName":"Zhezi",
    "urls":[
    {
    "url":"http://www.zhezi.com/index.html",
    "urlID":"53cf96242489db0d5db00a6f"
    },
    {
    "url":"http://www.zhezi.com/index.html",
    "urlID":"53cf96242489db0d5db00a6d"
    }
    ],
    "progress":100,
    "dirs":[
    ],
    "id":"53cf96242489db3206d03752"
    },
    """
    try:
        request_data = json.loads(request.data)
        if request_data.get('isSub', False):
            query = {'username': request_data.get("customerName"), 'created_time': {"$gte": datetime.strptime(
                request_data.get('startTime'), '%Y-%m-%d %H:%M'), "$lte": datetime.strptime(
                request_data.get('endTime'), '%Y-%m-%d %H:%M')}}
        else:
            query = {'parent': request_data.get("parent", request_data.get("customerName")),
                     'created_time': {"$gte": datetime.strptime(
                         request_data.get('startTime'), '%Y-%m-%d %H:%M'), "$lte": datetime.strptime(
                         request_data.get('endTime'), '%Y-%m-%d %H:%M')}}
        if request_data.get('status'):
            query['status'] = request_data.get('status')
        query_url = request_data.get('url', '')
        start_count = request_data.get('startCount', 1) - 1
        limit_count = request_data.get('limitCount', 0)
        total_count = 0
        if not query_url:
            db_requests = [db_request for db_request in query_db_session.request.find(query,
                                                                                      {"_id": True, "username": True,
                                                                                       "created_time": True,
                                                                                       "finish_time": True,
                                                                                       'status': True}).sort(
                'created_time', pymongo.DESCENDING).skip(start_count).limit(limit_count)]
            total_count = query_db_session.request.find(query).count()
        else:
            db_requests = [db_request for db_request in query_db_session.request.find(query,
                                                                                      {"_id": True, "username": True,
                                                                                       "created_time": True,
                                                                                       "finish_time": True,
                                                                                       'status': True}).sort(
                'created_time', pymongo.DESCENDING)]
        task_list = []
        for db_request in db_requests:
            task = get_request_task(db_request, query_url)
            if task:
                task_list.append(task)
        result = {"totalTaskCount": len(task_list),
                  "taskList": task_list[start_count:start_count + limit_count]} if query_url else {
            "totalTaskCount": total_count, "taskList": task_list}
        return jsonify(result)
    except Exception:
        logger.debug("internal_search error:%s" % e)
        return jsonify({"totalTaskCount": 0, "taskList": []})


@query.route("/internal/search_task/<r_id>", methods=['GET', 'POST'])
def internal_search_task(r_id):
    try:
        db_request = query_db_session.request.find_one({"_id": ObjectId(r_id)})
        if db_request.get("finish_time"):
            elapsedTime = int(time.mktime(db_request.get("finish_time").timetuple())
                              - time.mktime(db_request.get("created_time").timetuple()))
        else:
            elapsedTime = 0
        urls = [url for url in
                query_db_session.url.find({"r_id": db_request.get("_id")}).sort('created_time', pymongo.DESCENDING)]
        result = {
            "id": r_id, "status": db_request.get("status"), "customerName": db_request.get("username"),
            "submitTime": db_request.get("created_time").strftime('%Y-%m-%d %H:%M:%S'),
            "finishTime": db_request.get("finish_time").strftime('%Y-%m-%d %H:%M:%S') if elapsedTime else '',
            "elapsedTime": elapsedTime,
            "urls": [get_url_result(url) for url in urls if not url.get('isdir')],
            "dirs": [get_url_result(url) for url in urls if url.get('isdir')]}
        return jsonify(result)
    except Exception:
        logger.debug("internal_search_task error:%s" % e)
        return jsonify({})


def get_retry_count(url):
    """
    get Number succeed for retry device
    :rtype : int
    """
    r_db_dev = query_db_session.retry_device.find_one(
        {"_id": url.get("r_dev_id")})
    sucessDeviceCount = len(
        [rdev for rdev in r_db_dev.get("devices", []) if rdev.get('code') in [200, 204]]) if r_db_dev else 0
    return sucessDeviceCount


def get_url_result(url):
    db_dev = query_db_session.device.find_one(
        {"_id": url.get("dev_id")})
    totalDeviceCount = len(db_dev.get("devices", [])) if db_dev else 0
    failDeviceCount = len(
        [dev for dev in list(db_dev.get("devices", []).values()) if dev.get('code') in [503, 404, 408]]) if db_dev else 0
    if url.get("r_dev_id"):
        failDeviceCount = failDeviceCount - get_retry_count(url)

    result = {
        "urlID": str(url.get("_id")), "url": url.get("url"), "status": url.get("status"),
        "progress": (totalDeviceCount - failDeviceCount) * 100 / totalDeviceCount if totalDeviceCount else 0,
        "totalDeviceCount": totalDeviceCount,
        "failDeviceCount": failDeviceCount,
        "submitTime": url.get("created_time").strftime('%Y-%m-%d %H:%M:%S'),
        "finishTime": url.get("finish_time").strftime('%Y-%m-%d %H:%M:%S') if url.get("finish_time") else ''
    }
    return result


def get_retry_devices(url):
    r_db_dev = query_db_session.retry_device.find_one(
        {"_id": url.get("r_dev_id")})
    failDevices = []
    successDevices = []
    for dev in r_db_dev.get("devices"):
        if dev.get("code") in [200, 204]:
            successDevices.append(dev.get("name"))
        else:
            failDevices.append(dev.get("name"))
    result = {"successDevices": successDevices,
              "failDevices": failDevices}
    return result


@query.route("/internal/search_dev/<url_id>", methods=['GET', 'POST'])
def internal_search_dev(url_id):
    """
    获取指定URL的设备列表，包括成功与失败
    :param url_id:
    :return:
    { "successDevices":[
        {
            "deviceName":"CNC-CQ-2-3SC",
            "ip":"113.207.20.159"
        },
        {
            "deviceName":"CHN-WX-c-3SW",
            "ip":"58.215.107.181"
        }],"failDevices":[]
    }
    """
    try:
        db_url = query_db_session.url.find_one(
            {"_id": ObjectId(url_id)})
        db_dev = query_db_session.device.find_one(
            {"_id": db_url.get("dev_id")})
        retryCount = 6 if db_url.get("status") == "FAILED" else 3
        successDevices = []
        failDevices = []
        if db_url.get("r_dev_id"):
            retry_devices = get_retry_devices(db_url)
            for dev in list(db_dev.get("devices").values()):
                if dev.get("code") in [200, 204] or dev.get("name") in retry_devices["successDevices"]:
                    successDevices.append({"deviceName": dev.get("name"), "ip": dev.get("host")})
                else:
                    failDevices.append({"deviceName": dev.get("name"), "ip": dev.get("host"), "retryCount": retryCount})

        else:
            for dev in list(db_dev.get("devices").values()):
                if dev.get("code") in [200, 204]:
                    successDevices.append({"deviceName": dev.get("name"), "ip": dev.get("host")})
                else:
                    failDevices.append({"deviceName": dev.get("name"), "ip": dev.get("host"), "retryCount": retryCount})

        result = {"successDevices": successDevices, "failDevices": failDevices}
        return jsonify(result)
    except Exception:
        logger.debug("internal_search_dev error:%s" % traceback.format_exc())
        return jsonify({})


@query.route("/internal/search_failed_node_info/<url_id>", methods=['GET', 'POST'])
def internal_search_failed_node_info(url_id):
    """
    get the list of devices for the spcecified URL, the list of  failed device
    :param url_id: url Collection _id
    :return:
    { "failDevices":[
    {
    "countryCode" : "0086",
    "ispCode" : "95",
    "regionCode" : "8",
    "provinceCode" : "310000",
    "cityCode" : "0571",
    "nodeCode" : "9505714",
    }

    ]
    }
    """
    try:
        db_url = query_db_session.url.find_one(
            {"_id": ObjectId(url_id)})
        db_dev = query_db_session.device.find_one(
            {"_id": db_url.get("dev_id")})
        failed_dev = {}
        node_info = get_node_info()
        if db_url.get("r_dev_id"):
            retry_devices = get_retry_devices(db_url)
            for dev in list(db_dev.get("devices").values()):
                if dev.get("code") not in [200, 204] or dev.get("name") not in retry_devices["successDevices"]:
                    if dev.get('name') in node_info:
                        node = node_info[dev.get('name')]
                        failed_dev[node.get('nodeCode')] = node
        else:
            for dev in list(db_dev.get("devices").values()):
                if dev.get("code") not in [200, 204]:
                   if dev.get('name') in node_info:
                       node = node_info[dev.get('name')]
                       failed_dev[node.get('nodeCode')] = node

        result = {"failNodes": list(failed_dev.values())}
        return jsonify(result)
    except Exception:
        logger.debug("internal_search_failed_node_info error:%s" % traceback.format_exc())
        return jsonify({})


@query.route("/content/query_failed", methods=['POST'])
def content_query_failed():
    """
    receive data type  json:
    {
       'username': xxxx,
       'password':xxxxx,
       'start_time':'2017-07-02 18:30:41',
       'end_time': '2012-07-02 18:50:51'
    }
    require
    start_time > end_time
    end_time - start_time <= 3600 seconds
    Returns:
        json:
        {
           'msg': 'ok',

           'result': [
             {"username": xxxx, 'created_time': xxxxx, "url":xxxx, "isdir": True or False}
           ]
        }
    """
    try:
        task = json.loads(request.data)
    except Exception:
        logger.info('content  query_failed   error:%s, remote_addr' % (traceback.format_exc(), request.remote_addr))
        return json.dumps({'msg': 'error', 'info':'data is not json'})
    logger.debug('/content/query_failed  username:%s, start_time:%s, end_time:%s' % (task.get('username'),
                                        task.get('start_time'), task.get('end_time')))
    ticket = authentication.verify(task.get('username'), task.get('password'), request.remote_addr)
    try:
        start_time = task.get('start_time')
        end_time = task.get('end_time')
        if not start_time:
            return json.dumps({'msg': 'error', 'info': 'not have start_time'})
        if not end_time:
            return json.dumps({'msg': 'error', 'info': 'not have end_time'})
        start_time = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
        end_time = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
        # start_timestamp  = time.mktime(start_time.timetuple())
        # end_timestamp = time.mktime(end_time.timetuple())
        # if (end_timestamp - start_timestamp > 3600):
        #     logger.info('the interval is more than an hour')
        #     return json.dumps({'msg': 'error', 'info': 'the interval is more than an hour'})
    except Exception:
        logger.info('content query_failed get start_time  end_time error:%s' % traceback.format_exc())
        return json.dumps({'msg': 'error', 'info': 'start_time or end_time format error'})
    try:
        dev_failed_rate = float(config.get('failed_query_rate', 'dev_failed_rate'))
    except Exception:
        logger.debug('content query_failed error:%s' % traceback.format_exc())
        dev_failed_rate = 0.05
    try:
        failed_rate = float(config.get('failed_query_rate', 'failed_rate'))
    except Exception:
        logger.debug('content query_failed error:%s' % traceback.format_exc())
        failed_rate = 0.9

    # task_new = {'username': task.get('username'), 'start_time': start_time, 'end_time': end_time,
    #             'dev_failed_rate': dev_failed_rate, 'failed_rate': failed_rate}

    try:
        failed_task_result = query_db_session.failed_task.find({"username": task.get('username'),
                'created_time': {'$gte': start_time, '$lt': end_time}},
                {'username': 1, 'created_time': 1, 'url': 1, 'isdir': 1, 'failed_rate': 1}).batch_size(50)
    except Exception:
        logger.debug('query failed_task error:%s' % traceback.format_exc())
        return json.dumps({'msg': 'error', 'info': 'get data error'})
    list_result = []
    for result in failed_task_result:
        if result.get('failed_rate') > dev_failed_rate:
            del result['_id']
            del result['failed_rate']
            result['created_time'] = result['created_time'].strftime('%Y-%m-%d %H:%M:%S')
            list_result.append(result)
    list_result = list_result[:int(len(list_result)*failed_rate)]

    # result = get_failed_result(task_new)
    return json.dumps({"msg": 'ok', 'result': list_result})



@query.route("/query/all_refresh_content", methods=['POST'])
def query_all_refresh_content():
    """
    this interface is for bre at this moment
    json {'channel_name': xxxx, 'url': xxxxx, 'start_time':xxxxx, 'end_time':xxxxx}
    Returns:{
          'msg': 'ok',
        data: [{
         'username':xxxx,
         'url':xxxx,
         'isdir': False or True,
         'status': FAILED OR FINISHED OR PROGRESS OR INVALID OR TIMER,
         'created_time': xxxxx,
         'finish_time': xxxxx,
         'devices':  [
                   {
                   'name': xxxxx, 'status': OPEN or SUSPEND OR ..., 'type': FC or HPCC or unknown,
                   'code':xxx, 'a_code':xxxx, 'r_code': xxxxx, 'host':'127.53.32.23', 'firstLayer': False or True
                   }
                     ],
         'sub_center_devices':[
                         {
                         'name': 'xxxx', 'status': 'xxxx', 'type': HPCC or FC or unknown,'branch_code':xxxx, (int)
                         'host': xxxxx, 'firstLayer': xxxx, 'sub_center_ip': xxx, 'create_time': xxxxxx,
                         'subcenter_return_time': xxxx
                         }
                        ]
        }]
        }
    """
    logger.debug('query_all_refreh_content request.data:%s, remote_ip:%s' % (request.data, request.remote_addr))
    request_data = None
    try:
        request_data = json.loads(request.data)
    except Exception:
        logger.debug('query_all_refresh_content  json loads error:%s, request.data:%s, remote_ip:%s'
                     % (traceback.format_exc(), request.data, request.remote_addr))
        return json.dumps({'msg': 'error', 'info': 'parse data error, data is not json'})
    channel_name = request_data.get('channel_name')
    url = request_data.get('url')
    start_time =request_data.get('start_time')
    end_time =request_data.get('end_time')
    if not channel_name and not url:
        return json.dumps({'msg': 'error', 'info': 'channel_name and url is null'})
    try:
        start_time_datetime = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
        end_time_datetime = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
    except Exception:
        logger.debug('query_all_refresh_content parse data error:%s' % traceback.format_exc())
        return json.dumps({'msg': 'error', 'info': 'the start_time and end_time format error, time is string like '
                                                   '2017-01-02 18:00:01'})
    if not start_time_datetime or not end_time_datetime:
        return json.dumps({'msg': 'error', 'info': 'start_time or end_time  is null'})
    query_condition = {}
    if channel_name:
        query_condition['channel_name'] = channel_name
    if url:
        query_condition['url'] = url
    query_condition['created_time'] = {'$gte': start_time_datetime, '$lt': end_time_datetime}
    # query_condition['start_time'] = start_time_datetime
    # query_condition['end_time'] = end_time_datetime
    return query_all_result(query_condition)






def get_node_info():
    """
    according device_app, get device info
    :return: {'WAS-HZ-4-3X2':{
                            "countryCode" : "0086",
                            "ispCode" : "95",
                            "regionCode" : "8",
                            "provinceCode" : "310000",
                            "cityCode" : "0571",
                            "nodeCode" : "9505714",
                            }
            }
    """
    device_info = []
    result_info = {}
    try:
        device_info = query_db_session.device_app.find()
    except Exception:
        logger.debug("query get_node_info  find mongo error:%s" % traceback.format_exc())
    if device_info:
        # assemble device info
        for dev in device_info:
            res = {}
            res['countryCode'] = dev.get('countryCode', '')
            res['ispCode'] = dev.get('ispCode', '')
            res['regionCode'] = dev.get('regionCode', '')
            res['provinceCode'] = dev.get('provinceCode', '')
            res['cityCode'] = dev.get('cityCode', '')
            res['nodeCode'] = dev.get('nodeCode', '')
            dev_name = dev.get('name', '')
            if dev_name:
                result_info[dev_name] = res
    return result_info



def get_urlStatus(url):
    if url.get("status") in ('FINISHED', 'FAILED'):
        return {'url': url.get('url'), 'code': 200}
    elif url.get("status") == 'INVALID' or url.get("status") == 'NO_DEVICE':
        return {'url': url.get('url'), 'code': 400}
    elif url.get("status") == 'PROGRESS':
        return {'url': url.get('url'), 'code': 0}
