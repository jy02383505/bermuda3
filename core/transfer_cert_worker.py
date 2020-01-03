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
from core import transfer_cert_postal
from Crypto.Hash import SHA256
from pymongo.errors import DuplicateKeyError
from pymongo import ReturnDocument
from util import log_utils, rsa_tools, tools
from core.update import db_update
from core.link_detection_all import link_detection_cert, get_failed_cert_devs
from .config import config
import logging
import random

#from  util.link_portal_cms import cert_portal_delete,cert_cms_delete

WORKER_HOST = socket.gethostname()
TRANSFER_CERT_CACHE = redisfactory.getDB(4)
s1_db = database.s1_db_session()
db = database.db_session()
logger = log_utils.get_transfer_cert_worker_Logger()
api_rcms_obj = api_rcms.ApiRCMS()
api_obj = api_hope.ApiHOPE()

ERROR_HOSTS_DIR = '/Application/bermuda3/logs/cert_failed/'


@task(ignore_result=True, default_retry_delay=10, max_retries=3)
def dispatch(tasks):
    try:
        logger.debug("transfer  expired_cert begin %s" % len(tasks))
        logger.debug("transfer  expired_cert begin task_ids %s" % [i['_id'] for i in tasks])
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
            save_task['path'] = task.get('path')
            save_task['username'] = task.get('username')
            save_task['t_id'] = task.get('t_id')
            save_task['send_devs'] = task.get('send_dev')
            save_task['created_time'] = task.get('created_time')
            save_task['save_name'] = task.get('save_name')
            save_task['worker_host'] = WORKER_HOST
            save_tasks.append(save_task)
            make_result_cache(task['_id'], devs_dict)

        s1_db.transfer_cert_tasks.insert(save_tasks)
        worker(tasks, devs)

        # try:
        #     task_id_list = []
        #     for task in tasks:
        #         for sav_name in task['save_name'].split(','):
        #             info_cert = s1_db.cert_detail.find_one({'save_name': sav_name})
        #             task_id_list.append(str(info_cert['_id']))
        #     status = cert_cms_delete(task_id_list)
        #     if status:
        #             cert_portal_delete(task_id_list)
        # except Exception,e:
        #     logger.error('callback error %s'%(e.message))

        logger.debug("transfer cert trans end")
    except Exception:
        logger.debug("trasnfer cert trans error:%s " % traceback.format_exc())


def init_cert_dev(task):

    if task['send_dev'] == 'all_dev':

        #all_devs, devs_dict = get_all_hpcc_devs_by_rcms()
        all_devs, devs_dict = get_all_hpcc_devs()
        # 生成results cache
        if not all_devs:
            raise
    else:
        cache_key = task['send_dev_md5']
        all_devs = []
        devs_dict = {}
        cache_dict = {}
        send_dev = task['send_dev']
        logger.debug("send_dev:%s" % send_dev)
        logger.debug("send_dev type is:%s" % type(send_dev))
        logger.debug("send_dev len is:%s" % len(send_dev))
        for dev_ip in send_dev:
            # 根据设备的ip匹配出设备的name
            device_group = 'HPCC'
            device_name = tools.get_dev_infobyip(dev_ip)[0]
            logger.debug('device_name is %s' % device_name)
            #all_devs.append({'name': device_name, 'ip': dev_ip, 'type':device_group})
            dev = {'name': device_name, 'host': dev_ip, 'code': 0, 'type': device_group}
            logger.debug('dev is : %s' % dev)
            all_devs.append(dev)
            devs_dict[device_name] = dev
            cache_dict[device_name] = json.dumps(dev)

        TRANSFER_CERT_CACHE.hmset(cache_key, cache_dict)

    dev_id = s1_db.transfer_cert_dev.insert(
        {'devices': devs_dict, 'created_time': datetime.datetime.now(), 'unprocess': len(all_devs)})
    return dev_id, all_devs, devs_dict


def get_all_hpcc_devs_by_rcms(task):
    '''
    获取所有hpcc rcms
    '''
    cache_key = task['send_dev_md5']
    res = []
    res_dict = {}
    cache_dict = {}
    t1 = time.time()
    all_devs = api_rcms_obj.read_allHpcc_rcms()
    t2 = time.time()
    logger.debug("all_hpcc devs rcms get cost %s seconds" % (t2 - t1))
    if all_devs:
        all_info = json.loads(all_devs)
        for d in all_info:
            _dev = {'name': d['devName'], 'host': d['devAdminIP'], 'code': 0, 'type': 'HPCC'}
            res.append(_dev)
            res_dict[d['devName']] = _dev
            cache_dict[d['devName']] = json.dumps(_dev)
        if cache_dict:
            TRANSFER_CERT_CACHE.delete(cache_key)
            TRANSFER_CERT_CACHE.hmset(cache_key, cache_dict)
    t3 = time.time()
    logger.debug("all_hpcc devs rcms filter cost %s seconds all_devs count %s" %
                 (t3 - t2, len(res)))

    if not all_devs:
        _cache = TRANSFER_CERT_CACHE.hgetall(cache_key)
        res = [json.loads(i) for i in list(_cache.values())]
        res_dict = {i: json.loads(v) for i, v in list(_cache.items())}

    return res, res_dict


def get_all_hpcc_devs():
    '''
    获取所有hpcc (hope)
    '''
    cache_key = 'hpcc_all_devs'
    res = []
    res_dict = {}
    cache_dict = {}
    t1 = time.time()
    all_devs = api_obj.read_allHpcc_cache_hope()
    t2 = time.time()
    logger.debug("all_hpcc devs get cost %s seconds" % (t2 - t1))
    _host = []

    if all_devs:
        all_info = json.loads(all_devs)
        for d in all_info['data']:
            if d['device_group'] in ['H_D_CACHE', 'H_P_CACHE', 'H_V_CACHE'] or 'Single' in d['device_group']:
                if d['ip'] in _host:
                    continue
                if d['rcms_status'] in ['SUSPEND', 'CLOSE']:
                    continue
                if d['deviceState'] == "Online":
                    _dev = {'name': d['device_name'], 'host': d[
                        'ip'], 'code': 0, 'type': d['device_group']}
                    res.append(_dev)
                    res_dict[d['device_name']] = _dev
                    cache_dict[d['device_name']] = json.dumps(_dev)
                    _host.append(d['ip'])

        if cache_dict:
            TRANSFER_CERT_CACHE.delete(cache_key)
            TRANSFER_CERT_CACHE.hmset(cache_key, cache_dict)

    t3 = time.time()
    logger.debug("all_hpcc devs filter cost %s seconds" % (t3 - t2))
    if not res:
        _cache = TRANSFER_CERT_CACHE.hgetall(cache_key)
        res = [json.loads(i) for i in list(_cache.values())]
        res_dict = {i: json.loads(v) for i, v in list(_cache.items())}

    return res, res_dict


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
        faild_list = get_failed_cert_devs(tasks[0].get("dev_id"), results, 'transfer_cert_dev')
        logger.debug('---worker subsenter faild_list len %s----' % (len(faild_list)))

        if faild_list:
            Interface = 'transfer_cert'
            link_detection_cert.delay(tasks, faild_list, Interface)

        # check_cert_task
        check_transfer_cert_task.apply_async(([i['_id'] for i in tasks],), countdown=120)

        #make_all_callback_force([i['_id'] for i in tasks])

    except Exception:

        #make_all_callback_force([i['_id'] for i in tasks])
        logger.debug('transfer_cert worker error is %s' % (traceback.format_exc()))


@task(ignore_result=True, default_retry_delay=5, max_retries=3)
def check_transfer_cert_task(task_ids):
    '''
    n seconds 后检查任务状态
    '''
    logger.debug('---check_transfer_cert_task start task_ids: %s---' % (task_ids))

    task_info_list = s1_db.transfer_cert_tasks.find(
        {'_id': {'$in': [ObjectId(task_id) for task_id in task_ids]}, 'status': 'PROGRESS'})
    if task_info_list.count() == 0:
        logger.debug('---check_transfer_cert_task no task_info  ids: %s---' % (task_ids))
        return

    for task_info in task_info_list:

        error_devs = get_error_dev_result(task_info)
        if not error_devs:
            continue
        set_finished(task_info['_id'], 'FAILED')
        logger.debug('---check_transfer_cert_task id %s set Failed end---' % (task_info['_id']))

    return


def update_db_dev(dev_id, results):
    '''
    更新任务状态　transfer_cert_dev & transfer_cert_tasks
    '''
    try:

        now = datetime.datetime.now()
        db_dev = s1_db.transfer_cert_dev.find_one({"_id": ObjectId(dev_id)})
        db_dev["finish_time"] = now
        devices = db_dev.get("devices")
        for ret in results:
            devices.get(ret.get("name"))["code"] = ret.get("code", 0)
            devices.get(ret.get("name"))["a_code"] = ret.get("a_code", 0)
            devices.get(ret.get("name"))["r_code"] = ret.get("r_code", 0)
            db_dev["unprocess"] = int(db_dev.get("unprocess")) - 1
        update_dev = copy.deepcopy(db_dev)
        if '_id' in update_dev:
            update_dev.pop('_id')
        s1_db.transfer_cert_dev.update_one({"_id": ObjectId(dev_id)}, {'$set': update_dev})
        s1_db.transfer_cert_tasks.update_many({'dev_id': ObjectId(dev_id)}, {
                                              '$set': {'finish_time': now}})

    except Exception:
        logger.debug('transfer_cert update_db_dev error is %s' % (traceback.format_exc()))


def send(devs, tasks):
    '''
    下发任务
    '''
    try:

        dev_map = {}
        [dev_map.setdefault(d.get('host'), d) for d in devs]
        logger.debug("dev_map is %s" % dev_map)
        Interface = 'transfer_cert'
        ret, ret_faild = transfer_cert_postal.doloop_url(devs, tasks, Interface)
        results, error_result = transfer_cert_postal.process_loop_ret(ret, dev_map)

        results_faild_dic = transfer_cert_postal.process_loop_ret_faild(ret_faild, dev_map)
        if dev_map:
            # 重试
            try:
                results_faild_dic.update(error_result)
                retry_results = transfer_cert_postal.retry(
                    list(dev_map.values()), tasks, results_faild_dic, Interface)
            except Exception:
                retry_results = []
                logger.error('----transfer_cert  send retry error-----')
                logger.error(traceback.format_exc())
            results += retry_results
        return results

    except Exception:
        logger.error("transfer cert send error:%s " % e)
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

    TRANSFER_CERT_CACHE.hmset('%s_res' % (task_id), save_cache)
    TRANSFER_CERT_CACHE.set('%s_res_dev_num' % (task_id), len(save_cache))


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
        transfer_result = data.get('info', '')
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
        info_str = TRANSFER_CERT_CACHE.hget(res_cache_key, remote_ip)
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
        info['result'] = transfer_result
        logger.debug('save_result to save redis  info is %s remote_ip is %s' % (info, remote_ip))
        TRANSFER_CERT_CACHE.hset(res_cache_key, remote_ip, json.dumps(info))
        logger.debug('save_result to save redis  remote_ip is %s over' % (remote_ip))
        if status == 200:
            before_success_num = TRANSFER_CERT_CACHE.scard(success_cache_key)
            logger.debug('save_result add count success remote_ip %s before_success_num %s' %
                         (remote_ip, before_success_num))
            TRANSFER_CERT_CACHE.sadd(success_cache_key, remote_ip)
        else:
            TRANSFER_CERT_CACHE.sadd(failed_cache_key, remote_ip)
            logger.debug('save_result add count failed remote_ip %s' % (remote_ip))

        success_num = TRANSFER_CERT_CACHE.scard(success_cache_key)
        failed_num = TRANSFER_CERT_CACHE.scard(failed_cache_key)
        all_dev_num = TRANSFER_CERT_CACHE.get(dev_num_cache_key)

        logger.debug('save_result remote_ip %s success_num %s, failed_num %s, all_count %s' %
                     (remote_ip, success_num, failed_num, all_dev_num))
        if int(success_num) == int(all_dev_num):
            logger.debug('success_num is %s' % success_num)
            # 全部成功
            logger.debug('task_id is %s' % task_id)
            #set_finished(task_id, 'FINISHED',query_result)
            set_finished(task_id, 'FINISHED')
            #s1_db.cert_detail.update({'save_name':save_name},{"$set" : {"t_id" : t_id}});
        elif int(failed_num) == int(all_dev_num):
            # TODO
            task_info = s1_db.transfer_cert_tasks.find_one({'_id': ObjectId(task_id)})
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
    task_info = s1_db.transfer_cert_tasks.find_one_and_update({'_id': ObjectId(task_id), 'status': "PROGRESS"}, {
                                                              "$set": {'status': status, 'hpc_finish_time': now}}, return_document=ReturnDocument.AFTER)
    # cache -> mongo
    res_cache_key = '%s_res' % (task_id)
    dev_num_cache_key = '%s_res_dev_num' % (task_id)
    failed_cache_key = '%s_res_failed' % (task_id)
    success_cache_key = '%s_res_success' % (task_id)
    all_cache = TRANSFER_CERT_CACHE.hgetall(res_cache_key)
    all_dev_num = TRANSFER_CERT_CACHE.get(dev_num_cache_key)
    success_num = TRANSFER_CERT_CACHE.scard(success_cache_key)
    unprocess = int(all_dev_num) - int(success_num)
    logger.debug('unprocess is %s' % unprocess)
    if unprocess <= 0:
        unprocess = 0
    #save_cache = {'_id': ObjectId(task_id), 'devices': {}, 'created_time': now, 'unprocess': int(unprocess),'query_result':query_result}
    save_cache = {'_id': ObjectId(task_id), 'devices': {},
                  'created_time': now, 'unprocess': int(unprocess)}
    for k, v in list(all_cache.items()):
        v_obj = json.loads(v)
        save_cache['devices'][v_obj['name']] = v_obj
    logger.debug('save_cache is %s' % save_cache)
    try:
        s1_db.transfer_cert_result.insert_one(save_cache)
    except Exception:
        logger.debug('set_finished error is %s' % (traceback.format_exc()))
        return
    TRANSFER_CERT_CACHE.delete(res_cache_key)
    TRANSFER_CERT_CACHE.delete(dev_num_cache_key)
    TRANSFER_CERT_CACHE.delete(failed_cache_key)
    TRANSFER_CERT_CACHE.delete(success_cache_key)


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
    res_cache = TRANSFER_CERT_CACHE.hgetall(res_cache_key)
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
    s1_db.transfer_cert_op_log.insert({"username": username, "remote_ip": remote_ip,
                                       "task_ids": cert_ids, "type": _type, "created_time": datetime.datetime.now()})


def store_error_host(cert_id, error_list):

    try:
        if not os.path.exists(ERROR_HOSTS_DIR):
            os.makedirs(ERROR_HOSTS_DIR)
        with open('%shpcc_%s.txt' % (ERROR_HOSTS_DIR, cert_id), 'w') as file_w:
            for e in error_list:
                file_w.write(e['ip'] + '\n')
        return ERROR_HOSTS_DIR + 'hpcc_%s.txt' % (cert_id)

    except Exception:
        logger.debug('store_all_urls error:%s' % traceback.format_exc())
        return None
