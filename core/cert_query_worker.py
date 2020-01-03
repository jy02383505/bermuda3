# -*- coding:utf-8 -*-
import os
import copy
import time
import datetime
import base64
import traceback
import random
import requests
import queue
import socket
from core.generate_id import ObjectId
import simplejson as json
from celery.task import task
from core import rcmsapi, database, command_factory, redisfactory, sendEmail
from cache import api_hope, api_rcms
from core import cert_query_postal
from Crypto.Hash import SHA256
from pymongo.errors import DuplicateKeyError
from pymongo import ReturnDocument
from util import log_utils, rsa_tools, tools
from core.update import db_update
from core.link_detection_all import link_detection_cert, get_failed_cert_devs
from .config import config
import logging

WORKER_HOST = socket.gethostname()
CERT_QUERY_CACHE = redisfactory.getDB(4)
s1_db = database.s1_db_session()
db = database.db_session()
logger = log_utils.get_cert_query_worker_Logger()
api_obj = api_hope.ApiHOPE()


@task(ignore_result=True, default_retry_delay=10, max_retries=3)
def dispatch(tasks):
    try:
        logger.debug("dispatch cert_query trans  begin %s" % len(tasks))
        logger.debug("dispatch cert_query trans  begin task_ids %s" % [i['_id'] for i in tasks])
        dev_id, devs, devs_dict = init_cert_dev(tasks[0])
        logger.debug("devs is %s" % devs)
        logger.debug("cert_devs dev_id %s, devs len %s" % (dev_id, len(devs)))
        save_tasks = []
        for task in tasks:

            task['dev_id'] = dev_id
            save_task = {}
            save_task['_id'] = ObjectId(task['_id'])
            save_task['status'] = "PROGRESS"
            save_task['dev_id'] = dev_id
            save_task['query_path'] = task.get('query_path')
            save_task['username'] = task.get('username')
            save_task['q_id'] = task.get('q_id')
            save_task['query_type'] = task.get('query_type')
            save_task['send_devs'] = task.get('query_dev_ip')
            save_task['created_time'] = task.get('created_time')
            save_task['query_config_path'] = task.get('query_config_path')
            save_task['query_cert_name'] = task.get('query_cert_name')
            save_task['worker_host'] = WORKER_HOST
            save_tasks.append(save_task)
            make_result_cache(task['_id'], devs_dict)

        s1_db.cert_query_tasks.insert(save_tasks)
        worker(tasks, devs)
        logger.debug("query cert trans end")
    except Exception:
        logger.debug("query cert trans error:%s " % traceback.format_exc())


def init_cert_dev(task):

    cache_key = task['dev_ip_md5']
    all_devs = []
    devs_dict = {}
    cache_dict = {}
    all_dev_ip = task['query_dev_ip']
    logger.debug("all_dev_ip:%s" % all_dev_ip)
    # for dev_ip in all_dev_ip:
    for k, dev_ip in enumerate(all_dev_ip):
        # 根据设备的ip匹配出设备的name
        device_group = 'HPCC'
        logger.debug("dev_ip is %s" % dev_ip)
        device_name = tools.get_dev_infobyip(dev_ip)[0]
        logger.debug('device_name is %s' % device_name)
        #all_devs.append({'name': device_name, 'host': dev_ip, 'type':device_group})
        dev = {'name': device_name, 'host': dev_ip, 'code': 0, 'type': device_group}
        all_devs.append(dev)
        devs_dict[device_name] = dev
        cache_dict[device_name] = json.dumps(dev)

    CERT_QUERY_CACHE.hmset(cache_key, cache_dict)

    dev_id = s1_db.cert_query_dev.insert(
        {'query_dev_ip': devs_dict, 'created_time': datetime.datetime.now(), 'unprocess': len(all_devs)})
    return dev_id, all_devs, devs_dict


def worker(tasks, send_devs):
    '''
    下发
    '''
    try:

        logger.debug('---worker begin----')
        logger.debug('---worker send_devs len is %s----' % (len(send_devs)))
        results = send(send_devs, tasks)
        update_db_dev(tasks[0]['dev_id'], results)
        # subsenter
        faild_list = get_failed_cert_devs(tasks[0].get("dev_id"), results, 'cert_query_dev')
        logger.debug('---worker subsenter faild_list len %s----' % (len(faild_list)))

        if faild_list:
            Interface = 'checkcertisexits'
            link_detection_cert.delay(tasks, faild_list, Interface)

        # check_cert_task
        logger.debug('cert_query trans worker begin check delay')
        check_cert_query_task.apply_async(([i['_id'] for i in tasks],), countdown=120)
        logger.debug('cert_query trans worker begin end check delay')

        #make_all_callback_force([i['_id'] for i in tasks])

    except Exception:

        #make_all_callback_force([i['_id'] for i in tasks])
        logger.debug('cert_query trans worker error is %s' % (traceback.format_exc()))


@task(ignore_result=True, default_retry_delay=5, max_retries=3)
def check_cert_query_task(task_ids):
    '''
    n seconds 后检查任务状态
    '''
    logger.debug('---check_cert_task start task_ids: %s---' % (task_ids))

    task_info_list = s1_db.cert_query_tasks.find(
        {'_id': {'$in': [ObjectId(task_id) for task_id in task_ids]}, 'status': 'PROGRESS'})
    if task_info_list.count() == 0:
        logger.debug('---check_cert_query_task no task_info  ids: %s---' % (task_ids))
        return

    for task_info in task_info_list:

        error_devs = get_error_dev_result(task_info)
        if not error_devs:
            continue
        set_finished(task_info['_id'], 'FAILED')
        logger.debug('---check_cert_query_task id %s set Failed end---' % (task_info['_id']))

    return


def update_db_dev(dev_id, results):
    '''
    更新任务状态　cert_query_dev&cert_query_tasks
    '''
    try:

        now = datetime.datetime.now()
        db_dev = s1_db.cert_query_dev.find_one({"_id": ObjectId(dev_id)})
        db_dev["finish_time"] = now
        devices = db_dev.get("query_dev_ip")
        for ret in results:
            devices.get(ret.get("name"))["code"] = ret.get("code", 0)
            devices.get(ret.get("name"))["a_code"] = ret.get("a_code", 0)
            devices.get(ret.get("name"))["r_code"] = ret.get("r_code", 0)
            db_dev["unprocess"] = int(db_dev.get("unprocess")) - 1
        update_dev = copy.deepcopy(db_dev)
        if '_id' in update_dev:
            update_dev.pop('_id')
        s1_db.cert_query_dev.update_one({"_id": ObjectId(dev_id)}, {'$set': update_dev})
        s1_db.cert_query_tasks.update_many({'dev_id': ObjectId(dev_id)}, {
                                           '$set': {'finish_time': now}})

    except Exception:
        logger.debug('cert_query update_db_dev error is %s' % (traceback.format_exc()))


def send(devs, tasks):
    '''
    下发任务
    '''
    try:

        dev_map = {}
        [dev_map.setdefault(d.get('host'), d) for d in devs]
        logger.debug("dev_map is %s" % dev_map)
        Interface = 'checkcertisexits'
        ret, ret_faild = cert_query_postal.doloop_url(devs, tasks, Interface)
        results, error_result = cert_query_postal.process_loop_ret(ret, dev_map)

        results_faild_dic = cert_query_postal.process_loop_ret_faild(ret_faild, dev_map)
        if dev_map:
            # 重试
            try:
                results_faild_dic.update(error_result)
                retry_results = cert_query_postal.retry(
                    list(dev_map.values()), tasks, results_faild_dic, Interface)
            except Exception:
                retry_results = []
                logger.error('----cert query send retry error-----')
                logger.error(traceback.format_exc())
            results += retry_results
        return results

    except Exception:
        logger.error("cert send error:%s " % e)
        logger.error(traceback.format_exc())


def make_result_cache(task_id, dev_dict):
    '''
    生成结果缓存
    '''
    save_cache = {}
    for k, v in list(dev_dict.items()):
        save_cache[v['host']] = json.dumps(
            {'host': v['host'], 'result_status': 0, 'type': v['type'], 'name': v['name']})

    if not save_cache:
        raise

    CERT_QUERY_CACHE.hmset('%s_res' % (task_id), save_cache)
    CERT_QUERY_CACHE.set('%s_res_dev_num' % (task_id), len(save_cache))


@task(ignore_result=True, default_retry_delay=10, max_retries=3)
def save_result(data_list, remote_ip):
    '''
    存储状态
    '''
    logger.debug('save_result begin data_list %s remote_ip %s' % (data_list, remote_ip))
    now = datetime.datetime.now()
    for data in data_list:

        logger.debug('data is %s' % data)

        task_id = data.get('task_id', '')
        task_id = task_id.replace('\n', '')
        task_id = task_id.replace('"', '')
        status = int(data.get('status', 0))
        query_result = data.get('info', '')
        res_cache_key = '%s_res' % (task_id)
        logger.debug('save_result task_id %s  status:%s remote_ip %s' %
                     (task_id, status, remote_ip))
        dev_num_cache_key = '%s_res_dev_num' % (task_id)
        failed_cache_key = '%s_res_failed' % (task_id)
        success_cache_key = '%s_res_success' % (task_id)
        if not task_id:
            logger.debug('save_result not task_id return %s' % (remote_ip))
            continue
        cache_key = '%s_res' % (task_id)
        info_str = CERT_QUERY_CACHE.hget(res_cache_key, remote_ip)
        logger.debug('save_result hget cache_key %s  ,remote_ip %s' % (res_cache_key, remote_ip))

        if not info_str:
            logger.debug('save_result no cache id %s remote_ip %s' % (task_id, remote_ip))
            continue
        info = json.loads(info_str)
        logger.debug('info is %s' % info)
        if info['result_status'] == 200:
            logger.debug('save_result had 200 id %s remote_ip %s' % (task_id, remote_ip))
            continue
        info['update_time'] = time.time()
        info['result_status'] = status
        info['result'] = query_result
        logger.debug('save_result to save redis  info is %s remote_ip is %s' % (info, remote_ip))
        CERT_QUERY_CACHE.hset(res_cache_key, remote_ip, json.dumps(info))
        logger.debug('save_result to save redis  remote_ip is %s over' % (remote_ip))
        if status == 200:
            before_success_num = CERT_QUERY_CACHE.scard(success_cache_key)
            logger.debug('save_result add count success remote_ip %s before_success_num %s' %
                         (remote_ip, before_success_num))
            CERT_QUERY_CACHE.sadd(success_cache_key, remote_ip)
        else:
            CERT_QUERY_CACHE.sadd(failed_cache_key, remote_ip)
            logger.debug('save_result add count failed remote_ip %s' % (remote_ip))

        success_num = CERT_QUERY_CACHE.scard(success_cache_key)
        failed_num = CERT_QUERY_CACHE.scard(failed_cache_key)
        all_dev_num = CERT_QUERY_CACHE.get(dev_num_cache_key)

        logger.debug('save_result remote_ip %s success_num %s, failed_num %s, all_count %s' %
                     (remote_ip, success_num, failed_num, all_dev_num))
        if int(success_num) == int(all_dev_num):
            logger.debug('success_num is %s' % success_num)
            # 全部成功
            logger.debug('task_id is %s' % task_id)
            #set_finished(task_id, 'FINISHED',query_result)
            set_finished(task_id, 'FINISHED')
        elif int(failed_num) == int(all_dev_num):
            # TODO
            task_info = s1_db.cert_query_tasks.find_one({'_id': ObjectId(task_id)})
            error_list = get_error_dev_result(task_info)
            #send_error_email(task_info, error_list)
            #set_finished(task_id, 'FAILED',query_result)
            set_finished(task_id, 'FAILED')


def set_finished(task_id, status):
    '''
    to finish
    '''
    now = datetime.datetime.now()
    logger.debug('now is %s' % now)
    task_info = s1_db.cert_query_tasks.find_one_and_update({'_id': ObjectId(task_id), 'status': "PROGRESS"}, {
                                                           "$set": {'status': status, 'hpc_finish_time': now}}, return_document=ReturnDocument.AFTER)
    # cache -> mongo
    res_cache_key = '%s_res' % (task_id)
    dev_num_cache_key = '%s_res_dev_num' % (task_id)
    failed_cache_key = '%s_res_failed' % (task_id)
    success_cache_key = '%s_res_success' % (task_id)
    all_cache = CERT_QUERY_CACHE.hgetall(res_cache_key)
    all_dev_num = CERT_QUERY_CACHE.get(dev_num_cache_key)
    success_num = CERT_QUERY_CACHE.scard(success_cache_key)
    unprocess = int(all_dev_num) - int(success_num)
    logger.debug('unprocess is %s' % unprocess)
    if unprocess <= 0:
        unprocess = 0
    #save_cache = {'_id': ObjectId(task_id), 'devices': {}, 'created_time': now, 'unprocess': int(unprocess),'query_result':query_result}
    save_cache = {'_id': ObjectId(task_id), 'devices': {},
                  'created_time': now, 'unprocess': int(unprocess)}
    logger.debug('save_cache is %s' % save_cache)
    for k, v in list(all_cache.items()):
        v_obj = json.loads(v)
        save_cache['devices'][v_obj['name']] = v_obj
    try:
        s1_db.cert_query_result.insert_one(save_cache)
    except Exception:
        logger.debug('set_finished error is %s' % (traceback.format_exc()))
        return
    CERT_QUERY_CACHE.delete(res_cache_key)
    CERT_QUERY_CACHE.delete(dev_num_cache_key)
    CERT_QUERY_CACHE.delete(failed_cache_key)
    CERT_QUERY_CACHE.delete(success_cache_key)


def get_error_dev_result(task_info):
    '''
    获取执行中　非200的失败列表
    '''
    error_list = []
    if not task_info:
        logger.debug("get_error_dev_result no task_info")
        return error_list
    logger.debug("get_error_dev_result task_id:%s" % (task_info['_id']))
    if task_info['status'] != "PROGRESS":
        logger.debug("get_error_dev_result task_id:%s status not PROGRESS" % (task_info['_id']))
        return error_list

    res_cache_key = '%s_res' % (task_info['_id'])
    res_cache = CERT_QUERY_CACHE.hgetall(res_cache_key)
    if not res_cache:
        return error_list

    for k, v in list(res_cache.items()):
        v_obj = json.loads(v)
        if v_obj['result_status'] != 200:
            error_list.append({'host': v_obj['host'], 'code': v_obj[
                              'result_status'], 'name': v_obj['name'], 'type': v_obj['type']})
    return error_list


def make_op_log(username, remote_ip, cert_ids, _type):
    '''
    生成操作日志
    '''
    s1_db.query_op_log.insert({"username": username, "remote_ip": remote_ip,
                               "task_ids": cert_ids, "type": _type, "created_time": datetime.datetime.now()})
