# -*- coding:utf-8 -*-
'''
Created on 2016-3-09

@author: junyu.guo
'''

import simplejson as json
import datetime
from core import redisfactory, database
from bson import ObjectId
import time
from util import log_utils
import traceback
from core.update import db_update
logger = log_utils.get_receiver_Logger()
# import logging
from core.config import config
import urllib.request, urllib.error, urllib.parse


# LOG_FILENAME = '/Application/bermuda3/logs/autodesk_test.log'
# # LOG_FILENAME = '/home/rubin/logs/check_url_autodesk.log'
# # logging.basicConfig(filename=LOG_FILENAME, format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s', level=logging.INFO)
# formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s")
# fh = logging.FileHandler(LOG_FILENAME)
# fh.setFormatter(formatter)
#
# logger = logging.getLogger('check_url_autodesk')
# logger.addHandler(fh)
# logger.setLevel(logging.DEBUG)

query_db_session = database.query_db_session()
db = database.db_session()
db_s1 = database.s1_db_session()

def get_search_result_by_rid(rid, username):
    '''
    根据rid查询刷新通用结果
    '''
    results = []
    result_cache = redisfactory.getDB(3)

    for rid in rid.split(','):
        result = result_cache.get(username + rid)
        if not result:
            refresh_request = query_db_session.request.find_one(
                {'username': username, '_id': ObjectId(rid)})
            logger.debug("get_search_result_by_rid refresh_request:%s" % refresh_request)
            if refresh_request and refresh_request.get('task_id'):
                result = get_search_result_by_rid_webluker_one(refresh_request.get('task_id'), username, str(rid))
            else:
                if refresh_request:
                    totalTime = (refresh_request.get('finish_time', datetime.datetime.now())
                                 - refresh_request.get('created_time')).seconds
                    urlStatus = [get_urlStatus(u)
                                 for u in query_db_session.url.find({"r_id": ObjectId(rid)})]
                    successCount = len([u for u in urlStatus if u.get('code') == 200])
                    result = {
                        'r_id': rid,
                        'status': 'UNKNOWN' if refresh_request.get('status') == 'PROGRESS' else 'SUCCESS',
                        'createdTime': str(refresh_request.get('created_time')),
                        'finishedTime': str(refresh_request.get('finish_time')) if refresh_request.get(
                            'finish_time') else None,
                        'successRate': 1 if successCount == len(urlStatus) else float(successCount) / len(urlStatus),
                        'totalTime': totalTime,
                        'username': username,
                        'urlStatus': urlStatus
                    }
                    if result.get('status') == 'SUCCESS':
                        result_cache.set(username + rid, json.dumps(result))
                        result_cache.expire(username + rid, 300)
                else:
                    result = {
                        'r_id': rid, 'msg': '%s not found.' % rid
                    }
        else:
            result = json.loads(result)
        results.append(result)
    return results



def refresh_get_data_from_webluker(rid):
    """
    get data from webluer
    :param rid:
    :return:
    {"http://wsacdn3.miaopai.com/234/": {"type": "dir", "status": "SUCCESS"},
    "http://lxqncdn.miaopai.com/": {"type": "dir", "status": "SUCCESS"},
    "http://lxqncdn.miaopai.com/123.com": {"type": "url", "status": "SUCCESS"}
    }
    """
    s_data = {"task_ids": str(rid)}
    data_urlencode = json.dumps(s_data)
    try:
        requrl = config.get('task_forward', "webluker_refresh_search")
    except Exception:
        logger.error('refresh_get_data_from_webluker error:%s' % traceback.format_exc())
        #requrl = "http://223.202.202.37/nova/get/domain/refresh/status/"
        requrl = "http://api.novacdn.com/nova/get/domain/refresh/status/"
    try:
        req = urllib.request.Request(url=requrl, data=data_urlencode, headers={'Content-type': 'application/json'})
        res_data = urllib.request.urlopen(req, timeout=10)
        res = res_data.read()
        logger.debug('get data from webluker res:%s' % res)
        result_from_webluker = json.loads(res)
        if result_from_webluker:
            url_dict = result_from_webluker.get("result_desc").get(str(rid))
            return url_dict
        return {}
    except Exception:
        print(('refresh get data from webluker error:%s' % traceback.format_exc()))
        return {}


def get_search_result_by_rid_webluker_one(rid, username, rid_r):
    """

    Args:
        rid:

    Returns:

    """
    result_cache = redisfactory.getDB(3)
    refresh_request = db_s1.task_forward.find_one({'task_id': rid})

    if refresh_request:
        created_time = refresh_request.get('created_time')
        finish_time = refresh_request.get('finish_time')
        # contrast finish_time and current time
        finish_time_timestamps = time.mktime(finish_time.timetuple())
        time_now = datetime.datetime.now()
        time_now_timestamps = time.mktime(time_now.timetuple())
        flag = True if finish_time_timestamps < time_now_timestamps else False
        if finish_time_timestamps > time_now_timestamps:
            finish_time = time_now
        totalTime = (finish_time - created_time).seconds

        # totalTime = (refresh_request.get('finish_time', datetime.datetime.now())
        #          - refresh_request.get('created_time')).seconds
        webluer_result = refresh_get_data_from_webluker(rid)
        logger.debug("get_search_result_by_rid_webluker_one webluer_result:%s" % webluer_result)
        urlStatus = get_urlStatus_webluker(webluer_result, refresh_request.get('urls'), success=flag)

        urlStatus2 = get_urlStatus_webluker(webluer_result, refresh_request.get('dirs'), success=flag)
        urlStatus.extend(urlStatus2)
        success_count = len([url for url in urlStatus if url.get("code") == 200])



        # successCount = 0 if flag else (len(refresh_request.get('urls')) + len(refresh_request))
        success_rate = 0 if len(urlStatus) == 0 else success_count/ len(urlStatus)
        result = {
            'r_id': rid_r,
            'status': 'UNKNOWN' if (success_count != len(urlStatus)) else 'SUCCESS',
            'createdTime': str(refresh_request.get('created_time')),
            'finishedTime': str(finish_time) if flag else None,
            'successRate': success_rate,
            'totalTime': totalTime,
            'username': username,
            'urlStatus': urlStatus
        }
        if result.get('status') == 'SUCCESS':
            result_cache.set(username + rid_r, json.dumps(result))
            result_cache.expire(username + rid_r, 300)
    else:
        result = {
            'r_id': rid_r, 'msg': '%s not found.' % rid_r
        }
    return result


def get_search_result_by_rid_webluker(rid, username):
    '''
    根据rid查询刷新通用结果
    '''
    results = []
    result_cache = redisfactory.getDB(3)

    for rid in rid.split(','):
        result = result_cache.get(username + rid)
        if not result:
            refresh_request = db_s1.task_forward.find_one({'task_id': rid})

            if refresh_request:
                created_time = refresh_request.get('created_time')
                finish_time = refresh_request.get('finish_time')
                # contrast finish_time and current time
                finish_time_timestamps = time.mktime(finish_time.timetuple())
                time_now = datetime.datetime.now()
                time_now_timestamps = time.mktime(time_now.timetuple())
                flag = True if finish_time_timestamps < time_now_timestamps else False
                if finish_time_timestamps > time_now_timestamps:
                    finish_time = time_now
                totalTime = (finish_time - created_time).seconds

                # totalTime = (refresh_request.get('finish_time', datetime.datetime.now())
                #          - refresh_request.get('created_time')).seconds
                urlStatus = get_urlStatus_webluker(refresh_request.get('urls'), success=flag)

                urlStatus2 = get_urlStatus_webluker(refresh_request.get('dirs'), success=flag)
                urlStatus.extend(urlStatus2)
                # successCount = 0 if flag else (len(refresh_request.get('urls')) + len(refresh_request))
                result = {
                    'r_id': rid,
                    'status': 'UNKNOWN' if not flag else 'SUCCESS',
                    'createdTime': str(refresh_request.get('created_time')),
                    'finishedTime': str(finish_time) if flag else None,
                    'successRate': 1 if flag else 0,
                    'totalTime': totalTime,
                    'username': username,
                    'urlStatus': urlStatus
                }
                if result.get('status') == 'SUCCESS':
                    result_cache.set(username + rid, json.dumps(result))
                    result_cache.expire(username + rid, 300)
            else:
                result = {
                    'r_id': rid, 'msg': '%s not found.' % rid
                }
        else:
            result = json.loads(result)
        results.append(result)
    return results




def get_search_result_by_rid_autodesk(rid, username):
    '''
    根据rid查询刷新通用结果
    '''
    results = []
    result_cache = redisfactory.getDB(3)

    for rid in rid.split(','):
        result = result_cache.get('autodesk' + username + rid)
        if not result:
            refresh_request = query_db_session.request.find_one(
                {'username': username, '_id': ObjectId(rid)})
            if refresh_request:

                finishedTime = str(refresh_request.get('finish_time_autodesk')) if refresh_request.get(
                        'finish_time_autodesk') else None
                logger.debug('test1 get_search_result_by_rid_autodesk refresh_request:%s' % refresh_request)
                if finishedTime:
                    remain_time = 0
                    # totalTime = (refresh_request.get('finish_time_autodesk', datetime.datetime.now())
                    #          - refresh_request.get('created_time')).seconds
                    # urlStatus = [get_urlStatus_autodesk(u)
                    #          for u in query_db_session.url_autodesk.find({"r_id": ObjectId(rid)})]
                    # successCount = len([u for u in urlStatus if u.get('code') == 200])
                else:
                    time_now_timestamp = time.time()
                    executed_end_time_timestamp = refresh_request.get('executed_end_time_timestamp')
                    remain_time = executed_end_time_timestamp - time_now_timestamp
                    # if remain_time bigger 30s, go to normal progress
                    if remain_time > 10:
                        pass
                        # totalTime = (refresh_request.get('finish_time_autodesk', datetime.datetime.now())
                        #      - refresh_request.get('created_time')).seconds
                        # urlStatus = [get_urlStatus_autodesk(u)
                        #      for u in query_db_session.url_autodesk.find({"r_id": ObjectId(rid)})]
                        # successCount = len([u for u in urlStatus if u.get('code') == 200])
                    else:
                        logger.debug('query db and insert data rid:%s' % rid)
                        # auto trigger change status of url_autodesk
                        update_url_request_autodesk(rid)
                        remain_time = 0
                        refresh_request = query_db_session.request.find_one({'username': username, '_id': ObjectId(rid)})
                        logger.debug('test2 get_search_result_by_rid_autodesk refresh_request:%s' % refresh_request)
                logger.debug('test3 get_search_result_by_rid_autodesk refresh_request:%s' % refresh_request)

                finishedTime = str(refresh_request.get('finish_time_autodesk')) if refresh_request.get(
                               'finish_time_autodesk') else None
                totalTime = (refresh_request.get('finish_time_autodesk', datetime.datetime.now())
                              - refresh_request.get('created_time')).seconds
                urlStatus = [get_urlStatus_autodesk(u)
                              for u in query_db_session.url_autodesk.find({"r_id": ObjectId(rid)})]
                successCount = len([u for u in urlStatus if u.get('code') == 200])
                time_now_timestamp = time.time()
                judge_status_urls = status_urls([u for u in query_db_session.url_autodesk.find({'r_id': ObjectId(rid)})])

                if not finishedTime:
                    status = 'UNKNOWN'
                    remain_time = refresh_request.get('remain_time_return_timestamp') - time_now_timestamp
                elif not judge_status_urls:
                    try:
                        if refresh_request.get('remain_time_failed_timestamp') < time_now_timestamp:
                            status = 'SUCCESS'
                            remain_time = 0
                            finishedTime = datetime.datetime.fromtimestamp(refresh_request.get('remain_time_failed_timestamp')).strftime('%Y-%m-%d %H:%M:%S')
                            totalTime = (datetime.datetime.fromtimestamp(refresh_request.get('remain_time_failed_timestamp'))
                                          - refresh_request.get('created_time')).seconds
                            logger.debug('not judge_status_urls finishedTime:%s' % finishedTime)
                        else:
                            status = 'UNKNOWN'
                            remain_time = refresh_request.get('remain_time_failed_timestamp') - time_now_timestamp
                            # finishedTime = datetime.datetime.strptime(datetime.datetime.fromtimestamp(
                            #         refresh_request.get('remain_time_failed_timestamp')), '%Y-%m-%d %H:%M:%S')
                            finishedTime = None
                            totalTime = (datetime.datetime.now() - refresh_request.get('created_time')).seconds
                            logger.debug('not judge_status_urls >, remain_time:%s, finishedTime:%s' % (remain_time, finishedTime))
                    except Exception:
                        logger.debug('get_search_result_by_rid_autodesk not judeg_status_urls error:%s' % traceback.format_exc())

                elif successCount == len(urlStatus):
                    status = 'SUCCESS'
                else:
                    status = 'FAILED'
                result = {
                    'r_id': rid,
                    'status': status,
                    'createdTime': str(refresh_request.get('created_time')),
                    'finishedTime': finishedTime,
                    'successRate': 1 if successCount == len(urlStatus) else float(successCount) / len(urlStatus),
                    'totalTime': totalTime,
                    'username': username,
                    'urlStatus': urlStatus,
                    'remain_time': remain_time
                }
                if result.get('status') == 'SUCCESS' and remain_time == 0:
                    result_cache.set('autodesk' + username + rid, json.dumps(result))
                    result_cache.expire('autodesk' + username + rid, 300)
            else:
                result = {
                    'r_id': rid, 'msg': '%s not found.' % rid
                }
        else:
            result = json.loads(result)
        results.append(result)
    return results



def get_search_result_by_rid_autodesk_new(rid, username):
    '''
    根据rid查询刷新通用结果
    '''
    results = []
    result_cache = redisfactory.getDB(3)
    refresh_result = redisfactory.getDB(5)
    for rid in rid.split(','):
        result = result_cache.get('autodesk' + username + rid)
        if not result:
            refresh_request = query_db_session.request.find_one(
                {'username': username, '_id': ObjectId(rid)})

            try:
                type_t = config.get('query_type', username)
            except Exception:
                logger.error('get_search_result_by_rid_autodesk_new get quer_type error:%s' % traceback.format_exc())
                logger.info("query_type username:%s" % username)
                type_t = "ALL"
            finishedTime = None
            if type_t == 'FC':
                finishedTime_timestamps = refresh_result.get('RID_%s_FC_F' % rid)
                if finishedTime_timestamps:
                    # transformation timestamps to datatime
                    finishedTime = datetime.datetime.fromtimestamp(float(finishedTime_timestamps))
            elif type_t == "HPCC":
                finishedTime_timestamps = refresh_result.get('RID_%s_HPCC_F' % rid)
                if finishedTime_timestamps:
                    # transformation timestamps to datatime
                    finishedTime = datetime.datetime.fromtimestamp(float(finishedTime_timestamps))
            else:
                finishedTime_timestamps_fc = refresh_result.get('RID_%s_FC_F' % rid)
                finishedTime_timestamps_hpcc = refresh_result.get('RID_%s_HPCC_F' % rid)
                if finishedTime_timestamps_fc and finishedTime_timestamps_hpcc:
                    if float(finishedTime_timestamps_fc) > float(finishedTime_timestamps_hpcc):
                        finishedTime = datetime.datetime.fromtimestamp(float(finishedTime_timestamps_fc))
                    else:
                        finishedTime = datetime.datetime.fromtimestamp(float(finishedTime_timestamps_hpcc))

            if refresh_request:


                # finishedTime = str(refresh_request.get('finish_time_autodesk')) if refresh_request.get(
                #         'finish_time_autodesk') else None
                logger.debug('test1 get_search_result_by_rid_autodesk refresh_request:%s' % refresh_request)
                # if finishedTime:
                #     remain_time = 0
                # else:
                #     time_now_timestamp = time.time()
                #     executed_end_time_timestamp = refresh_request.get('remain_time_failed_timestamp')
                #     remain_time = executed_end_time_timestamp - time_now_timestamp
                #     # if remain_time bigger 30s, go to normal progress
                #     if remain_time > 0:
                #         pass
                #     else:
                #         remain_time = 0

                logger.debug('test3 get_search_result_by_rid_autodesk refresh_request:%s' % refresh_request)
                finishedTime = str(finishedTime) if finishedTime else None
                urlStatus = [get_urlStatus_autodesk(u)
                              for u in query_db_session.url.find({"r_id": ObjectId(rid)})]
                successCount = len([u for u in urlStatus if u.get('code') == 200])
                time_now_timestamp = time.time()
                # refresh_request['remain_time_failed_timestamp'] = time.mktime(refresh_request.get('created_time').timetuple()) + float(100)
                # judge_status_urls = status_urls([u for u in query_db_session.url_autodesk.find({'r_id': ObjectId(rid)})])

                if finishedTime:
                    status = 'SUCCESS'
                    totalTime = float(finishedTime_timestamps) - time.mktime(refresh_request.get('created_time').timetuple())
                    remain_time = 0
                    # remain_time = float(finishedTime_timestamps) - time_now_timestamp
                    # remain_time = refresh_request.get('remain_time_return_timestamp') - time_now_timestamp


                elif not finishedTime:
                    try:
                        if refresh_request.get('remain_time_failed_timestamp') < time_now_timestamp:
                            status = 'SUCCESS'
                            remain_time = 0
                            finishedTime = datetime.datetime.fromtimestamp(refresh_request.get('remain_time_failed_timestamp')).strftime('%Y-%m-%d %H:%M:%S')
                            totalTime = (datetime.datetime.fromtimestamp(refresh_request.get('remain_time_failed_timestamp'))
                                          - refresh_request.get('created_time')).seconds
                            logger.debug('not judge_status_urls finishedTime:%s' % finishedTime)
                        else:
                            status = 'UNKNOWN'
                            remain_time = refresh_request.get('remain_time_failed_timestamp') - time_now_timestamp
                            finishedTime = None
                            totalTime = (datetime.datetime.now() - refresh_request.get('created_time')).seconds
                            logger.debug('not judge_status_urls >, remain_time:%s, finishedTime:%s' % (remain_time, finishedTime))
                    except Exception:
                        logger.debug('get_search_result_by_rid_autodesk not judeg_status_urls error:%s' % traceback.format_exc())

                # elif successCount == len(urlStatus):
                #     status = 'SUCCESS'
                # else:
                #     status = 'FAILED'
                result = {
                    'r_id': rid,
                    'status': status,
                    'createdTime': str(refresh_request.get('created_time')),
                    'finishedTime': finishedTime,
                    'successRate': 1 if successCount == len(urlStatus) else float(successCount) / len(urlStatus),
                    'totalTime': totalTime,
                    'username': username,
                    'urlStatus': urlStatus,
                    'remain_time': remain_time
                }
                if result.get('status') == 'SUCCESS' and remain_time == 0:
                    result_cache.set('autodesk' + username + rid, json.dumps(result))
                    result_cache.expire('autodesk' + username + rid, 300)
            else:
                result = {
                    'r_id': rid, 'msg': '%s not found.' % rid
                }
        else:
            result = json.loads(result)
        results.append(result)
    return results


def get_urlStatus(url):
    if url.get("status") in ('FINISHED', 'FAILED'):
        return {'url': url.get('url'), 'code': 200}
    elif url.get("status") == 'INVALID' or url.get("status") == 'NO_DEVICE':
        return {'url': url.get('url'), 'code': 400}
    elif url.get("status") == 'PROGRESS':
        return {'url': url.get('url'), 'code': 0}

def get_urlStatus_autodesk(url):
    if url.get("status") in ('FINISHED', 'FAILED'):
        return {'url': url.get('url'), 'code': 200}
    # elif url.get("status") == 'FAILED':
    #     return {'url': url.get('url'), 'code': 503}
    elif url.get("status") == 'INVALID' or url.get("status") == 'NO_DEVICE':
        return {'url': url.get('url'), 'code': 400}
    elif url.get("status") == 'PROGRESS':
        return {'url': url.get('url'), 'code': 201}


def get_urlStatus_webluker(webluer_result, urls, success=True):
    """

    :param webluer_result: {"http://wsacdn3.miaopai.com/234/": {"type": "dir", "status": "SUCCESS"},
            "http://lxqncdn.miaopai.com/": {"type": "dir", "status": "SUCCESS"},
            "http://lxqncdn.miaopai.com/123.com": {"type": "url", "status": "SUCCESS"}
            }
    :param urls:
    :param success:
    :return:
    """
    result = []
    if success:
        if urls:
            for url in urls:
                if url in webluer_result and webluer_result.get(url).get('status') != "SUCCESS":
                    result.append({'url': url, 'code': 0})
                else:
                    result.append({'url': url, 'code': 200})
    else:
        if urls:
            for url in urls:
                result.append({'url': url, 'code': 0})
    return result



def status_urls(urls):
    """
　　　judge urls all success or not, if the status of url is not 'FINISHED',return False, if all 'FINISHED', return True
    Args:
        urls:

    Returns:

    """
    for url in urls:
        if url.get('status') != 'FINISHED':
            logger.debug('status_urls status is not finished!')
            return False
    logger.debug('status_urls  true')
    return True



def update_url_request_autodesk(rid):
    """
    update request collection, url_autodesk,
    :param rid: the _id of request, the rid of url_autodesk
    :return:
    """
    try:
        url_autodesk_rids = query_db_session.url_autodesk.find({'r_id': ObjectId(rid)})
        logger.debug('query_result update_url_reques_autodesk, rid:%s' % rid)
    except Exception:
        logger.debug('query_result update_url_reques_autodesk error:%s' % e)
        return None
    url_data_rids = get_data_from_url_by_rid(rid)
    logger.debug('update_url_request_autodesk url_data_rids:%s' % url_data_rids)
    try:
        if url_data_rids:
            for url_autodesk_rid in url_autodesk_rids:
                logger.debug('update_url_requeset_autodesk url_autodesk_rid:%s' % url_autodesk_rid)
                id = str(url_autodesk_rid.get('_id'))
                status = url_autodesk_rid.get('status')
                if status == 'PROGRESS':
                    status = url_data_rids.get(id).get('status')
                    logger.debug('query_result  url id:%s, status:%s' % (id, status))
                    dev_id = url_data_rids.get(id).get('dev_id')
                    retry_branch_id = url_data_rids.get(id).get('retry_branch_id')
                    finish_time = datetime.datetime.now()
                    finish_time_timestamp = time.mktime(finish_time.timetuple())
                    db.url_autodesk.update_one({"_id": ObjectId(id)}, {'$set': {'status': status,
                                'finish_time': finish_time, 'finish_time_timestamp': finish_time_timestamp,
                                 'dev_id': dev_id, 'retry_branch_id': retry_branch_id, 'autodesk_flag': 1}})
                    db_update(db.request, {'_id': ObjectId(rid)}, {'$inc': {'check_unprocess': -1}})
            db.request.update_one({'_id': ObjectId(rid)}, {'$set': {'finish_time_autodesk': datetime.datetime.now()}})
            logger.debug('update request url_autodesk from query, rid:%s' % rid)
    except Exception:
        logger.debug('update request url_autodesk from query error:%s' % traceback.format_exc())


def get_data_from_url_by_rid(rid):
    """
    get data from url, according rid
    :param rid: the rid of url
    :return: {id1:{'_id':xxx, 'status': xxx}, id2:{'_id': xxx, 'status':xxxx}
    """
    try:
        # url_rids = query_db_session.url.find({'rid': ObjectId(rid)}, {'_id': 1, 'status': 1, 'dev_id': 1,
        #                                                               'retry_branch_id': 1})
        url_rids = query_db_session.url.find({'r_id': ObjectId(rid)})
        logger.debug("query_result get_data_from_url_by_rid success, rid:%s" % rid)
    except Exception:
        logger.debug('query_result get_data_from_url_by_rid error:%s' % e)
        return None
    logger.debug('get_data_from_url_by_rid url_rids:%s' % url_rids)

    return parse_url_data(url_rids)


def parse_url_data(result):
    """

    :param result: the data of url collection
    :return: {id1:{'_id':xxx, 'status': xxx}, id2:{'_id': xxx, 'status':xxxx}
    """
    logger.debug('test result:%s' % result)
    try:
        if not result:
            logger.debug('parse_url_data result:%s' % result)
            return None
        else:
            url_dict = {}
            for res in result:
                logger.debug('parse_url_data res:%s' % res)
                id = str(res.get('_id'))
                url_dict[id] = res
            logger.debug('query_result.py parse_url_data url_dict:%s' % url_dict)
            return url_dict
    except Exception:
        logger.debug('parse_url_data error:%s' % traceback.format_exc())


def get_device_type_by_mongo(dev_name):
    '''
    根据设备名获取设备类型
    '''
    if not dev_name:
        return ''
    _type = query_db_session.device_app.find_one({'name': dev_name})
    if _type:
        return _type['type']
    else:
        return ''