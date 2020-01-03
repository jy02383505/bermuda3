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
from core import cert_trans_postal
from Crypto.Hash import SHA256
from pymongo.errors import DuplicateKeyError
from pymongo import ReturnDocument
from util import log_utils, rsa_tools
from core.update import db_update
from core.link_detection_all import link_detection_cert, get_failed_cert_devs
from .config import config
import string
import hashlib


WORKER_HOST = socket.gethostname()
CERT_TRANS_CACHE = redisfactory.getDB(10)
CERT_PULL_CACHE = redisfactory.getDB(1)
s1_db = database.s1_db_session()
db = database.db_session()
logger = log_utils.get_cert_worker_Logger()
api_rcms_obj = api_rcms.ApiRCMS()
api_obj = api_hope.ApiHOPE()
#PORTAL_URL = 'http://113.105.10.252:8888/rest-api/internal/config/certificate/status'
#PORTAL_URL = 'http://portal.chinacache.com/rest-api/internal/config/certificate/status'
PORTAL_URL = config.get('cert_trans', 'portal_callback')
# rcms
#RCMS_URL = 'http://223.202.75.86:8080/phoenix/api/9040/addCrtInfo'
# cms
#RCMS_URL = 'http://223.202.75.136:32000/bm-app/apiw/9040/addCrtInfo'

RCMS_URL = config.get('cert_trans', 'rcms_callback')

# 中央生成zip位置
CERT_DIR = '/Application/bermuda3/static/certs/'
ERROR_HOSTS_DIR = '/Application/bermuda3/logs/cert_failed/'


@task(ignore_result=True, default_retry_delay=10, max_retries=3)
def dispatch(tasks):
    '''
    分发证书
    [{‘key’:xx,’cert’:xx, seed: xxx, dir:xxx, send_devs:’all_hpcc’, 'task_id':xxx} ]
    '''
    try:
        logger.debug("dispatch cert trans  begin %s" % len(tasks))
        logger.debug("dispatch cert trans  begin task_ids %s" % [i['_id'] for i in tasks])
        dev_id, devs, devs_dict = init_cert_devs(tasks[0]['send_devs'])
        logger.debug("cert_devs dev_id %s, devs len %s" % (dev_id, len(devs)))
        save_tasks = []
        for task in tasks:

            task['dev_id'] = dev_id

            save_task = {}
            save_task['_id'] = ObjectId(task['_id'])
            save_task['status'] = "PROGRESS"
            save_task['dev_id'] = dev_id
            save_task['username'] = task.get('username')
            save_task['user_id'] = task.get('user_id')
            save_task['c_id'] = task.get('c_id', '')
            save_task['o_c_id'] = task.get('o_c_id', '')
            save_task['cert_alias'] = task.get('cert_alias', '')
            save_task['send_devs'] = task.get('send_devs', '')
            save_task['created_time'] = task.get('created_time')
            save_task['recev_host'] = task.get('recev_host')
            save_task['worker_host'] = WORKER_HOST
            save_task['rcms_callback_time'] = ''
            save_task['portal_callback_time'] = ''
            save_tasks.append(save_task)
            make_result_cache(task['_id'], devs_dict)

        s1_db.cert_trans_tasks.insert(save_tasks)
        worker(tasks, devs)
        logger.debug("dispatch cert trans end")
    except Exception:
        logger.debug("dispatch cert trans error:%s " % traceback.format_exc())


def init_cert_devs(send_devs):
    '''
    生成证书下发设备组
    '''
    if send_devs == 'all_hpcc':

        #all_devs, devs_dict = get_all_hpcc_devs_by_rcms()
        all_devs, devs_dict = get_all_hpcc_devs()
        #all_devs = [{'name': 'BGP-SM-e-3gL', 'host': '223.202.203.53', 'type':'make_test'},{'name': 'BGP-SM-3-3gE', 'host': '223.202.201.165', 'type':'make_test'}]
        #devs_dict = {'SM-test':{'name': 'SM-test', 'host': '223.202.203.53', 'type':'make_test'}}
        #devs_dict = {'BGP-SM-e-3gL':{'name': 'BGP-SM-e-3gL', 'host': '223.202.203.53', 'type':'make_test'}, 'BGP-SM-3-3gE':{'name': 'BGP-SM-3-3gE', 'host': '223.202.201.165', 'type':'make_test'}}
        all_devs = [dev for dev in all_devs if dev.get('host')]

        try:
            all_devs_sms, devs_dict_sms = get_all_sms_devs()
            all_devs_sms = [dev_sms for dev_sms in all_devs_sms if dev_sms.get('host')]
            all_devs.extend(all_devs_sms)
            devs_dict.update(devs_dict_sms)
        except Exception:
            logger.debug('get sms devices fail')

        # 生成results cache
        if not all_devs:
            raise
    else:
        raise
    dev_id = s1_db.cert_trans_dev.insert(
        {'devices': devs_dict, 'created_time': datetime.datetime.now(), 'unprocess': len(all_devs)})
    return dev_id, all_devs, devs_dict


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
            CERT_TRANS_CACHE.delete(cache_key)
            CERT_TRANS_CACHE.hmset(cache_key, cache_dict)

    t3 = time.time()
    logger.debug("all_hpcc devs filter cost %s seconds" % (t3 - t2))

    if not res:
        _cache = CERT_TRANS_CACHE.hgetall(cache_key)
        res = [json.loads(i) for i in list(_cache.values())]
        res_dict = {i: json.loads(v) for i, v in list(_cache.items())}

    return res, res_dict


def get_all_sms_devs():
    '''
    获取所有sms (hope)
    '''
    cache_key = 'sms_all_devs'
    res = []
    res_dict = {}
    cache_dict = {}
    t1 = time.time()
    all_devs = api_obj.read_all_sms_cache_hope()
    t2 = time.time()
    logger.debug("all_sms devs get cost %s seconds" % (t2 - t1))
    _host = []

    if all_devs:
        all_info = json.loads(all_devs)
        for d in all_info['data']:
            if d['device_group'] in ['sms001'] or 'Single' in d['device_group']:
                if d['ip'] in _host:
                    continue
                if d['rcms_status'] in ['SUSPEND', 'CLOSE']:
                    continue
                # if d['deviceState'] == "Online":#sms devices don't have this status
                _dev = {'name': d['device_name'], 'host': d[
                    'ip'], 'code': 0, 'type': d['device_group']}
                res.append(_dev)
                res_dict[d['device_name']] = _dev
                cache_dict[d['device_name']] = json.dumps(_dev)
                _host.append(d['ip'])

        if cache_dict:
            CERT_TRANS_CACHE.delete(cache_key)
            CERT_TRANS_CACHE.hmset(cache_key, cache_dict)

    t3 = time.time()
    logger.debug("all_sms devs filter cost %s seconds" % (t3 - t2))

    if not res:
        _cache = CERT_TRANS_CACHE.hgetall(cache_key)
        res = [json.loads(i) for i in list(_cache.values())]
        res_dict = {i: json.loads(v) for i, v in list(_cache.items())}

    return res, res_dict


def get_all_hpcc_devs_by_rcms():
    '''
    获取所有hpcc rcms
    '''
    cache_key = 'hpcc_all_devs'
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
            CERT_TRANS_CACHE.delete(cache_key)
            CERT_TRANS_CACHE.hmset(cache_key, cache_dict)
    t3 = time.time()
    logger.debug("all_hpcc devs rcms filter cost %s seconds all_devs count %s" %
                 (t3 - t2, len(res)))

    if not all_devs:
        _cache = CERT_TRANS_CACHE.hgetall(cache_key)
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
        update_db_dev(tasks[0].get("dev_id"), results)
        # subsenter
        faild_list = get_failed_cert_devs(tasks[0].get("dev_id"), results, 'cert_trans_dev')
        logger.debug('---worker subsenter faild_list len %s----' % (len(faild_list)))

        if faild_list:
            link_detection_cert.delay(tasks, faild_list)

        # check_cert_task
        check_cert_task.apply_async(([i['_id'] for i in tasks],), countdown=180)

        make_all_callback_force([i['_id'] for i in tasks])

    except Exception:

        #make_all_callback_force([i['_id'] for i in tasks])
        logger.debug('cert trans worker error is %s' % (traceback.format_exc()))


@task(ignore_result=True, default_retry_delay=5, max_retries=3)
def check_cert_task(task_ids):
    '''
    n seconds 后检查任务状态
    '''
    logger.debug('---check_cert_task start task_ids: %s---' % (task_ids))

    callback_list = s1_db.cert_trans_tasks.find(
        {'_id': {'$in': [ObjectId(task_id) for task_id in task_ids]}, 'status': 'FINISHED'})
    # 尝试2次回调
    for c in callback_list:
        if not c['rcms_callback_time'] or not c['portal_callback_time']:
            cert_info = s1_db.cert_detail.find_one({'_id': ObjectId(c['c_id'])})
            logger.debug('---check_cert_task  retry callback task_id %s  cert_id %s---' %
                         (c['_id'], c['c_id']))
            make_all_callback(c, cert_info)

    task_info_list = s1_db.cert_trans_tasks.find(
        {'_id': {'$in': [ObjectId(task_id) for task_id in task_ids]}, 'status': 'PROGRESS'})
    if task_info_list.count() == 0:
        logger.debug('---check_cert_task no task_info  ids: %s---' % (task_ids))
        return

    for task_info in task_info_list:

        error_devs = get_error_dev_result(task_info)
        if not error_devs:
            continue
        send_error_email(task_info, error_devs)
        logger.debug('---check_cert_task id %s set Failed begin---' % (task_info['_id']))
        set_finished(task_info['_id'], 'FAILED')
        logger.debug('---check_cert_task id %s set Failed end---' % (task_info['_id']))

    # 尝试再次回调，无状态
    make_all_callback_force(task_ids)

    logger.debug('---check_cert_task  end task_ids: %s---' % (task_ids))

    return


def update_db_dev(dev_id, results):
    '''
    更新任务状态　cert_trans_dev&cert_trans_tasks
    '''
    try:
        now = datetime.datetime.now()
        db_dev = s1_db.cert_trans_dev.find_one({"_id": ObjectId(dev_id)})
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
        s1_db.cert_trans_dev.update_one({"_id": ObjectId(dev_id)}, {'$set': update_dev})
        s1_db.cert_trans_tasks.update_many({'dev_id': ObjectId(dev_id)}, {
                                           '$set': {'finish_time': now}})

    except Exception:
        logger.debug('cert update_db_dev error is %s' % (traceback.format_exc()))


def send(devs, tasks):
    '''
    发生至设备
    '''
    try:

        dev_map = {}
        [dev_map.setdefault(d.get('host'), d) for d in devs]
        ret, ret_faild = cert_trans_postal.doloop(devs, tasks)
        results, error_result = cert_trans_postal.process_loop_ret(ret, dev_map)

        results_faild_dic = cert_trans_postal.process_loop_ret_faild(ret_faild, dev_map)
        if dev_map:
            # 重试
            try:
                results_faild_dic.update(error_result)
                retry_results = cert_trans_postal.retry(
                    list(dev_map.values()), tasks, results_faild_dic)
            except Exception:
                retry_results = []
                logger.error('----cert trans send retry error-----')
                logger.error(traceback.format_exc())
            results += retry_results
        return results

    except Exception:
        logger.error("cert send error:%s " % e)
        logger.error(traceback.format_exc())


def get_custom_seed(username):
    '''
    获取用户seed
    '''
    cache_key = 'cert_seed_%s' % (username)
    seed = CERT_TRANS_CACHE.get(cache_key)
    if not seed:
        seed_info = db.cert_user_seed.find_one({'username': username})
        if seed_info:
            seed = seed_info.get('seed')
            CERT_TRANS_CACHE.set(cache_key, seed)
        else:
            # 创建seed
            _hash = SHA256.new()
            _hash.update('%s_%s' % (username, time.time()))
            seed = base64.b64encode(_hash.digest())
            try:
                db.cert_user_seed.insert_one(
                    {'username': username, 'seed': seed, 'created_time': datetime.datetime.now()})
            except DuplicateKeyError as e:
                seed_info = db.cert_user_seed.find_one({'username': username})
                seed = seed_info.get('seed')
                CERT_TRANS_CACHE.set(cache_key, seed)

    logger.debug("get_custom_seed username:%s seed:%s" % (username, seed))

    return seed


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

    CERT_TRANS_CACHE.hmset('%s_res' % (task_id), save_cache)
    CERT_TRANS_CACHE.set('%s_res_dev_num' % (task_id), len(save_cache))


@task(ignore_result=True, default_retry_delay=10, max_retries=3)
def save_result(data_list, remote_ip):
    '''
    存储状态
    '''
    logger.debug('save_result begin data_list %s remote_ip %s' % (data_list, remote_ip))
    now = datetime.datetime.now()
    for data in data_list:

        task_id = data.get('task_id', '')
        task_id = task_id.replace('\n', '')
        task_id = task_id.replace('"', '')
        status = int(data.get('status', 0))
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
        info_str = CERT_TRANS_CACHE.hget(res_cache_key, remote_ip)
        logger.debug('save_result hget cache_key %s  ,remote_ip %s' % (res_cache_key, remote_ip))

        if not info_str:
            logger.debug('save_result no cache id %s remote_ip %s' % (task_id, remote_ip))
            continue
        info = json.loads(info_str)
        if info['result_status'] == 200:
            logger.debug('save_result had 200 id %s remote_ip %s' % (task_id, remote_ip))
            continue
        info['update_time'] = time.time()
        info['result_status'] = status
        logger.debug('save_result to save redis  info is %s remote_ip is %s' % (info, remote_ip))
        CERT_TRANS_CACHE.hset(res_cache_key, remote_ip, json.dumps(info))
        logger.debug('save_result to save redis  remote_ip is %s over' % (remote_ip))
        if status == 200:
            before_success_num = CERT_TRANS_CACHE.scard(success_cache_key)
            logger.debug('save_result add count success remote_ip %s before_success_num %s' %
                         (remote_ip, before_success_num))
            CERT_TRANS_CACHE.sadd(success_cache_key, remote_ip)
        else:
            CERT_TRANS_CACHE.sadd(failed_cache_key, remote_ip)
            logger.debug('save_result add count failed remote_ip %s' % (remote_ip))

        success_num = CERT_TRANS_CACHE.scard(success_cache_key)
        failed_num = CERT_TRANS_CACHE.scard(failed_cache_key)
        all_dev_num = CERT_TRANS_CACHE.get(dev_num_cache_key)

        logger.debug('save_result remote_ip %s success_num %s, failed_num %s, all_count %s' %
                     (remote_ip, success_num, failed_num, all_dev_num))
        if int(success_num) == int(all_dev_num):
            # 全部成功
            set_finished(task_id, 'FINISHED')
        elif int(failed_num) == int(all_dev_num):
            # TODO
            task_info = s1_db.cert_trans_tasks.find_one({'_id': ObjectId(task_id)})
            error_list = get_error_dev_result(task_info)
            send_error_email(task_info, error_list)
            set_finished(task_id, 'FAILED')


def set_finished(task_id, status):
    '''
    to finish
    '''
    now = datetime.datetime.now()
    task_info = s1_db.cert_trans_tasks.find_one_and_update({'_id': ObjectId(task_id), 'status': "PROGRESS"}, {
                                                           "$set": {'status': status, 'hpc_finish_time': now}}, return_document=ReturnDocument.AFTER)
    # cache -> mongo
    res_cache_key = '%s_res' % (task_id)
    dev_num_cache_key = '%s_res_dev_num' % (task_id)
    failed_cache_key = '%s_res_failed' % (task_id)
    success_cache_key = '%s_res_success' % (task_id)
    all_cache = CERT_TRANS_CACHE.hgetall(res_cache_key)
    all_dev_num = CERT_TRANS_CACHE.get(dev_num_cache_key)
    success_num = CERT_TRANS_CACHE.scard(success_cache_key)
    unprocess = int(all_dev_num) - int(success_num)
    if unprocess <= 0:
        unprocess = 0
    save_cache = {'_id': ObjectId(task_id), 'devices': {},
                  'created_time': now, 'unprocess': int(unprocess)}
    for k, v in list(all_cache.items()):
        v_obj = json.loads(v)
        save_cache['devices'][v_obj['name']] = v_obj
    try:
        s1_db.cert_trans_result.insert_one(save_cache)
    except Exception:
        logger.debug('set_finished error is %s' % (traceback.format_exc()))
        return
    CERT_TRANS_CACHE.delete(res_cache_key)
    CERT_TRANS_CACHE.delete(dev_num_cache_key)
    CERT_TRANS_CACHE.delete(failed_cache_key)
    CERT_TRANS_CACHE.delete(success_cache_key)

    if status == 'FINISHED':
        cert_info = s1_db.cert_detail.find_one({'_id': ObjectId(task_info['c_id'])})
        make_all_callback(task_info, cert_info)


def make_dir_name(username):
    '''
    生成随机目录
    '''
    num1 = random.randint(0, 1000)
    num2 = random.randint(0, 1000)
    ISOTIMEFORMAT = '%Y%m%d%H%M%S'
    t_s = time.strftime(ISOTIMEFORMAT)
    
    md5_str = '%s_%s_%s' % (username, num1, num2)
    _md5_num = hashlib.md5(md5_str.encode(encoding='utf-8')).hexdigest()
    name = _md5_num + '_' + t_s
    return name


def make_dir(username):
    '''
    生成目录
    '''
    for x in range(2):
        dir_name = make_dir_name(username)
        if os.path.isdir(CERT_DIR + dir_name):
            if x == 0:
                continue
            else:
                raise
        else:
            break
    os.makedirs(CERT_DIR + dir_name)

    return dir_name


def get_cert_by_task_id(task_id):
    '''
    通过任务ID 获取证书/私钥/存储名
    '''
    cert_res = {}
    task_info = s1_db.cert_trans_tasks.find_one({'_id': ObjectId(task_id)})
    if not task_info:
        return cert_res
    cert_id = task_info.get('c_id', '')
    if not cert_id:
        return cert_res
    cert_info = s1_db.cert_detail.find_one({'_id': ObjectId(cert_id)})
    if not cert_info:
        return cert_res

    return get_cert_detail(cert_info)


def get_cert_detail(cert_info):
    '''
    通过任务ID 获取证书/私钥/存储名
    '''
    cert_res = {}
    if not cert_info:
        return cert_res

    cert_trunk, _ = rsa_tools.split_ciphertext_and_sign(cert_info['cert'])
    cert_orgin_encry = rsa_tools.deal(base64.b64decode(cert_trunk), cert_info['seed'])
    cert_orgin = rsa_tools.decrypt_trunk(cert_orgin_encry, rsa_tools.bermuda_pri_key)

    cert_pk_trunk, _ = rsa_tools.split_ciphertext_and_sign(cert_info['p_key'])
    cert_pk_encry = rsa_tools.deal(base64.b64decode(cert_pk_trunk), cert_info['seed'])
    cert_pk = rsa_tools.decrypt_trunk(cert_pk_encry, rsa_tools.bermuda_pri_key)

    return {'cert': cert_orgin, 'p_key': cert_pk, 'save_name': cert_info['save_name'], 'cert_type': cert_info.get('cert_type', 'crt')}


def get_cert_by_ids(cert_ids):
    '''
    通过任务IDS 获取证书/私钥/存储名
    '''
    cert_info_list = s1_db.cert_detail.find({'_id': {'$in': [ObjectId(i) for i in cert_ids]}})
    all_res = []
    for cert_info in cert_info_list:
        res = get_cert_detail(cert_info)
        if res:
            all_res.append(res)
    return all_res


def get_all_cert(ignore_n=[]):
    '''
    获取所有证书
    '''
    if ignore_n:
        all_cert = s1_db.cert_detail.find({'save_name': {'$not': {'$in': ignore_n}}})
    else:
        all_cert = s1_db.cert_detail.find()

    all_res = []
    for cert in all_cert:
        res = get_cert_detail(cert)
        all_res.append(res)

    return all_res


def get_all_cert_by_dev(ignore_n, ignore_transfer=False):
    '''
    获取所有证书
    cert p_key s_name op_type cert_type task_id seed s_dir
    '''
    s_dir = config.get('cert_trans', 'cache_dir')
    if ignore_transfer:
        all_cert = s1_db.cert_detail.find(
            {'save_name': {'$not': {'$in': ignore_n}}, 't_id': {"$exists": False}})
    else:
        all_cert = s1_db.cert_detail.find({'save_name': {'$not': {'$in': ignore_n}}})

    all_res = []

    for cert_info in all_cert:

        _data = {'s_name': cert_info['save_name'], 'op_type': 'pull',
                 'cert_type': cert_info.get('cert_type', 'crt'), 's_dir': s_dir}
        _data['cert'] = cert_info['cert']
        _data['p_key'] = cert_info['p_key']
        _data['task_id'] = cert_info['save_name']
        _data['seed'] = cert_info['seed']

        all_res.append(_data)

    return all_res


def get_cert_transferAndadd(ver):
    '''
    从mongo获取证书下发和证书转移数据
    '''
    all_res = []
    res = {}
    # db=get_db()
    t = time.strftime('%Y%m%d')
    version = int(ver)
    all_cert = s1_db.cert_update_pull.find({"update_time": {"$lte": int(t), "$gte": int(version)}})
    # print all_cert
    res["add_cert"] = []
    res["transfer_cert"] = []
    for info in all_cert:
        res["add_cert"] += info["add_cert"]
        res["transfer_cert"] += info["transfer_cert"]
    # return res["transfer_cert_savename"]
    return res


def get_allcertdata_from_redis(ver):
    '''
    从reids获取夜里同步数据
    '''
    # r=get_r()
    t = time.strftime('%Y%m%d')
    today = int(t)
    res = {}
    res["add_cert"] = []
    res["transfer_cert"] = []
    version = int(ver)
    for num in range(version, today + 1):
        inf = CERT_PULL_CACHE.hget("update_res", num)
        if inf != None:
            info = json.loads(inf)
            #print (info.keys())
            res["add_cert"] += info["add_cert"]
            res["transfer_cert"] += info["transfer_cert"]
    # return res["transfer_cert_savename"]
    return res


def make_all_callback(task_info, cert_info):
    '''
    执行所有回调
    '''
    now = datetime.datetime.now()
    task_id = str(task_info['_id'])
    rcms_callback_time = task_info.get('rcms_callback_time')
    portal_callback_time = task_info.get('portal_callback_time')
    if rcms_callback_time and portal_callback_time:
        logger.debug('----make_all_callback task_id %s had callback rcms in %s and callback portal in %s' %
                     (task_id, rcms_callback_time, portal_callback_time))
        return True

    cert_save_name = cert_info['save_name']
    rcms_body = {'ROOT': {'HEADER': {'AUTH_INFO': {'LOGIN_NO': 'refresh_preload', 'LOGIN_PWD': 'cert_2018_Q2', 'FUNC_CODE': '9040'}}, 'BODY': {'BUSI_INFO': {'CRT_INFO': {'extnId': task_info['c_id'], 'crtName': task_info['cert_alias'], 'userId': str(
        task_info.get('user_id', 2275)), 'isSafe': (lambda x: 'true' if x == False else 'false')(cert_info.get('middle_cert_lack', False)), 'crtFilename': '%s.crt' % (cert_save_name), 'keyFilename': '%s.key' % (cert_save_name)}}}}}

    to_portal = False
    if not rcms_callback_time:
        rcms_success = do_callback(RCMS_URL, 'rcms', rcms_body)
        if rcms_success:
            s1_db.cert_trans_tasks.find_one_and_update({'_id': ObjectId(task_id), 'rcms_callback_time': ""}, {
                                                       "$set": {'rcms_callback_time': now}})
            to_portal = True
            logger.debug('----make_all_callback task_id %s cert_id %s callback rcms success in %s' %
                         (task_id, task_info['c_id'], now))
    else:
        to_portal = True

    if to_portal and not portal_callback_time:
        #portal_success = do_callback(PORTAL_URL, 'portal', {'taskId':task_id})
        portal_success = do_callback_portal(PORTAL_URL, 'portal', {'taskId': task_id})
        if portal_success:
            s1_db.cert_trans_tasks.find_one_and_update({'_id': ObjectId(task_id), 'portal_callback_time': ""}, {
                                                       "$set": {'portal_callback_time': now}})
            logger.debug('----make_all_callback task_id %s cert_id %s callback portal success in %s' %
                         (task_id, task_info['c_id'], now))
            return True

    return False


def make_all_callback_force(task_ids):
    '''
    强行回调
    '''
    try:
        for t in task_ids:
            t_id = t
            t_obj = s1_db.cert_trans_tasks.find_one({'_id': ObjectId(t_id)})
            if t_obj:
                c_obj = s1_db.cert_detail.find_one({'_id': ObjectId(t_obj['c_id'])})
                logger.debug('make_all_callback_force begin task_id %s' % (t_id))
                make_all_callback(t_obj, c_obj)
            else:
                logger.debug('make_all_callback_force not begin task_id %s' % (t_id))

    except Exception:
        logger.debug('make_all_callback_force error e %s' % (e))


def get_cert_info(cert_id):

    if not cert_id:
        return None
    return s1_db.cert_detail.find_one({'_id': ObjectId(cert_id)})


def get_task_info_by_cert_id(cert_id):

    if not cert_id:
        return None
    return s1_db.cert_trans_tasks.find_one({'c_id': str(cert_id)})


def do_callback_portal(url, _type, command):
    is_success = False
    start_time = time.time()
    json_command = json.dumps(command)

    for x in range(2):

        try:
            access_key = '51e7713a8e9e7d31'
            access_secret = '85053e054c735430e12f12850397545f'

            timestamp = str(int(time.time()))
            nonce = "".join(random.sample(string.ascii_letters + string.digits, 10))
            str_list = [access_key, access_secret, timestamp, nonce]
            str_list_sorted = sorted(str_list)
            str_sorted = "".join(str_list_sorted)
            signature = hashlib.sha1(str_sorted).hexdigest()
            content_type = 'application/json'
            send_headers = {
                'X-CC-Auth-Key': access_key,
                'X-CC-Auth-Timestamp': timestamp,
                'X-CC-Auth-Nonce': nonce,
                'X-CC-Auth-Signature': signature
            }
            if content_type:
                send_headers["Content-Type"] = content_type

            rc = requests.post(url, data=json_command, timeout=(5, 5), headers=send_headers)
            rc.raise_for_status()
            response_body = rc.text
            res = json.loads(response_body)
            print(res)
            logger.debug('%s callback json command %s res is %s' % (_type, json_command, res))
            if _type == 'portal':
                if res['status'] in [0]:
                    is_success = True
                    break
                elif res['status'] in [2]:
                    break
            elif _type == 'rcms':
                if res['ROOT']['BODY']['RETURN_CODE'] == '0':
                    is_success = True
                    break
        except Exception:
            logger.error(
                "%s callback error command is %s, error is %s" % (_type, json_command, traceback.format_exc()))
            continue

    end_time = time.time()
    logger.debug('%s do callback end cost seconds %s' % (json_command, (end_time - start_time)))
    return is_success


def do_callback(url, _type, command):
    '''
    回调
    '''
    is_success = False
    start_time = time.time()
    json_command = json.dumps(command)

    headers = {'content-type': 'application/json;charset=UTF-8'}

    for x in range(2):

        try:
            rc = requests.post(url, data=json_command, timeout=(5, 5), headers=headers)
            rc.raise_for_status()
            response_body = rc.text
            res = json.loads(response_body)
            logger.debug('%s callback json command %s res is %s' % (_type, json_command, res))
            if _type == 'portal':
                if res['status'] in [0]:
                    is_success = True
                    break
                elif res['status'] in [2]:
                    break
            elif _type == 'rcms':
                if res['ROOT']['BODY']['RETURN_CODE'] == '0':
                    is_success = True
                    break
        except Exception:
            logger.error("%s callback error command is %s, error is %s" %
                         (_type, json_command, traceback.format_exc()))
            continue

    end_time = time.time()
    logger.debug('%s do callback end cost seconds %s' % (json_command, (end_time - start_time)))
    return is_success


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
    res_cache = CERT_TRANS_CACHE.hgetall(res_cache_key)
    if not res_cache:
        return error_list

    for k, v in list(res_cache.items()):
        v_obj = json.loads(v)
        if v_obj['result_status'] != 200:
            error_list.append({'host': v_obj['host'], 'code': v_obj[
                              'result_status'], 'name': v_obj['name'], 'type': v_obj['type']})
    return error_list


def send_error_email(task_info, error_list):
    '''
    发送失败设备邮件
    '''
    task_id = task_info['_id']
    cert_id = task_info['c_id']
    username = task_info['username']
    created_time = task_info['created_time']
    all_error = []

    dev_info = s1_db.cert_trans_dev.find_one({'_id': ObjectId(task_info['dev_id'])})

    content = '用户ID: %s , 证书ID: %s 于 %s 下发证书任务，失败设备如下: \n' % (username, cert_id, created_time)
    table = '<table border="1">\n<tr><th>name</th><th>host</th><th>type</th><th>code</th><th>a_code</th><th>r_code</th><th>c_code</th>'

    # 下发
    for h_k, h_d in list(dev_info['devices'].items()):
        if h_d['code'] == 200:
            continue
        table += '<tr><td>%s</td><td style="text-align:center">%s</td><td style="text-align:center">%s</td><td style="text-align:center">%s</td><td style="text-align:center">%s</td><td style="text-align:center">%s</td><td style="text-align:center">%s</td></tr>' % (h_k, h_d[
                                                                                                                                                                                                                                                                         'host'], h_d['type'], h_d['code'], h_d['a_code'], h_d['r_code'], 0)
        all_error.append(h_d)

    # 回调　暂时排除 0
    for error_dev in error_list:
        e_code = int(error_dev.get('code', 0))
        if e_code in [0, 524]:
            continue
        table += '<tr><td>%s</td><td style="text-align:center">%s</td><td style="text-align:center">%s</td><td style="text-align:center">%s</td><td style="text-align:center">%s</td><td style="text-align:center">%s</td><td style="text-align:center">%s</td></tr>' % (error_dev[
                                                                                                                                                                                                                                                                         'name'], error_dev['host'], error_dev['type'], 200, 200, 200, error_dev['code'])
        all_error.append(error_dev)

    table += '</table>\n'

    content_end = '请依照 wiki http://wiki.dev.chinacache.com/pages/viewpage.action?pageId=43014430 步骤操作　处理异常设备'

    all_content = content + table + content_end

    to_addrs = config.get('cert_trans', 'email_group')

    attch = store_error_host(cert_id, all_error)
    if attch:
        attchs = [attch]
    else:
        attchs = []

    # noc 版本
    sendEmail.send(eval(to_addrs), '自助证书下发邮件告警', all_content.encode('utf-8'), 'html', attchs)

    try:
       # 个人版
        p_attch = store_error_host(cert_id, error_list)
        if p_attch:
            p_attchs = [p_attch]
        else:
            p_attchs = []
        sendEmail.send(['pengfei.hao@chinacache.com'], '自助证书下发邮件详情',
                       all_content.encode('utf-8'), 'html', p_attchs)
        #sendEmail.send(['junyu.guo@chinacache.com'], '自助证书下发邮件详情', all_content.encode('utf-8'), 'html', p_attchs)
    except:
        pass


def make_op_log(username, remote_ip, cert_ids, _type):
    '''
    生成操作日志
    '''
    s1_db.cert_op_log.insert({"username": username, "remote_ip": remote_ip,
                              "cert_ids": cert_ids, "type": _type, "created_time": datetime.datetime.now()})


def store_error_host(cert_id, error_list):

    try:
        if not os.path.exists(ERROR_HOSTS_DIR):
            os.makedirs(ERROR_HOSTS_DIR)
        with open('%shpcc_%s.txt' % (ERROR_HOSTS_DIR, cert_id), 'w') as file_w:
            for e in error_list:
                file_w.write(e['host'] + '\n')
        return ERROR_HOSTS_DIR + 'hpcc_%s.txt' % (cert_id)

    except Exception:
        logger.debug('store_all_urls error:%s' % traceback.format_exc())
        return None
