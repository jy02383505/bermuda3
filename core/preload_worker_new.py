# -*- coding:utf-8 -*-
from core.rcmsapi import get_channelname_from_url
import logging, traceback ,time
from datetime import datetime

# from bson import ObjectId
from core.generate_id import ObjectId
from redis import WatchError
import simplejson as json
from celery.task import task

from core import rcmsapi, database, command_factory, redisfactory
from core import preload_postal_new as postal
from core import postal as r_postal
from core.models import STATUS_UNPROCESSED, STATUS_RETRY_SUCCESS, STATUS_CONNECT_FAILED, PRELOAD_STATUS_REPEATED, \
    PRELOAD_STATUS_SUCCESS, PRELOAD_STATUS_FAILED, PRELOAD_STATUS_RETRYED, PRELOAD_STATUS_MD5_DIFF
from core.sendEmail import send as send_mail
from core.verify import doPost
from core.update import db_update
from util import log_utils
from cache import rediscache
import copy
from core.link_detection_all import link_detection_preload, get_failed_pre
import socket


PRELOAD_CACHE = redisfactory.getDB(1)
PRELOAD_DEVS = redisfactory.getDB(5)
db = database.db_session()
s1_db = database.s1_db_session()
logger = log_utils.get_pcelery_Logger()

REFRESH_WORKER_HOST = socket.gethostname()


@task(ignore_result=True, default_retry_delay=10, max_retries=3)
def dispatch(urls):
    """
    preload worker 入口函数

    :param urls:
    """
    try:
        logger.debug("dispatch urls: %s|| len(urls): %s" % (urls, len(urls)))
        devices_if = urls[0].get('devices','')
        if devices_if:
            pre_devs = urls[0].get('devices', [])
            ref_devs = []
            channel_code = urls[0].get('channel_code')
            try:
                c_code = int(channel_code)
                channel_info = db.preload_channel.find_one({'channel_code': channel_code})
            except ValueError as e:
                if urls[0].get('username') != 'duowan':
                    one_channel = get_channelname_from_url(urls[0].get('url'))
                    channel_info = db.preload_channel.find_one({'channel_name': one_channel})
                    ### 后面有个callback会依据channel_code来查询频道,这里统一将
                    [set_channel_code(url, channel_info.get('channel_code')) for url in urls if url.get('channel_code') == 'webluker']
                else:
                    one_channel = get_channelname_from_url(urls[0].get('url'))
                    # channel_info = db.preload_channel.find_one({'channel_name': one_channel})

                    channel_list_all = PRELOAD_DEVS.get('duowan_pk_channel_all')
                    channel_list_all = json.loads(channel_list_all) if channel_list_all else None
                    if not channel_list_all:
                        channel_list_all = get_all_channels('duowan')
                        PRELOAD_DEVS.set('duowan_pk_channel_all', json.dumps(channel_list_all))
                        PRELOAD_DEVS.expire('duowan_pk_channel_all', 60*20)

                    for c in channel_list_all:
                        if c.get('name') == one_channel:
                            channel_info = c
                            channel_info['channel_code'] = c.get('code')
                            channel_info['channel_name'] = c.get('name')

                    channel_info['first_layer_not_first'] = False
                    channel_info['parse_m3u8_f'] = False
                    channel_info['parse_m3u8_nf'] = False
                    ### 后面有个callback会依据channel_code来查询频道,这里统一将
                    [set_channel_code(url, channel_info.get('channel_code')) for url in urls if url.get('channel_code') == 'webluker']

            first_layer_first = True if not channel_info.get('first_layer_not_first') else False
            parse_m3u8_f = channel_info.get('parse_m3u8_f')
            parse_m3u8_nf = channel_info.get('parse_m3u8_nf')
            logger.debug("dispatch channel_info: %s" % (channel_info, ))

            add_fds = {'first_layer_first': first_layer_first, 'parse_m3u8_f': parse_m3u8_f, 'parse_m3u8_nf': parse_m3u8_nf}
            dev_id = s1_db.preload_dev.insert(
                {"devices": create_send_dev_dict(pre_devs, add_fields=add_fds), "created_time": datetime.now(),
                 "channel_code": urls[0].get('channel_code'), "unprocess": (len(pre_devs)+len(ref_devs))})
        else:
            dev_id, pre_devs, ref_devs = init_pre_devs(urls[0].get('channel_code'))
        logger.debug("dispatch ref_devs: %s|| pre_devs: %s" % (ref_devs, pre_devs))
        if not len(pre_devs):
            logger.debug("no_devices::::%s"%urls[0].get('channel_code'))
        #  test down
        # 以下部分为测试部分  增加一个新的设备  CNC-JS-c-3WR 外网地址 182.118.78.102   内网地址：172.16.21.102
        # pre_devs.append({'status': 'OPEN', 'code': 0, 'name': 'CNC-DL-5-3S3', 'type':'HPCC','serviceIp': None,\
        #        'serialNumber': '060120b3g7', 'host': '218.60.108.79', 'deviceId': None, 'firstLayer': False,\
        #             'port': 31108})
        # ref_devs.append({'status': 'OPEN', 'code': 0, 'name': 'CNC-DL-5-3S3', 'type':'HPCC','serviceIp': None,\
        #        'serialNumber': '060120b3g7', 'host': '218.60.108.79', 'deviceId': None, 'firstLayer': False,\
        #             'port': 31108})
        #
        # pre_devs.append({'status': 'OPEN', 'code': 0, 'name': 'CNC-CP-9-3S5', 'type':'FC','serviceIp': None,\
        #        'serialNumber': '060120b3g8', 'host': '113.207.33.142', 'deviceId': None, 'firstLayer': False,\
        #             'port': 31108})
        # ref_devs.append({'status': 'OPEN', 'code': 0, 'name': 'CNC-CP-9-3S5', 'type':'FC','serviceIp': None,\
        #        'serialNumber': '060120b3g8', 'host': '113.207.33.142', 'deviceId': None, 'firstLayer': False,\
        #             'port': 31108})
        # logger.debug("pre_devs:XXXXXXXXXXXXXXXXXXX:%s" % pre_devs)
        # logger.debug(dev_map)

        # new modification  get len of firstLayer of preload dev
        first_layer_preload = [dev for dev in pre_devs if dev.get("firstLayer")]
        not_first_layer_preload_len = len(pre_devs) - len(first_layer_preload)
        first_layer_preload_len = len(first_layer_preload)
        f_and_nf = False
        if first_layer_preload_len and not_first_layer_preload_len:
            f_and_nf = True

        logger.debug("dispatch first_layer_preload_len: %s|| not_first_layer_preload_len: %s" %
                     (first_layer_preload_len, not_first_layer_preload_len))
        if first_layer_preload_len:
            conn_num, speed = get_bandwidth(first_layer_preload_len, urls[0].get('limit_speed'))
            logger.debug('dispatch first_layer_preload_len send conn_num:%s|| speed:%s' % (conn_num, speed))
        if not first_layer_preload_len and not_first_layer_preload_len:
            conn_num, speed = get_bandwidth(not_first_layer_preload_len, urls[0].get('limit_speed'))
            logger.debug("dispatch not_first_layer_preload_len send conn_num:%s, speed:%s" % (conn_num, speed))
        # end new modification

        is_timer_tasks = False
        if urls[0].get('status') == 'TIMER':
            is_timer_tasks = True

        for url in urls:
            url["dev_id"] = dev_id
            url_id=url.get('_id')
            if url_id:
                url["_id"]=ObjectId(str(url_id))
            else:
                url["_id"] = ObjectId()
            url["status"] = "PROGRESS"
            if speed:
                url['conn_num'] = conn_num
                url['single_limit_speed'] = speed
            # preload_worker host
            url['worker_host'] = REFRESH_WORKER_HOST
            #preload_url任务缓存
            PRELOAD_CACHE.set(url.get('_id'), json.dumps(
                {"dev_id": str(dev_id), "task_id": url.get("task_id"),
                 "channel_code": url.get("channel_code"), "unprocess": len(
                    pre_devs), 'status': 'PROGRESS', 'check_type': url.get('check_type'),
                 'check_result': url.get('md5'), 'first_layer_first': pre_devs[0].get('first_layer_first'),
                 'f_and_nf': f_and_nf
                }))
            if is_timer_tasks:
                try:
                    s1_db.preload_url.update_one({'_id': url["_id"]}, {'$set': url})
                except Exception:
                    logger.debug("dispatch preload_worker update_one  error:%s, _id:%s" % (e, url['_id']))

            #设备缓存
            PRELOAD_CACHE.hmset('%s_dev'%(str(url.get('_id'))), create_preload_result_dict_to_cache(pre_devs))
            PRELOAD_CACHE.expire(url.get('_id'), int(3600*24*5.5))
            PRELOAD_CACHE.expire('%s_dev'%(str(url.get('_id'))), int(3600*24*5.5))

        if not is_timer_tasks:
            s1_db.preload_url.insert(urls)

        layer_worker(urls, pre_devs, ref_devs) if ref_devs else worker(urls, pre_devs)
        logger.debug("dispatch new preload end")
    except Exception:
        logger.debug("dispatch new preload error: %s " % traceback.format_exc())

def get_preload_dev_cache(url_id, host=None):
    '''
    获取任务设备缓存
    '''
    res_dict = {}
    if host:
        res = PRELOAD_CACHE.hget("%s_dev"%(url_id), host)
        if res:
            res_dict = json.loads(res)
        return res_dict
    else:
        res = PRELOAD_CACHE.hgetall("%s_dev"%(url_id))
        if res:
            for k,v in list(res.items()):
                res_dict[k] = json.loads(v)
        return res_dict

def nf_tasks_begin(url_id, cache_body):
    """
    make the tasks of non-layer begin.
    """
    try:
        ### Whether non-first-layer-device tasks begin.
        devices = get_preload_dev_cache(url_id)
        dev_list = list(devices.values())
        preload_200_num = 0
        logger.debug("nf_tasks_begin url_id: %s" % (url_id, ))
        for dev in dev_list:
            if dev.get('preload_status') in [200, '200', 406, '406']:
                preload_200_num += 1

        dev_first_num = len([d for d in dev_list if d.get('firstLayer')])
        logger.debug("nf_tasks_begin dev_first_num: %s|| preload_200_num: %s" % (dev_first_num, preload_200_num))

        nf_begin = False
        if cache_body.get('first_layer_first') and preload_200_num >= (dev_first_num * 0.6):
            nf_begin = PRELOAD_CACHE.setnx('%s_lock' % (url_id, ), 1)
            PRELOAD_CACHE.expire('%s_lock' % url_id, int(3600*24*5.5))
        if nf_begin:
            logger.debug("nf_tasks_begin [nf_tasks_begin!!!preload_200_num(%s) >= dev_first_num(%s)] url_id: %s" % (preload_200_num, dev_first_num, url_id))
            results = []
            urls = [u for u in s1_db.preload_url.find({'_id': ObjectId(url_id)})]
            dev_id = urls[0].get('dev_id')
            devs = s1_db.preload_dev.find_one({'_id': dev_id})
            # logger.debug("nf_tasks_begin type(devs.get('devices')): %s|| devs.get('devices'): %s" % (type(devs.get('devices')), devs.get('devices')))
            pre_devs = devs.get('devices')
            layer_dev = [dev for dev in list(pre_devs.values()) if not dev.get("firstLayer")]

            if layer_dev:
                f_res = send(layer_dev, urls)
                if f_res:
                    results += f_res

            update_db_dev(dev_id, results)
            # subsenter
            # refresh_failed_list, preload_failed_list = get_failed_pre(urls[0].get('dev_id'),results)
            # link_detection_preload.delay(urls, refresh_failed_list, 'url_ret', preload_failed_list, 'pre_ret')
            # logger.debug("nf_tasks_begin layer_dev: %s,\n refresh_failed_list: %s,\n preload_failed_list: %s,\n results: %s" % (layer_dev, refresh_failed_list, preload_failed_list, results))
    except Exception:
        logger.debug("nf_tasks_begin [error]: %s" % traceback.format_exc())

def recycle_redis_task_dev_cache(url_id):
    """
    delete the cache after using when the condition is satisfied and save the data.
    """
    try:
        devices = get_preload_dev_cache(url_id)
        dev_list = list(devices.values())
        preload_200_num = 0
        logger.debug("recycle_redis_task_dev_cache url_id: %s" % (url_id, ))
        for dev in dev_list:
            if dev.get('preload_status') in [200, '200']:
                preload_200_num += 1

        dev_total_num = len(dev_list)
        logger.debug("recycle_redis_task_dev_cache dev_total_num: %s|| preload_200_num: %s" % (dev_total_num, preload_200_num))
        update_body = PRELOAD_CACHE.get(url_id)
        if update_body is None:
            logger.debug("recycle_redis_task_dev_cache update_body is None, returned.")
            return
        logger.debug("type(update_body): %s|| update_body: %s" % (type(update_body), update_body))
        update_body = json.loads(update_body)
        status = 'FINISHED'
        update_body['status'] = status
        update_body['devices'] = {v['name']: v for v in list(devices.values())}
        update_body['created_time'] = datetime.now()
        logger.debug("recycle_redis_task_dev_cache update_body: %s" % (update_body, ))

        #-# 用于将达到阈值后（任务状态为FINISHED）的设备缓存状态同步到mongodb中的preload_result表中
        try:
            db_update(s1_db.preload_result, {'_id': ObjectId(url_id)}, {"$set": {'devices': update_body['devices']}})
        except Exception:
            logger.debug("recycle_redis_task_dev_cache [preload_result updating error]: %s" % (traceback.format_exc(), ))

        if preload_200_num and dev_total_num == preload_200_num:
            try:
                s1_db.preload_result.update_one({'_id': ObjectId(url_id)}, {'$set': update_body}, upsert=True)
                db_update(s1_db.preload_url, {'_id': ObjectId(url_id)}, {"$set": {'status': status}})
            except Exception:
                logger.debug("recycle_redis_task_dev_cache insert error: %s|| url_id: %s " % (traceback.format_exc(), url_id))
            PRELOAD_CACHE.delete(url_id)
            PRELOAD_CACHE.delete('%s_dev'%(url_id))
            PRELOAD_CACHE.delete('%s_lock'%(url_id))
            PRELOAD_CACHE.delete('%s_callback_lock'%(url_id))
            logger.debug("recycle_redis_task_dev_cache [cache deleted successfully.] url_id: %s" %(url_id, ))
    except Exception:
        logger.debug("recycle_redis_task_dev_cache [error]: %s" % traceback.format_exc())

def update_preload_dev_cache(url_id, host, value):
    '''
    dev缓存更新
    '''
    logger.debug("update_preload_dev_cache begin url_id: %s|| host: %s|| value: %s " % (url_id, host, value))
    if isinstance(value,dict):
        save_value = json.dumps(value)
    else:
        save_value = value
    s_key = '%s_dev' %(url_id)
    PRELOAD_CACHE.hset(s_key, host, save_value)
    PRELOAD_CACHE.expire(s_key, int(3600*24*5.5))
    logger.debug("update_preload_dev_cache end url_id: %s|| host: %s|| value:%s" % (url_id, host, PRELOAD_CACHE.hget(s_key, host)))

def merge_other_dispatch_task(pre_url, url_dict, new_action, package_size=25):
    """
    对进行中的任务，下发remove操作
    :param pre_url:
    :param url_dict:
    :param new_action:
    :param package_size:
    """
    pre_url['previous_action'] = pre_url.get("action")
    pre_url['action'] = new_action
    url_dict.setdefault(pre_url.get("dev_id"), []).append(pre_url)
    if len(url_dict.get(pre_url.get("dev_id"))) > package_size:
        dispatch_other(url_dict.pop(pre_url.get("dev_id")))

@task(ignore_result=True, default_retry_delay=10, max_retries=3)
def preload_cancel(username, task_list):
    try:
        logger.debug("preload_cancel username: %s task_list :%s" %
                     (username, str(task_list)))
        # logger.debug('cancel find %s'%({"task_id": {'$in': task_list}, 'username': username}))
        condition = {"task_id": {'$in': task_list}}
        if rediscache.isFunctionUser(username):
            condition['username'] = username
        else:
            condition['parent'] = username
        pre_urls = s1_db.preload_url.find(condition)
        url_dict = {}
        # logger.debug(pre_urls)
        for pre_url in pre_urls:
            # logger.debug('preload cancel urls:%s'%pre_url.get('_id'))
            if pre_url.get('status') == 'PROGRESS':
                merge_other_dispatch_task(pre_url, url_dict, 'remove')
            db_update(s1_db.preload_url, {'_id': pre_url.get('_id')}, {
                "$set": {'status': 'CANCEL', 'previous_action': pre_url.get("action"), "action": "remove",
                         'finish_time': datetime.now()}})
            PRELOAD_CACHE.delete(pre_url.get('_id'))
            s1_db.preload_error_task.remove({'url_id': str(pre_url.get('_id'))})
        for urls in list(url_dict.values()):
            dispatch_other(urls)
    except Exception:
        logger.debug("preload_cancel error:%s " % e)

@task(ignore_result=True, default_retry_delay=10, max_retries=3)
def execute_retry_task(username, task_list):
    try:
        logger.debug("execute_retry_task username: %s task_list :%s" %
                     (username, str(task_list)))
        condition = {"task_id": {'$in': task_list}}
        if rediscache.isFunctionUser(username):
            condition['username'] = username
        else:
            condition['parent'] = username
        pre_urls = s1_db.preload_url.find(condition)
        url_dict = {}
        for pre_url in pre_urls:
            logger.debug("execute_retry_task pre_url: %s" % str(pre_url))
            if pre_url.get('status') == 'FAILED':
                merge_other_dispatch_task(pre_url, url_dict, 'refresh,preload')
                old_result = s1_db.preload_result.find_one({"_id": pre_url.get("_id")})
                logger.debug("execute_retry_task old_result: %s" % str(old_result))
                old_result["_id"] = str(pre_url.get('_id'))
                old_result["devices"] = create_proload_result_dict(list(old_result.get('devices').values()))
                old_result["unprocess"] = len(old_result.get('devices'))
                old_result["status"] = "PROGRESS"
                PRELOAD_CACHE.set(pre_url.get('_id'), json.dumps(old_result))
                logger.debug("execute_retry_task preload_cache: %s" % str(PRELOAD_CACHE.get(pre_url.get('_id'))))
                db_update(s1_db.preload_url, {'_id': pre_url.get('_id')}, {
                    "$set": {'status': 'PROGRESS', 'finish_time': None}})
                s1_db.preload_error_task.remove({"url_id": str(pre_url.get('_id'))})
                url = s1_db.preload_url.find_one({"_id": pre_url.get("_id")})
                logger.debug("execute_retry_task url: %s" % str(url))
                logger.debug("execute_retry_task url_dict: %s" % str(url_dict))
        for urls in list(url_dict.values()):
            dispatch_other(urls)
        logger.debug("execute_retry_task end")
    except Exception:
        logger.debug("execute_retry_task error:%s " % e)

def get_error_tasks(host):
    '''
    边缘定期过来拿失败任务
    '''
    import datetime as f_datetime
    now = datetime.now()
    _query = {"host": host, "grapped": False, "last_retrytime": {"$gte": now - f_datetime.timedelta(hours=12),"$lte": now - f_datetime.timedelta(seconds=int(600))}}
    preload_task = [task for task in s1_db.preload_error_task.find(_query).limit(100)]
    return preload_task

@task(ignore_result=True, default_retry_delay=10, max_retries=3)
def save_fc_report(report_body):
    """
    worker 处理 预加载返回结果
    :param report_body:
    """

    try:
        #report_body = json.loads(report_body)
        logger.debug("save_fc_report host: %s|| url_id: %s|| body: %s" % (report_body.get("remote_addr"), report_body.get("url_id"), report_body))
        report_addr = report_body.get("remote_addr")
        url_id = report_body.get("url_id")
        cache_body = PRELOAD_CACHE.get(url_id)
        if cache_body:
            cache_body = json.loads(cache_body)
        dev_cache = get_preload_dev_cache(url_id, host=report_addr)
        logger.debug('<1>save_fc_report dev_cache: %s|| cache_body: %s' %(dev_cache, cache_body))

        if not cache_body or not dev_cache:
            logger.debug("save_fc_report no cache_body %s or no dev_cache %s" %(cache_body, dev_cache))
            return

        if report_body.get('preload_status') == PRELOAD_STATUS_REPEATED:
            #边缘暂时无该状态
            logger.debug("PRELOAD_STATUS_REPEATED: %s" % report_body.get("url_id"))
           # db_update(db.preload_url, {'_id': ObjectId(report_body.get("url_id"))}, {"$set": {'status': 'EXPIRED'}})
           # db.preload_error_task.remove({"url_id": str(report_body.get("url_id"))})
           # PRELOAD_CACHE.delete(report_body.get('url_id'))

        # elif report_body.get('preload_status') == PRELOAD_STATUS_SUCCESS and (
        #                 cache_body.get('check_result') == report_body.get('check_result') or cache_body.get(
        #             'check_type') == 'BASIC'):
        elif report_body.get('preload_status') == PRELOAD_STATUS_SUCCESS and (
                        cache_body.get('check_type') == 'MD5' or cache_body.get('check_type') == 'BASIC'):
            logger.debug("PRELOAD_STATUS_SUCCESS: %s,%s" % (report_body.get("url_id"),report_body.get("remote_addr")))
            reset_preload_dev_cache(cache_body, dev_cache, report_body)
            # logger.debug('<2>save_fc_report dev_cache is: %s|| cache_body: %s' %(dev_cache, cache_body))
            if cache_body.get('first_layer_first') and cache_body.get('f_and_nf'):
                nf_tasks_begin(url_id, cache_body)
            if cache_body.get('status') in ['PROGRESS']:
                save_result(url_id, cache_body)
                ### number of device less than 3, how to delete the cache.
                dev_all = get_preload_dev_cache(url_id)
                dev_f = [d for d in list(dev_all.values()) if d.get('firstLayer')]
                dev_nf = [d for d in list(dev_all.values()) if not d.get('firstLayer')]
                if (len(dev_f) < 3 and not dev_nf) or (not dev_f and len(dev_nf) < 3) or (len(dev_f) < 3 and len(dev_nf) < 3):
                    recycle_redis_task_dev_cache(url_id)
            else:
                recycle_redis_task_dev_cache(url_id)
            # 删除错误任务
            s1_db.preload_error_task.remove({"url_id": str(report_body.get("url_id")), "host":report_addr})
        else:
            logger.warn("save_fc_report [handle_error_task!!!] report_body: %s|| cache_body: %s|| dev_cache: %s" % (report_body, cache_body, dev_cache))
            handle_error_task(report_body, cache_body, dev_cache)
    except Exception:
        logger.debug("save_fc_report error: %s " % traceback.format_exc())


def reset_preload_dev_cache(cache_body ,dev_cache, report_body, is_failed=False):
    """
    重置cache内容
    :param cache_body:
    :param report_body:
    :param is_failed:
    """
    if is_failed:
        dev_cache["preload_status"] = STATUS_CONNECT_FAILED
    else:
        # explanation , if basic, return report status 200,
        # if check_type is MD5     cache_body md5 == report_body md5 return report 200, not eq return 406
        dev_cache["preload_status"] = report_body.get("preload_status") if cache_body.get(
            'check_type') == 'BASIC' or cache_body.get('check_result') == report_body.get(
            'check_result') else PRELOAD_STATUS_MD5_DIFF
        set_value(report_body, dev_cache, ["content_length", "check_result", "check_type", "last_modified",
                                     "cache_status", "http_status_code", "download_mean_rate",
                                     "finish_time", "final_status"])
    url_id = report_body.get('url_id')
    update_preload_dev_cache(url_id, report_body.get('remote_addr'), dev_cache)

def save_result(url_id, cache_body):
    """
    存任务执行结果，只有没有未处理的设备才会结束
    :param url_id:
    :param cache_body:
    """
    logger.debug("save_result begin url_id: %s" % url_id)
    if get_unprocess(cache_body, url_id):
        PRELOAD_CACHE.set(url_id, json.dumps(cache_body))
        PRELOAD_CACHE.expire(url_id, int(3600*24*5.5))
        logger.debug("save_result not finished reset cache url_id: %s" % url_id)
    else:
        cache_body['status'] = 'FINISHED'
        logger.debug("save_result url_id: %s|| cache_body: %s" % (url_id, cache_body))
        PRELOAD_CACHE.set(url_id, json.dumps(cache_body))
        PRELOAD_CACHE.expire(url_id, int(3600*24*5.5))
        set_finished(url_id, cache_body, 'FINISHED' if cache_body.get(
            'status') == 'PROGRESS' else cache_body.get('status'))
    logger.debug("save_result end url_id: %s|| cache_body: %s" % (url_id, cache_body))


def get_unprocess(cache_body, url_id):
    """
    统计未接收到返回的设备数与连接失败的设备数
    PRELOAD_STATUS_FAILED(500),STATUS_UNPROCESSED(0)
    如果上层设备100%，下层设备 80%即为完成
    :param cache_body:
    :return:
    """
    firstlayer_count = 0
    unprocess_firstlayer_count = 0
    un_firstlayer_count = 0
    unprocess_un_firstlayer_count = 0
    dev_cache = get_preload_dev_cache(url_id)
    logger.debug("get_unprocess cache_body: %s" % (cache_body, ))
    logger.info("get_unprocess dev_cache: %s" % (dev_cache, ))
    if not dev_cache:
        logger.debug("get_unprocess [error no dev_cache] url_id: %s"%(url_id, ))
        return 999

    for dev in list(dev_cache.values()):

        if dev.get("firstLayer") in ["true", "True", True]:
            firstlayer_count += 1
            if dev.get("preload_status") in [PRELOAD_STATUS_FAILED, STATUS_UNPROCESSED, STATUS_CONNECT_FAILED]:
                unprocess_firstlayer_count += 1
        else:
            un_firstlayer_count += 1
            if dev.get("preload_status") in [PRELOAD_STATUS_FAILED, STATUS_UNPROCESSED, STATUS_CONNECT_FAILED]:
                unprocess_un_firstlayer_count += 1
    try:
        cache_body['unprocess'] = unprocess_firstlayer_count + unprocess_un_firstlayer_count
        # 只有上层设备时,回调成功设备数量大于60%即置任务状态为FINISHED
        if firstlayer_count > 0 and un_firstlayer_count == 0:
            if (unprocess_firstlayer_count / float(firstlayer_count)) < 0.4:
                cache_body['unprocess'] = 0
            else:
                cache_body['unprocess'] = unprocess_firstlayer_count
        # 只有下层设备时,回调成功设备数量大于50%即置任务状态为FINISHED
        elif firstlayer_count == 0 and un_firstlayer_count > 0:
            if (unprocess_un_firstlayer_count / float(un_firstlayer_count)) < 0.5:
                cache_body['unprocess'] = 0
            else:
                cache_body['unprocess'] = unprocess_un_firstlayer_count
        # 上下层设备均有时,回调成功上层设备数量大于60%且下层回调成功设备数量大于50%时,即置任务状态为FINISHED
        elif firstlayer_count > 0 and un_firstlayer_count > 0:
            if ((unprocess_firstlayer_count / float(firstlayer_count)) < 0.4) and ((unprocess_un_firstlayer_count / float(un_firstlayer_count)) < 0.5):
                cache_body['unprocess'] = 0
            else:
                cache_body['unprocess'] = unprocess_firstlayer_count + unprocess_un_firstlayer_count
        else:
            cache_body['unprocess'] = unprocess_firstlayer_count + unprocess_un_firstlayer_count

        logger.debug('get_unprocess unprocess: %s|| un_firstlayer_count: %s|| unprocess_un_firstlayer_count: %s' % (cache_body['unprocess'], un_firstlayer_count, unprocess_un_firstlayer_count))
        return cache_body.get('unprocess')
    except Exception:
        logger.error('get_unprocess[error]: %s' % (traceback.format_exc(), ))
        return 999


def handle_error_task(report_body, cache_body, dev_cache):
    """
    处理失败的任务
    :param report_body:
    :param cache_body:
    """
    logger.debug("handle_error_task host: %s url_id:%s " % (report_body.get('remote_addr'), report_body.get('url_id')))
    error_task = s1_db.preload_error_task.find_one(
        {'url_id': report_body.get('url_id'), 'host': report_body.get('remote_addr'), 'type': 'preload_failed'})
    if error_task:
        if error_task.get("retry_times") >= 3:
            logger.debug("handle_error_task retry_times > 3 url_id:%s " % report_body.get('url_id'))
            reset_preload_dev_cache(cache_body, dev_cache, report_body, True)
            if get_unprocess(cache_body, report_body.get("url_id")):
                cache_body['status'] = 'FAILED'
                PRELOAD_CACHE.set(report_body.get('url_id'), json.dumps(cache_body))
                logger.debug("handle_error_task reset cache status FAILED url_id: %s" % report_body.get("url_id"))
            else:
                PRELOAD_CACHE.set(report_body.get('url_id'), json.dumps(cache_body))
                logger.debug(
                    "handle_error_task reset cache status FAILED  finished url_id: %s" % report_body.get("url_id"))
                set_finished(report_body.get('url_id'), cache_body, 'FAILED')
            #删除错误任务
            logger.debug("handle_error_task > 3 remove")
            s1_db.preload_error_task.remove({'url_id': report_body.get('url_id'), 'host': report_body.get('remote_addr')})
            
        else:
            PRELOAD_CACHE.set(report_body.get('url_id'), json.dumps(cache_body))
            now = datetime.now()

            db_update(s1_db.preload_error_task,
                      {'url_id': report_body.get('url_id'), 'host': report_body.get('remote_addr')},
                      {'$inc': {'retry_times': 1}, '$set': {
                          #'command': command_factory.re_handle_command(error_task.get('command')),
                          'last_retrytime': now, 'last_retrytime_timestamp':time.mktime(now.timetuple()),'grapped': False}})
            logger.debug("handle_error_task unprocess lt 3")

    else:
        do_first_retry(report_body.get('url_id'), report_body.get('remote_addr'), cache_body, dev_cache)


def do_first_retry(url_id, host, cache_body, dev_cache):
    """
    第一次重试,并插入preload_error_task
    :param url_id:
    :param host:
    :param cache_body:
    """
    now = datetime.now()
    logger.debug("do_frist_retry begin url_id: %s host %s " % (url_id, host))
    dev_cache['preload_status'] = PRELOAD_STATUS_FAILED if dev_cache.get("host") == host else dev_cache.get('preload_status')
    update_preload_dev_cache(url_id, host, dev_cache)
    db_url = s1_db.preload_url.find_one({'_id': ObjectId(url_id)})
    if db_url.get('single_limit_speed'):
        if db_url.get('have_first_layer'):
            if judge_first_layer(str(db_url.get("dev_id")), host):
                s1_db.preload_error_task.insert({'url_id': url_id, 'retry_times': 0, 'command': command_factory.get_command_json(
                [db_url], db_url.get('action'), dev_cache, check_conn=True), 'host': host, 'type': 'preload_failed', 'last_retrytime': now, 'last_retrytime_timestamp': time.mktime(now.timetuple()), 'grapped': False})
            else:
                s1_db.preload_error_task.insert({'url_id': url_id, 'retry_times': 0, 'command': command_factory.get_command_json(
                [db_url], db_url.get('action'), dev_cache), 'host': host, 'type': 'preload_failed', 'last_retrytime': now, 'last_retrytime_timestamp': time.mktime(now.timetuple()), 'grapped': False})

        else:
            s1_db.preload_error_task.insert({'url_id': url_id, 'retry_times': 0, 'command': command_factory.get_command_json(
            [db_url], db_url.get('action'), dev_cache, check_conn=True), 'host': host, 'type': 'preload_failed', 'last_retrytime': now, 'last_retrytime_timestamp': time.mktime(now.timetuple()), 'grapped': False})

    else:

        s1_db.preload_error_task.insert({'url_id': url_id, 'retry_times': 0, 'command': command_factory.get_command_json(
            [db_url], db_url.get('action'), dev_cache), 'host': host, 'type': 'preload_failed', 'last_retrytime': now, 'last_retrytime_timestamp': time.mktime(now.timetuple()), 'grapped': False})

    logger.debug("do_frist_retry end url_id: %s host %s " % (url_id, host))


def set_finished(url_id, cache_body, status):
    """
     处理URL结果存入DB
    :param url_id:
    :param cache_body:
    :param status:
    """
    logger.debug("set_finished begin url_id: %s|| cache_body: %s|| status: %s " % (url_id, cache_body, status))
    now = datetime.now()
    now_t = time.mktime(now.timetuple())
    db_update(s1_db.preload_url, {'_id': ObjectId(url_id)}, {
        "$set": {'status': status, 'finish_time': now, 'finish_time_timestamp': now_t}})
    dev_cache = get_preload_dev_cache(url_id)
    if not dev_cache:
        logger.debug("set_finished no dev_cache %s" %(url_id))
        return

    cache_body['_id'] = ObjectId(url_id)
    cache_body['status'] = status
    save_body = copy.deepcopy(cache_body)
    save_body['devices'] = {v['name']: v for v in list(dev_cache.values())}
    save_body['created_time'] = datetime.now()
    try:
        s1_db.preload_result.insert_one(save_body)
    except Exception:
        # logger.debug("set_finished insert error: %s|| url_id: %s " % (traceback.format_exc(), url_id))
        pass
        
    task_info = get_information(dev_cache)
    preload_info = s1_db.preload_url.find_one({"_id": ObjectId(url_id)})
    # logger.debug("set_finished dev_cache: %s|| task_info: %s" % (dev_cache, task_info))
    ### prevent from mailing more than once.
    has_callback_lock = False
    has_callback_lock = PRELOAD_CACHE.setnx('%s_callback_lock' % (url_id, ), 1)
    PRELOAD_CACHE.expire('%s_callback_lock' % url_id, int(3600*24*5.5))
    if has_callback_lock:
        preload_callback(
            db.preload_channel.find_one({"channel_code": cache_body.get("channel_code"),"username":preload_info.get("username")}),
            {"task_id": cache_body.get('task_id'), "status": cache_body.get('status'), "percent": task_info.get('percent')},
            task_info, id=cache_body.get("_id")
        )
    logger.debug("set_finished end url_id: %s|| status: %s|| has_callback_lock: %s" % (url_id, status, has_callback_lock))


def dispatch_other(urls):
    try:
        logger.debug("dispatch_other uils:%s" % str(urls))
        pre_devs = [dev for dev in list(s1_db.preload_dev.find_one({'_id': urls[0].get('dev_id')}).get(
            "devices").values()) if dev.get("type") == "preload"]
        # pre_devs.append({
        #     "status": "OPEN",
        #     "code": 0,
        #     "name": "CNC-DL-5-3S3",
        #     "serialNumber" : "01011443W1",
        #     "host": "218.60.108.79",
        #     "firstLayer" : False,
        #     "type": "preload",
        #     "port": 31108
        # })
        # logger.debug("pre_devs_test:%s" % pre_devs)
        results = send(
            pre_devs, urls)
        return {"results": results, "devices": pre_devs}
    except Exception:
        logger.debug("dispatch_other error:%s " % e)


def init_pre_devs(channel_code, all_dev=False):
    '''
        初始化预加载设备列表，如果库内没有，直接从
        RCMS通过getDevices获取 "status" == "OPEN"的设备
        getFirstLayerDevices获取第一层设备，过滤出不是preload
        的刷新设备,如果没有配置预加载设备，pre_devs为频道所有设备

    Parameters:

        channel_code :  频道号


    Returns:
        表内ID，预加载设备，刷新设备
    '''
    try:
        rcms_devs = [] # this should be all layer
        rcms_dev_names = []
        rcms_first_devs = []
        for dev in rcmsapi.getFirstLayerDevices(channel_code):
            if dev.get("status") == "OPEN":
                rcms_devs.append(dev)
                rcms_first_devs.append(dev)
                rcms_dev_names.append(dev.get('name'))
        for dev in rcmsapi.getDevices(channel_code):
            if dev.get("status") == "OPEN":
                rcms_devs.append(dev)
                rcms_dev_names.append(dev.get('name'))
        if all_dev:
            return rcms_devs
        pre_devs = []
    #pre_devs = [{u'status': u'OPEN', 'code': 0, u'name': u'CNC-TI-3-3WK', u'host': u'218.24.18.85', u'firstLayer': False, 'type': 'preload'}]
    #pre_devs.append({u'status': u'OPEN', 'code': 0, u'name': u'BGP-BJ-C-5HN', u'host': u'223.202.52.82', u'firstLayer': False, 'type': 'preload'})
    #pre_devs.append({u'status': u'OPEN', 'code': 0, u'name': u'BGP-BJ-C-5H9', u'host': u'223.202.52.83', u'firstLayer': False, 'type': 'preload'})
        if channel_code !=0:
            
            channel_name = ""
            condition={}
            condition['channel_code']=channel_code
            channel_info = db.preload_channel.find_one(condition)
            channel_name = channel_info.get('channel_name')
            parse_m3u8_f = channel_info.get('parse_m3u8_f')
            parse_m3u8_nf = channel_info.get('parse_m3u8_nf')
            first_layer_first = True if not channel_info.get('first_layer_not_first') else False
   
            device_type = PRELOAD_DEVS.get(channel_name)
            if int(device_type)==1:
                pre_devs = rcms_devs
            elif int(device_type)==2:
                pre_devs = rcms_first_devs
            elif int(device_type)== 3 or 500:
                pre_devs = [set_type(dev, d_rcms['type']) for dev in db.preload_config_device.find({"channel_code": channel_code},
                                                                 {"status": 1, "firstLayer": 1, "host": 1, "name": 1,
                                                                  "_id": 0}) for d_rcms in rcms_devs if dev.get('name') == d_rcms['name']]
        else:
            pre_devs = [set_type(dev, d_rcms['type']) for dev in db.preload_config_device.find({"channel_code": channel_code},
                                                             {"status": 1, "firstLayer": 1, "host": 1, "name": 1,
                                                              "_id": 0}) for d_rcms in rcms_devs if dev.get('name') == d_rcms['name']]
        if not pre_devs:
            pre_devs = rcms_devs
            logger.error("init_pre_devs[error occured]: %s set all rcms_devs to pre_devs!!!" % channel_code)
        
        # ref_devs = [set_type(rcms_dev, 'refresh') for rcms_dev in rcms_first_devs
        #             if rcms_dev.get("name") not in [pre_dev.get("name") for pre_dev in pre_devs]]
        ref_devs = [] # demand now is don't refresh.
        for dev in pre_devs:
            dev['first_layer_first'] = first_layer_first
            if parse_m3u8_f and dev.get('firstLayer'):
                dev['parse_m3u8_f'] = True
            elif parse_m3u8_nf and not dev.get('firstLayer'):
                dev['parse_m3u8_nf'] = True
        dev_id = s1_db.preload_dev.insert(
            {"devices": create_send_dev_dict(pre_devs + ref_devs), "created_time": datetime.now(),
             "channel_code": channel_code, "unprocess": len(pre_devs + ref_devs)})
        logger.debug("init_pre_devs channel_info: %s|| dev_id: %s|| pre_devs: %s|| ref_devs: %s|| len(rcms_devs): %s" % (channel_info, dev_id, pre_devs, ref_devs, len(rcms_devs)))
        return dev_id, pre_devs, ref_devs
    except Exception:
        logger.error("init_pre_devs error:%s " % traceback.format_exc())


def set_type(dev, type):
    '''
        设置设备类型

    Parameters:

        dev :  设备

        type : 类型


    Returns:

    '''
    dev['type'] = type
    return dev


def create_proload_result_dict(devs, old_dev_dict={}):
    try:
        dev_dict = old_dev_dict if old_dev_dict else {}
        for dev in devs:
            dev_dict[dev.get('name')] = {"name": dev.get("name"), "host": dev.get("host"),
                                         "firstLayer": dev.get("firstLayer"), 'preload_status': 0,
                                         'download_mean_rate': '-', 'content_length': '-', 'check_type': '-',
                                         'check_result': '-'}
        return dev_dict
    except Exception:
        logger.debug("create_dev_dict error:%s " % e)


def create_preload_result_dict_to_cache(devs):
    try:
        dev_dict = {}
        for dev in devs:
            dev_dict[dev.get('host')] = json.dumps({"name": dev.get("name"), "host": dev.get("host"),
                                         "firstLayer": dev.get("firstLayer"), 'preload_status': 0,
                                         'download_mean_rate': '-', 'content_length': '-', 'check_type': '-',
                                         'check_result': '-', 'first_layer_first':dev.get('first_layer_first')})
        return dev_dict
    except Exception:
        logger.debug("create_dev_dict_to_cache error:%s " % e)


def create_send_dev_dict(devs, old_dev_dict={}, add_fields={}):
    """
    创建设备字典
    :param devs:
    :param old_dev_dict:
    :return:
    """
    try:
        dev_dict = old_dev_dict if old_dev_dict else {}
        for dev in devs:
            dev['code'] = 0

            if add_fields:
                for k, v in list(add_fields.items()):
                    dev[k] = v

                    if k == 'parse_m3u8_f':
                        dev['parse_m3u8_f'] = True if v and dev.get('firstLayer') else False

                    if k == 'parse_m3u8_nf':
                        dev['parse_m3u8_nf'] = True if v and not dev.get('firstLayer') else False

            dev_dict[dev.get('name')] = dev
        return dev_dict
    except Exception:
        logger.debug("create_dev_dict error:%s " % traceback.format_exc())


def layer_worker(urls, pre_devs, ref_devs):
    """
    预加载处理（含刷新设备）
    :param urls:
    :param pre_devs:
    :param ref_devs:
    """
    try:
        preload_results = []
        refresh_results = r_postal.do_send_url(urls, ref_devs)

        firstLayer_dev = [dev for dev in pre_devs if dev.get("firstLayer")]
        if firstLayer_dev:
            f_res = send(firstLayer_dev, urls)
            if f_res:
                preload_results += f_res
        layer_dev = [dev for dev in pre_devs if not dev.get("firstLayer")]
        if layer_dev:
            res = send(layer_dev, urls)
            if res:
                preload_results += res

        update_db_dev(urls[0].get("dev_id"), refresh_results + preload_results)
        # subsenter
        preload_failed_list = get_failed_pre(urls[0].get('dev_id'), preload_results)
        if preload_failed_list:
            link_detection_preload.delay(urls, preload_failed_list)

    except Exception:
        logger.debug("layer_worker error: %s " % traceback.format_exc())


def worker(urls, pre_devs):
    """
    预加载处理（无刷新设备）
    :param urls:
    :param pre_devs:
    """
    try:
        results = []
        first_layer_first = pre_devs[0].get('first_layer_first')

        firstLayer_dev = [dev for dev in pre_devs if dev.get("firstLayer")]
        layer_dev = [dev for dev in pre_devs if not dev.get("firstLayer")]
        f_and_nf = False
        if firstLayer_dev and layer_dev:
            f_and_nf = True

        if first_layer_first and f_and_nf:
            f_res = send((firstLayer_dev), urls)
            if f_res:
                results += f_res
        else:
            f_res = send((firstLayer_dev + layer_dev), urls)
            if f_res:
                results += f_res
        update_db_dev(urls[0].get("dev_id"), results)
        ### subsenter
        preload_failed_list = get_failed_pre(urls[0].get('dev_id'), results)
        # if preload_failed_list:
        #     link_detection_preload.delay(urls, preload_failed_list)
        #     logger.debug("worker urls: %s|| firstLayer_dev: %s|| layer_dev: %s|| preload_failed_list: %s|| results: %s" % (urls, firstLayer_dev, layer_dev, preload_failed_list, results))
    except Exception:
        logger.debug("worker[error]: %s" % traceback.format_exc())


def update_db_dev(dev_id, results):
    """
     更新任务状态,preload_dev
    :param dev_id:
    :param results:
    """
    try:
        now = datetime.now()
        db_dev = s1_db.preload_dev.find_one({"_id": ObjectId(dev_id)})
        db_dev["finish_time"] = now
        db_dev["finish_time_timestamp"] = time.mktime(now.timetuple())
        devices = db_dev.get("devices")
        logger.debug("update_db_dev dev_id: %s|| results: %s" % (dev_id, results))
        for ret in results:
            devices.get(ret.get("name"))["code"] = ret.get("code", 0)
            devices.get(ret.get("name"))["a_code"] = ret.get("a_code", 0)
            devices.get(ret.get("name"))["r_code"] = ret.get("r_code", 0)
            unprocess_num = int(db_dev.get('unprocess'))
            db_dev["unprocess"] = unprocess_num - 1 if unprocess_num > 0 else 0

        logger.debug("update_db_dev dev_id: %s|| db_dev: %s" % (dev_id, db_dev))
        try:
            # logger.debug(db_dev)
            s1_db.preload_dev.save(db_dev)
        except:
            #3.0.3 pymongo update
            update_dev = copy.deepcopy(db_dev)
            if '_id' in update_dev:
                update_dev.pop('_id')
            s1_db.preload_dev.update_one({"_id": ObjectId(dev_id)}, {'$set': update_dev})
            logger.debug("update_db_dev dev_id: %s|| update_dev: %s" % (dev_id, update_dev))
    except Exception:
        logger.debug("update_db_dev[error]: %s" % traceback.format_exc())


def send(devs, urls):
    """
    发送命令到FC
    :param devs:
    :param command:
    :return:
    """
    try:
        dev_map = {}
        [dev_map.setdefault(d.get('host'), d) for d in devs]
        # original code
        # results = postal.process_loop_ret(
        #     postal.doloop(devs, urls), dev_map, "pre_ret")
        # the result of success and failure
        pre_ret, pre_ret_faild = postal.doloop(devs, urls)
        results, error_result = postal.process_loop_ret(pre_ret, dev_map)
        # process the result of failed
        pre_results_faild_dic = postal.process_loop_ret_faild(pre_ret_faild, dev_map)
        if dev_map:
            # the failure in the successful information    join the failure of the info list
            # results += postal.retry(dev_map.values(), urls, "pre_ret", pre_results_faild_dic)
            try:
                pre_results_faild_dic.update(error_result)
                retry_results = postal.retry(list(dev_map.values()), urls, pre_results_faild_dic)
            except Exception:
                logger.error(traceback.format_exc())
            results += retry_results

        # logger.debug("send devs: %s,\n dev_map: %s,\n results: %s,\n error_result: %s,\n pre_results_faild_dic: %s" % (devs, dev_map, results, error_result, pre_results_faild_dic))
        return results
    except Exception:
        logger.debug("send error:%s " % e)


@task(ignore_result=True, default_retry_delay=10, max_retries=3)
def reset_error_tasks(preload_task):

    try:
        now = datetime.now()
        #msg_obj = json.loads(msg)
        #logger.debug("reset_error_tasks msg:%s " % msg)
        #preload_task = msg_obj['preload_task']
        logger.debug("reset_error_tasks preload_task:%s " % preload_task)
        #logger.debug("reset_error_tasks preload_task_type:%s " % type(preload_task))
        for url in preload_task:
            logger.debug("reset_error_tasks url:%s " % (url))
            db_update(s1_db.preload_error_task, {'url_id': url.get('url_id'), 'host': url.get('host')}, {
            '$set': {'last_retrytime': now, 'last_retrytime_timestamp':time.mktime(now.timetuple()),'grapped': True}})
    except Exception:
        logger.debug("reset error task error :%s " % traceback.format_exc())


def set_value(source_dict, new_dict, keys):
    for key in keys:
        if source_dict.get(key):
            new_dict[key] = source_dict.get(key)


def get_information(cache_body):
    """
    计算完成比例
    :param dev_cache: <type 'dict'>
    {'status': 'FINISHED', 'check_result': '', 'check_type': 'BASIC',
    'task_id': 'c32f4eaa-c56a-485e-99ba-0dfffa43bb37', 'lock': False,
    'devices': {'CHN-ZI-2-3g9': {'content_length': '-', 'check_result': '-',
    'name': 'CHN-ZI-2-3g9', 'download_mean_rate': '-', 'host': '222.186.47.10',
     'firstLayer': False, 'preload_status': 0, 'check_type': '-'},'unprocess': 99,
     '_id': ObjectId('53b4b5da3770e1604118b954'), 'channel_code': '56893'}
    :return:
    """
    count = 0
    percent = 0
    file_size = 0
    total_count = 0
    firstLayer_count = 0
    firstLayer_success = 0
    for dev in list(cache_body.values()):
        if dev.get('firstLayer'):
            firstLayer_count += 1
        if dev.get('preload_status') in [200, 205]:
            file_size = dev.get('content_length', 0)
            try:
                float(file_size)
            except Exception:
                file_size = 0
            if dev.get('firstLayer'):
                firstLayer_success += 1
            count += 1
        total_count += 1
    # firstLayer_success =10
    # firstLayer_count =10
    # count =8
    # total_count = 10

    # first only
    if total_count - firstLayer_count == 0:
        if firstLayer_success / float(total_count) >= 0.6:
            percent = 100
    # nf only
    elif firstLayer_count == 0 and total_count > 0:
        if (count - firstLayer_success) / float(total_count) >= 0.5:
            percent = 100
    # first + nf
    elif firstLayer_count > 0 and (total_count - firstLayer_count) > 0:
        if (firstLayer_success / float(firstLayer_count)) >= 0.6 and ((count - firstLayer_success) / float(total_count - firstLayer_count)) >= 0.5:
            percent = 100
    else:
        percent = round(float(count) / (float(total_count) if total_count else 1),2) * 100
    # if (firstLayer_count - firstLayer_success) == 0 and (True if ((total_count - firstLayer_count) == 0) else (
    #             round((float(count - firstLayer_success) / (float(total_count - firstLayer_count))), 2) >= 0.8)):
    #     percent = 100
    # else:
    #     percent = round(float(count) / (float(total_count) if total_count else 1),2) * 100
    if total_count==0:
        percent=0 
    # print {"percent": percent, "file_size": float(file_size), "total_count": total_count, "count": count}
    return {"percent": percent, "file_size": float(file_size), "total_count": total_count, "count": count}


def preload_callback(channel, callback_body, info={}, id=None):
    """
    任务处理完成的汇报，处理预加载结果，调用提交的callback(email,url)
    :param channel:
    :param callback_body:
    :param info:
    :param id:the _id of preload_result
    """
    try:
        content = {}
        content['username'] = channel.get('username', '')
        content['uid'] = callback_body.get('_id', '')
        if id:
            content['uid'] = id
        if channel.get('callback', {}).get('email'):
            email = {}
            try:
                send_mail(channel.get('callback').get('email'),
                          'preload callback', str(callback_body))
                email['email_url'] = channel.get('callback').get('email')
                email['code'] = 200
            except Exception:
                logger.debug("preload_callback email [error]: %s|| url_id: %s " % (traceback.format_exc(), callback_body.get("url_id")))
                email['code'] = 0
            email['send_times'] = 1

            content['email'] = email

        if channel.get('callback', {}).get('url'):
            url = {}
            url['email_url'] = []
            url['email_url'].append(channel.get('callback').get('url'))
            status = doPost(channel.get('callback').get('url'), json.dumps(callback_body))
            url['send_times'] = 1
            if status != 200:
                for i in range(3):
                    status = doPost(channel.get('callback').get('url'), json.dumps(callback_body))
                    logger.debug('request : %s ,urlcallback retry count:%s ,status:%s.' % (
                        channel.get('callback').get('url'), i, status))
                    url['send_times'] = i + 1
                    if status == 200:
                        break
            url['code'] = status
            content['url'] = url

        if info and channel.get('username', '') == 'snda':
            snda_portal = {}
            snda_portal['email_url'] = []
            snda_portal['email_url'].append('http://116.211.20.45/api/preload_report?cdn_id=1005')
            import hashlib
            import urllib.request, urllib.parse, urllib.error
            time_md5 = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            post_data = {'username': channel.get('username'), 'time': time_md5, 'password': hashlib.md5(
                channel.get('username') + 'qetsfh!3' + time_md5).hexdigest()}
            if callback_body.get('status') == 'FINISHED':
                post_data['context'] = json.dumps(
                    [{"task_id": callback_body.get('task_id'), "status": True}])
            else:
                post_data['context'] = json.dumps(
                    [{"task_id": callback_body.get('task_id'), "status": False,
                      "err_text": "Error dev count: %s" % (info.get('total_count') - info.get('count'))}])
            params = urllib.parse.urlencode(post_data)
            logger.debug(post_data)
            logger.debug(params)
            for i in range(3):
                response = urllib.request.urlopen("http://116.211.20.45/api/preload_report?cdn_id=1005", params)
                ret = json.loads(response.read())
                if ret.get('success') == True:
                    snda_portal['code'] = 200
                else:
                    snda_portal['code'] = 0
                snda_portal['send_times'] = i + 1
                if ret.get('success') == True:
                    break
            content['snda_portal'] = snda_portal

        try:
            if content.get('email') or content.get('url') or content.get('snda_portal'):
                content['datetime'] = datetime.now()
                db.email_url_result.insert(content)
        except Exception:
            logger.debug('preload_callback insert email_url_result error:%s' % e)
    except Exception:
        logger.debug("preload_callback[error]: %s url_id: %s " % (traceback.format_exc(), callback_body.get("url_id")))



def get_bandwidth(first_layer_preload_len, speed):
    """
    计算每台机器带宽
    :param devs:
    :param speed:
    :return:
    """
    speed_current = 0

    dev_len = first_layer_preload_len
    if not speed:
        return dev_len, speed_current
    logger.debug("get_bandwidth dev_len:%s" % dev_len)
    speed_temp = parse_speed(speed)
    logger.debug('parse_speed speed:%s, limit_speed:%s' % (speed, speed_temp))
    single_dev_bandwidth = (speed_temp/first_layer_preload_len)/8
    if speed_temp >= (1 * 1024 *1024):
        speed_current = 1500
        logger.debug("speed_temp:%s, dev_len:%s, speed_current:%s" % (speed_temp, dev_len, speed_current))
        conn_num = (speed_temp/dev_len) / 8 /speed_current
        return conn_num, speed_current
    elif speed_temp >= 500 * 1024:
        return two_point_search(1, 20, 1280, 1500, single_dev_bandwidth)
    elif speed_temp >= 100 * 1024:
        return two_point_search(1, 20, 256, 1280, single_dev_bandwidth)
    elif speed_temp >= 50 * 1024:
        logger.debug("bigger 50m single_dev_bandwidth:%s" % single_dev_bandwidth)
        return two_point_search(1, 20, 128, 256, single_dev_bandwidth)
    elif speed_temp >= 20 * 1024:
        return two_point_search(1, 20, 50, 128, single_dev_bandwidth)
    elif speed_temp >= 1 * 1024:
        return two_point_search(1, 20, 1, 100, single_dev_bandwidth)
    elif speed_temp > 0:
        # 速度比较小　　超出了限制范围，　默认
        if single_dev_bandwidth > 0:
            logger.debug("single_dev_bandwidth not all situation single_dev_bandwidth:%s" % single_dev_bandwidth)
            return 1, single_dev_bandwidth
        else:
            # 平均到每台机器限制速度太小，每台机器开一个链接，速度是１  边缘设备对１K 有特殊用途, 变为２k
            logger.debug("get_bandwidth　　conn_num:1, single_conn_speed:1")
            return 1, 2
    else:
        # 不限速
        logger.debug('get_bandwidth not speed limit:%s' % speed_temp)
        return 0, 0



def two_point_search(min_conn, max_conn, min_speed, max_speed, speed, flag=1):
    """
    大于1Gbps  单个连接速度1000kB  根据此算连接数
    源站带宽限制>500Mbps  单个连接限速就是1280-1500KB/s
    100Mbps< 源站带宽限制<500Mbps  单个连接限速就是256-1280KB/s
    50-100Mbsp  单个连接限速就是128-256KB/s
    20-50Mbps  单个连接限速就是50-128KB/s
    1-20Mbps 1-100KB/s

    几个边缘值 需要重新计算

    Args:
        min_conn: the connect of curl
        max_conn: the connect of curl
        min_speed: minimum allowable speed
        max_speed: maximum allowable speed
        speed: bandwidth of every device
        flag: is the maximum of max_con value of a sign to be expanded

    Returns:proper connection number, appropriate bandwidth

    """
    if flag == 1:
        single_conn_speed = speed / max_conn
        if single_conn_speed > max_speed:
            return two_point_search(max_conn, max_conn * 2, min_speed, max_speed, speed, flag=1)
        if speed == 0:
            # 最小时　　返回速度为２，　１k  边缘有特殊用途
            return 1, 2
        # 已到能控制的最小速度
        if speed < min_speed:
            return 1, speed
    middle_conn = (min_conn + max_conn) / 2
    single_conn_speed = speed / middle_conn
    if (single_conn_speed >= min_speed) and (single_conn_speed < max_speed):
        return middle_conn, single_conn_speed
    if single_conn_speed < min_speed:
        return two_point_search(min_conn, middle_conn, min_speed, max_speed, speed, flag=0)
    if single_conn_speed >= max_speed:
        if middle_conn + 1 == max_conn:
            return middle_conn, single_conn_speed
            # return two_point_search(middle_conn + 1, max_conn, min_speed, max_speed, speed, flag=0)
        else:
            return two_point_search(middle_conn + 1, max_conn, min_speed, max_speed, speed, flag=0)


def parse_speed(speed):
    """

    :param speed:200G, 20k, 20
    :return:
    """
    try:
        logger.debug("parse_speed speed:%s" % speed)

        speed_lower = speed.lower()
        speed_lower_no_blank = speed_lower.replace(' ', '')
        logger.debug("parse_speed no blank speed_lower_no_blank:%s" % speed_lower_no_blank)
        speed_lower_no_blank_n = speed_lower_no_blank.strip()
        if speed_lower_no_blank_n.endswith('g'):
            return (int(speed_lower_no_blank_n.replace('g', ''))) * 1024 * 1024
        elif speed_lower_no_blank_n.endswith('m'):
            return (int(speed_lower_no_blank_n.replace('m', ''))) * 1024
        elif speed_lower_no_blank_n.endswith('k'):
            return int(speed_lower_no_blank_n.replace('k', ''))
        else:
            return int(speed_lower_no_blank_n)
    except Exception:
        logger.debug('parse_speed error:%s' % traceback.format_exc())
        return 0


def judge_first_layer(id, host):
    """
        判断此设备是否是上层
    Args:
        id:
        host:

    Returns:True False

    """
    try:
        result = s1_db.preload_dev.find_one({"_id": ObjectId(id)})
        logger.debug("judge_first_layer find_one success _id:%s" % id)
    except Exception:
        logger.debug('judge_first_layer find _id:%s, error:%s' % (id, e))
        return False
    try:
        if result:
            for dev in list(result.get('devices').values()):
                if dev.get('host') == host:
                    logger.debug('find host success')
                    return dev.get('firstLayer')
        return False
    except Exception:
        logger.deubug("judge_first_layer judge error:%s" % traceback.format_exc())
        return False


def set_finished_by_api(url_id, date_s, status="FINISHED"):
    '''
    通过接口改变任务状态
    '''
    try:
        url_obj = s1_db.preload_url.find_one({'_id': ObjectId(url_id)})

        logger.debug('set_finished_by_api begin url_id %s, date_s %s'%(url_id, date_s))

        if url_obj['status'] == "PROGRESS":

            logger.debug('set_finished_by_api status POGRESS url_id %s'%(url_id))
            cache_body = PRELOAD_CACHE.get(url_id)
            if not cache_body:
                logger.debug('set_finished_by_api no cache')
                return
            else:
                set_finished(url_id, cache_body, status)
        else:

            logger.debug('set_finished_by_api status no POGRESS url_id %s'%(url_id))
            date_obj = datetime.strptime(date_s, '%Y%m%d%H%M%S')
            time_date = time.mktime(date_obj.timetuple())
            db_update(s1_db.preload_url, {'_id': ObjectId(url_id)}, {'$set':{"finish_time":date_obj, 'finish_time_timestamp':time_date, "status":status}})

        logger.debug('set_finished_by_api end url_id %s, date_s %s'%(url_id, date_s))

    except Exception:
        logger.debug('set_finished_by_api error is %s'%(e))


def set_channel_code(url_dict, c_code):
    try:
        if isinstance(url_dict, dict):
            url_dict['channel_code'] = c_code
        return url_dict
    except Exception:
        logger.debug("set_channel_code[error]: %s" % (traceback.format_exc(), ))


def get_all_channels(username):
    import urllib.request, urllib.error, urllib.parse
    try:
        url = 'https://cms3-apir.chinacache.com/customer/%s/channels' % username
        channel_list = json.loads(urllib.request.urlopen(url, timeout=60).read())
        return [i for i in channel_list if i.get('channelState') != 'TRANSFER']

    except Exception:
        logger.debug("get_all_channels[error]: %s" % (traceback.format_exc(), ))
