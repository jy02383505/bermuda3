# -*- coding:utf-8 -*-

import logging, traceback
from datetime import datetime

# from bson import ObjectId
from core.generate_id import ObjectId
from redis import WatchError
import simplejson as json
from celery.task import task

from core import rcmsapi, database, command_factory, redisfactory
from core import preload_postal as postal
from core import postal as r_postal
from core.models import STATUS_UNPROCESSED, STATUS_RETRY_SUCCESS, STATUS_CONNECT_FAILED, PRELOAD_STATUS_REPEATED, \
    PRELOAD_STATUS_SUCCESS, PRELOAD_STATUS_FAILED, PRELOAD_STATUS_RETRYED, PRELOAD_STATUS_MD5_DIFF
from core.sendEmail import send as send_mail
from core.verify import doPost
from core.update import db_update
from util import log_utils
from cache import rediscache
import time
import copy
from core.link_detection_all import link_detection_preload, get_failed_pre


PRELOAD_CACHE = redisfactory.getDB(1)
PRELOAD_DEVS = redisfactory.getDB(5)
db = database.db_session()
s1_db = database.s1_db_session()
logger = log_utils.get_pcelery_Logger()


@task(ignore_result=True, default_retry_delay=10, max_retries=3)
def dispatch(urls):
    """
    preload worker 入口函数

    :param urls:
    """
    try:
        logger.debug("dispatch preload begin %s" % len(urls))
        dev_id, pre_devs, ref_devs = init_pre_devs(urls[0].get('channel_code'))
        logger.debug("ref_devs:%s" % ref_devs)
        logger.debug('pre_devs:%s' % pre_devs)
        #  test down
        # 以下部分为测试部分  增加一个新的设备  CNC-JS-c-3WR 外网地址 182.118.78.102   内网地址：172.16.21.102

        # ref_devs.append({'status': 'OPEN', 'code': 0, 'name': 'CNC-DL-5-3S3', 'type':'HPCC','serviceIp': None,\
        #        'serialNumber': '060120b3g7', 'host': '218.60.108.79', 'deviceId': None, 'firstLayer': False,\
        #             'port': 31108})
        #

        # ref_devs.append({'status': 'OPEN', 'code': 1, 'name': 'CNC-TI-3-3WK', 'type':'HPCC','serviceIp': None,\
        #        'serialNumber': '060120b3g8', 'host': '218.24.18.85', 'deviceId': None, 'firstLayer': False,\
        #             'port': 21108})
        # logger.debug("pre_devs:XXXXXXXXXXXXXXXXXXX:%s" % pre_devs)
        # logger.debug(dev_map)
        #  test  upper
        region_devs = get_channel_region(urls[0].get('channel_code'), pre_devs)
        PRELOAD_DEVS.set(urls[0].get('channel_code'), json.dumps(region_devs))
        first_layer_devs = [
                               dev for dev in pre_devs if dev.get("firstLayer") or dev in region_devs] + ref_devs
        # new modification  get len of firstLayer of preload dev
        first_layer_preload = [dev for dev in pre_devs if dev.get("firstLayer")]
        not_first_layer_preload_len = len(pre_devs) - len(first_layer_preload)
        first_layer_preload_len = len(first_layer_preload)
        logger.debug("dispatch first_layer_preload_len:%s, not_first_layer_preload_len:%s" %
                     (first_layer_preload_len, not_first_layer_preload_len))
        if first_layer_preload_len:
            conn_num, speed = get_bandwidth(first_layer_preload_len, urls[0].get('limit_speed'))
            logger.debug('first_layer_preload_len send conn_num:%s, speed:%s' % (conn_num, speed))
        if not first_layer_preload_len and not_first_layer_preload_len:
            conn_num, speed = get_bandwidth(not_first_layer_preload_len, urls[0].get('limit_speed'))
            logger.debug("not_first_layer_preload_len send conn_num:%s, speed:%s" % (conn_num, speed))
        # end new modification
        if urls[0].get('status') == 'TIMER':
            # logger.debug('test_rubin dispatch urs:%s' % urls)
            for url in urls:
                url["dev_id"] = dev_id
                # logger.debug('test_rubin dispatch url before _id:%s' % url.get('_id'))
                url["_id"] = ObjectId(url.get('_id'))
                # logger.debug('test_rubin dispatch url after _id:%s' % url['_id'])
                url['status'] = 'PROGRESS'
                # new modification by longju.zhao 2016/12/12 14:28
                if speed:
                    url['conn_num'] = conn_num
                    url['single_limit_speed'] = speed

                if first_layer_preload_len:
                    logger.debug("url dev have first layer url_id:%s" % url.get("_id"))
                    url['have_first_layer'] = 1
                else:
                    logger.debug("url dev not have first layer url_id:%s" % url.get("_id"))
                    url['have_first_layer'] = 0

                PRELOAD_CACHE.set(url.get('_id'), json.dumps(
                    {"devices": create_proload_result_dict(pre_devs), "task_id": url.get("task_id"),
                     "channel_code": url.get("channel_code"), "unprocess": len(
                        pre_devs), 'status': 'PROGRESS', 'check_type': url.get('check_type'),
                     'check_result': url.get('md5')}))
                try:
                    # logger.debug('test_rubin dispatch url:%s' % url)
                    s1_db.preload_url.update_one({'_id': url["_id"]}, {'$set': url})
                except Exception:
                    logger.debug("preload_worker update_one  error:%s, _id:%s" % (traceback.format_exc(), url['_id']))
            logger.debug("dispatch urls:%s" % urls)
        else:
            for url in urls:
                url["dev_id"] = dev_id
                url["_id"] = ObjectId()
                # new modification by longju.zhao 2016/12/12 14:28
                if speed:
                    url['conn_num'] = conn_num
                    url['single_limit_speed'] = speed

                if first_layer_preload_len:
                    logger.debug("url dev have first layer url_id:%s" % url.get("_id"))
                    url['have_first_layer'] = 1
                else:
                    logger.debug("url dev not have first layer url_id:%s" % url.get("_id"))
                    url['have_first_layer'] = 0
                PRELOAD_CACHE.set(url.get('_id'), json.dumps(
                    {"devices": create_proload_result_dict(pre_devs), "task_id": url.get("task_id"),
                     "channel_code": url.get("channel_code"), "unprocess": len(
                        pre_devs), 'status': 'PROGRESS', 'check_type': url.get('check_type'),
                     'check_result': url.get('md5')}))
            logger.debug("dispatch urls:%s" % urls)
            s1_db.preload_url.insert(urls)



        layer_worker(urls, pre_devs, ref_devs, first_layer_preload_len=first_layer_preload_len) if first_layer_devs else worker(
            urls, pre_devs, first_layer_preload_len=first_layer_preload_len)
        logger.debug("dispatch preload end")
    except Exception:
        logger.debug("dispatch error:%s " % e)
        logger.debug(traceback.format_exc())


def merge_dispatch_task(body, url_dict, url_other, package_size=20):
    try:
        task = json.loads(body)
        if task.get('status') == 'PROGRESS':
            url_dict.setdefault(
                task.get("channel_code"), []).append(task)
        else:
            url_other.append(task)
        if len(url_dict.get(task.get("channel_code"), {})) > package_size:
            dispatch(url_dict.pop(task.get("channel_code")))
    except Exception:
        logger.debug("merge_dispatch_task error:%s " % e)


def extract_name(p_name):
    name = p_name.strip()
    name_list = name.split('-')
    use_name = '-'.join([name_list[0].strip(), name_list[1].strip()])
    return use_name


def get_channel_region(channel_code, pre_devs):
    regions = db.preload_channel.find_one({"channel_code": channel_code}, {"region": 1, "_id": 0})
    if not regions:
        return []

    reg_list = regions['region']
    super_devs = db.device_basic_info.find({"province": {"$in": reg_list}}, {"name": 1, "_id": 0})
    dev_list = [dev["name"] for dev in super_devs]
    regions_list = []
    regions_list = [p_dev for p_dev in pre_devs if extract_name(p_dev['name']) in dev_list]
    return regions_list


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


@task(ignore_result=True, default_retry_delay=10, max_retries=3)
def save_fc_report(report_body):
    """
    worker 处理 预加载返回结果
    :param report_body:
    """
    logger.debug("save_fc_report host:%s url_id:%s" % (report_body.get("remote_addr"), report_body.get("url_id")))
    # has_lock, cache_body = lock(report_body.get("url_id"))
    RL = RedisLock()
    has_lock, cache_body = RL.lock(report_body.get("url_id"))
    # logger.debug("get lock %s"%has_lock)
    # logger.debug(report_body)
    # has_lock, cache_body = report_body.get("url_id")
    if has_lock:
        save_fc_report.delay(report_body)
        logger.debug("url_id:%s  locking reput queue.%s" % (report_body.get("url_id"),report_body.get("remote_addr")))
    elif cache_body:
        try:
            if report_body.get('preload_status') == PRELOAD_STATUS_REPEATED:
                logger.debug("PRELOAD_STATUS_REPEATED: %s" % report_body.get("url_id"))
                db_update(s1_db.preload_url, {'_id': ObjectId(report_body.get("url_id"))}, {"$set": {'status': 'EXPIRED'}})
                s1_db.preload_error_task.remove({"url_id": str(report_body.get("url_id"))})
                PRELOAD_CACHE.delete(report_body.get('url_id'))
                RL.unlock(report_body.get("url_id"))
            # elif report_body.get('preload_status') == PRELOAD_STATUS_SUCCESS and (
            #                 cache_body.get('check_result') == report_body.get('check_result') or cache_body.get(
            #             'check_type') == 'BASIC'):
            elif report_body.get('preload_status') == PRELOAD_STATUS_SUCCESS and (
                            cache_body.get('check_type') == 'MD5' or cache_body.get('check_type') == 'BASIC'):
                logger.debug("PRELOAD_STATUS_SUCCESS: %s,%s" % (report_body.get("url_id"),report_body.get("remote_addr")))
                reset_cache(cache_body, report_body)
                save_result(report_body.get("url_id"), cache_body, report_body.get("remote_addr"))
                RL.unlock(report_body.get("url_id"))
            else:
                handle_error_task(report_body, cache_body)
                RL.unlock(report_body.get("url_id"))
        except Exception:
            logger.debug("save_fc_report error: %s" % (traceback.format_exc()))
            RL.unlock(report_body.get("url_id"))
    else:
        logger.debug(
            "url_id:%s cache_body is null,host:%s" % (report_body.get("url_id"), report_body.get("remote_addr")))
        RL.unlock(report_body.get("url_id"))


class RedisLock(object):
    def __init__(self):
        self.timeout = 0
        self.expire = 60  # s
        self.waitInterval = 10  # s
        self.now = time.time()
        # self.pipe = PRELOAD_CACHE.pipeline()

    def lock(self, name):
        timeoutAt = self.now + self.timeout
        expireAt = self.now + self.expire
        redisKey = "Lock:%s" % name
        # logger.debug(redisKey)
        cache_body = {}
        while 1:
            # 将rediskey的最大生存时刻存到redis里，过了这个时刻该锁会被自动释放
            result = PRELOAD_CACHE.setnx(redisKey, expireAt)
            if result:
                PRELOAD_CACHE.expire(redisKey, self.expire)
                pip_cache_body = PRELOAD_CACHE.get(name)
                cache_body = json.loads(pip_cache_body)
                if not cache_body:
                    logger.debug("%s cache is null" % name)
                    self.unlock(name)
                return False, cache_body

            # 以秒为单位，返回给定key的剩余生存时间
            ttl_time = PRELOAD_CACHE.ttl(redisKey)
            # ttl小于0 表示key上没有设置生存时间（key是不会不存在的，因为前面setnx会自动创建）
            # 如果出现这种状况，那就是进程的某个实例setnx成功后 crash 导致紧跟着的expire没有被调用
            # 这时可以直接设置expire并把锁纳为己用
            # logger.debug("ttl %s"%ttl_time)
            if ttl_time < 0:
                logger.debug("in ttl")
                PRELOAD_CACHE.set(redisKey, expireAt)
                PRELOAD_CACHE.expire(redisKey, self.expire)
                pip_cache_body = PRELOAD_CACHE.get(name)
                cache_body = json.loads(pip_cache_body)
                if not cache_body:
                    logger.debug("%s cache is null" % name)
                    self.unlock(name)
                return False, cache_body
            # 如果没设置锁失败的等待时间 或者 已超过最大等待时间了，那就退出
            if self.timeout <= 0 or timeoutAt < time.time():
                break
                # logger.debug("sleep %s"%self.waitInterval)
                # time.sleep(self.waitInterval)

        return True, cache_body

    def unlock(self, name):
        redisKey = "Lock:%s" % name
        try:
            PRELOAD_CACHE.delete(redisKey)
            return True
        except:
            pass
        return False


def lock(uid):
    cache_body = {}
    has_lock = False
    try:
        pipe = PRELOAD_CACHE.pipeline()
        # 对序列号的键进行 WATCH
        while 1:
            try:
                key = "lock_%s" % (uid)
                timestamp = int(time.time())
                pipe.setnx(key, timestamp)
                pipe.watch(key)  # 监控字段变化，如果在未处理之前有变化，直接报错
                # WATCH 执行后，pipeline 被设置成立即执行模式直到我们通知它
                # 重新开始缓冲命令。
                # 这就允许我们获取序列号的值
                pip_cache_body = pipe.get(key)
                if not pip_cache_body:
                    return has_lock, cache_body
                cache_body = json.loads(pip_cache_body)
                if cache_body.get("lock"):
                    has_lock = True
                else:
                    cache_body["lock"] = True
                    pipe.multi()  # 对数据进行缓存
                    # pipe.set(key, json.dumps(cache_body))
                    # pipe.set set(key,val,nx,ex,180)
                    # lock_map={ip:timestamp}
                    # pipe.hmset(key,lock_map)
                    pipe.execute()
                    cache_body["lock"] = False  # 虽然对字段进行了赋值，但是没有入库，所以lock 仍为true
                break
            except WatchError:
                logger.debug("watch error:%s" % key)
                continue
            finally:
                pipe.reset()
    except Exception:
        logger.debug("%s,has_lock error:%s." % (key, e))
        has_lock = True
    return has_lock, cache_body


# --my function !--##
def reset_cache(cache_body, report_body, is_failed=False):
    """
    重置cache内容
    :param cache_body:
    :param report_body:
    :param is_failed:
    """
    for dev in list(cache_body.get('devices', {}).values()):
        if dev.get("host") == report_body.get("remote_addr"):
            if is_failed:
                dev["preload_status"] = STATUS_CONNECT_FAILED
            else:
                # explanation , if basic, return report status 200,
                # if check_type is MD5     cache_body md5 == report_body md5 return report 200, not eq return 406
                dev["preload_status"] = report_body.get("preload_status") if cache_body.get(
                    'check_type') == 'BASIC' or cache_body.get('check_result') == report_body.get(
                    'check_result') else PRELOAD_STATUS_MD5_DIFF
                set_value(report_body, dev, ["content_length", "check_result", "check_type", "last_modified",
                                             "response_time", "cache_status", "http_status_code", "download_mean_rate",
                                             "finish_time"])


def save_result(url_id, cache_body, report_host):
    """
    存任务执行结果，只有没有未处理的设备才会结束
    :param url_id:
    :param cache_body:
    """
    logger.debug("save_result begin url_id: %s" % url_id)
    if get_unprocess(cache_body, url_id, report_host):
        logger.debug("not finished reset cache url_id: %s" % url_id)
        PRELOAD_CACHE.set(url_id, json.dumps(cache_body))
    else:
        PRELOAD_CACHE.set(url_id, json.dumps(cache_body))
        set_finished(url_id, cache_body, 'FINISHED' if cache_body.get(
            'status') == 'PROGRESS' else cache_body.get('status'))
    logger.debug("save_result end url_id: %s" % url_id)


def calRegionDevicePer(reg_count, succ_count):
    if reg_count > 0 and round(float(succ_count) / float(reg_count), 2) >= 0.8:
        return True
    else:
        return False


def get_unprocess(cache_body, url_id, report_host):
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
    channel_code = s1_db.preload_url.find_one({"_id": ObjectId(url_id)}, {"channel_code": 1, "_id": 0})["channel_code"]
    region_devs = PRELOAD_DEVS.get(channel_code)
    reg_name_list = []
    reg_host_list = []
    try:
        [(reg_name_list.append(dd['name']), reg_host_list.append(dd['host'])) for dd in json.loads(region_devs)]
    except Exception:
        logger.error(traceback.format_exc())
        logger.error("error code: %s" % channel_code)
    succ_reg_dev = []
    for dev in list(cache_body.get("devices").values()):
        if dev.get("firstLayer") in ["true", "True", True]:
            firstlayer_count += 1
            if dev.get("preload_status") in [PRELOAD_STATUS_FAILED, STATUS_UNPROCESSED, STATUS_CONNECT_FAILED]:
                # cache_body['unprocess'] = len([dev for dev in cache_body.get("devices").values() if dev.get("preload_status") in [PRELOAD_STATUS_FAILED,STATUS_UNPROCESSED]])
                unprocess_firstlayer_count += 1
        else:
            un_firstlayer_count += 1
            if dev.get("preload_status") in [PRELOAD_STATUS_FAILED, STATUS_UNPROCESSED, STATUS_CONNECT_FAILED]:
                unprocess_un_firstlayer_count += 1
        if dev.get("name") in reg_name_list and dev.get("preload_status") in [PRELOAD_STATUS_SUCCESS,
                                                                              PRELOAD_STATUS_RETRYED]:
            succ_reg_dev.append(dev.get("name"))
    # if not list(set(reg_name_list).difference(set(succ_reg_dev))) and report_host in reg_host_list:
    try:
        if calRegionDevicePer(len(reg_name_list), len(succ_reg_dev)) and report_host in reg_host_list:
            logger.debug("finish region devs: {0}".format(region_devs))
            task_info = get_information(cache_body)
            reg_list = []
            regions = db.preload_channel.find_one({"channel_code": channel_code}, {"region": 1, "_id": 0})
            reg_list = regions['region']
            preload_callback(db.preload_channel.find_one({"channel_code": cache_body.get("channel_code")}), {
                "task_id": cache_body.get('task_id'), "status": "SUCCESS", "percent": "100", "region": reg_list},
                             task_info)

        if not unprocess_firstlayer_count and (
                        un_firstlayer_count == 0 or round(
                        float(unprocess_un_firstlayer_count) / float(un_firstlayer_count), 2) <= 0.2):
            cache_body['unprocess'] = 0
        else:
            cache_body['unprocess'] = unprocess_firstlayer_count + unprocess_un_firstlayer_count
        logger.debug(
            'unprocess: %s %s %s' % (cache_body['unprocess'], un_firstlayer_count, unprocess_un_firstlayer_count))
        return cache_body.get('unprocess')
    except Exception:
        logger.error(traceback.format_exc())
        return 0


def handle_error_task(report_body, cache_body):
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
            reset_cache(cache_body, report_body, True)
            if get_unprocess(cache_body, report_body.get("url_id"), report_body.get("remote_addr")):
                cache_body['status'] = 'FAILED'
                PRELOAD_CACHE.set(report_body.get('url_id'), json.dumps(cache_body))
                logger.debug("handle_error_task reset cache status FAILED url_id: %s" % report_body.get("url_id"))
            else:
                PRELOAD_CACHE.set(report_body.get('url_id'), json.dumps(cache_body))
                logger.debug(
                    "handle_error_task reset cache status FAILED  finished url_id: %s" % report_body.get("url_id"))
                set_finished(report_body.get('url_id'), cache_body, 'FAILED')
        else:
            PRELOAD_CACHE.set(report_body.get('url_id'), json.dumps(cache_body))
            # db_update(db.preload_error_task,
            #           {'url_id': report_body.get('url_id'), 'host': report_body.get('remote_addr')},
            #           {'$inc': {'retry_times': 1}, '$set': {
            #               'command': command_factory.re_handle_command(error_task.get('command')),
            #               'last_retrytime': datetime.now(), 'grapped': False}})
            db_update(s1_db.preload_error_task,
                      {'url_id': report_body.get('url_id'), 'host': report_body.get('remote_addr')},
                      {'$inc': {'retry_times': 1}, '$set': {
                          'command': command_factory.re_handle_command(error_task.get('command')),
                          'last_retrytime': datetime.now(), 'grapped': False}})
            logger.debug("handle_error_task unprocess lt 3")

    else:
        do_frist_retry(report_body.get('url_id'), report_body.get('remote_addr'), cache_body)


def do_frist_retry(url_id, host, cache_body):
    """
    第一次重试,并插入preload_error_task
    :param url_id:
    :param host:
    :param cache_body:
    """
    logger.debug("do_frist_retry begin url_id: %s host %s " % (url_id, host))
    for dev in list(cache_body.get("devices").values()):
        dev['preload_status'] = PRELOAD_STATUS_FAILED if dev.get("host") == host else dev.get('preload_status')
    PRELOAD_CACHE.set(url_id, json.dumps(cache_body))
    db_url = s1_db.preload_url.find_one({'_id': ObjectId(url_id)})
    if db_url.get('single_limit_speed'):
        # 判断是否预加载，
        # 判断这条url 对应的设备是否有上层预加载设备，　　是否是上层
        if db_url.get('have_first_layer'):
            if judge_first_layer(str(db_url.get("dev_id")), host):
                db.preload_error_task.insert({'url_id': url_id, 'retry_times': 0, 'command': command_factory.get_command(
                  [db_url], db_url.get('action'), host, conn_num=db_url.get('conn_num', 0),
                speed=db_url.get('single_limit_speed', 0), test=5), 'host': host, 'type': 'preload_failed',
                                      'last_retrytime': datetime.now(), 'grapped': False})
            else:
                s1_db.preload_error_task.insert({'url_id': url_id, 'retry_times': 0, 'command': command_factory.get_command(
                  [db_url], db_url.get('action'), host, test=5), 'host': host, 'type': 'preload_failed',
                                      'last_retrytime': datetime.now(), 'grapped': False})
        else:
            s1_db.preload_error_task.insert({'url_id': url_id, 'retry_times': 0, 'command': command_factory.get_command(
                  [db_url], db_url.get('action'), host, conn_num=db_url.get('conn_num', 0),
                speed=db_url.get('single_limit_speed', 0), test=5), 'host': host, 'type': 'preload_failed',
                                      'last_retrytime': datetime.now(), 'grapped': False})
    else:
        s1_db.preload_error_task.insert({'url_id': url_id, 'retry_times': 0, 'command': command_factory.get_command(
                  [db_url], db_url.get('action'), host, conn_num=0, speed=0, test=5), 'host': host, 'type': 'preload_failed',
                                      'last_retrytime': datetime.now(), 'grapped': False})

    logger.debug("do_frist_retry end url_id: %s host %s " % (url_id, host))


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




def set_finished(url_id, cache_body, status):
    """
     处理URL结果存入DB preload_url
    :param url_id:
    :param cache_body:
    :param status:
    """
    logger.debug("set_finished begin url_id: %s status: %s " % (url_id, status))
    db_update(s1_db.preload_url, {'_id': ObjectId(url_id)}, {
        "$set": {'status': status, 'finish_time': datetime.now()}})
    cache_body['_id'] = ObjectId(url_id)
    cache_body['status'] = status
    try:
        s1_db.preload_result.save(cache_body)
    except:
        #3.0.3 pymongo update
        update_body = copy.deepcopy(cache_body)
        if '_id' in update_body:
            update_body.pop('_id')
        s1_db.preload_result.update_one({"_id": ObjectId(url_id)}, {"$set": update_body}, upsert=True)
    task_info = get_information(cache_body)
    preload_callback(db.preload_channel.find_one({"channel_code": cache_body.get("channel_code")}), {
        "task_id": cache_body.get('task_id'), "status": cache_body.get('status'), "percent": task_info.get('percent')},
                     task_info, id=cache_body.get("_id"))
    PRELOAD_CACHE.delete(cache_body.get('_id'))
    logger.debug("set_finished end url_id: %s status: %s " % (url_id, status))


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


def init_pre_devs(channel_code):
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
        rcms_devs = []
        rcms_dev_names = []
        rcms_first_devs = []
        for dev in rcmsapi.getFirstLayerDevices(channel_code):
            if dev.get("status") == "OPEN":
                rcms_first_devs.append(dev)
                rcms_dev_names.append(dev.get('name'))
        for dev in rcmsapi.getDevices(channel_code):
            if dev.get("status") == "OPEN":
                rcms_devs.append(dev)
                rcms_dev_names.append(dev.get('name'))
        pre_devs = [set_type(dev, 'preload')
                    for dev in db.preload_config_device.find({"channel_code": channel_code},
                                                             {"status": 1, "firstLayer": 1, "host": 1, "name": 1,
                                                              "_id": 0}) if dev.get('name') in rcms_dev_names]
        if not pre_devs:
            pre_devs = rcms_devs
            logger.debug("init_pre_devs error:%s must config device" % channel_code)
        ref_devs = [set_type(rcms_dev, 'refresh') for rcms_dev in rcms_first_devs
                    if rcms_dev.get("name") not in [pre_dev.get("name") for pre_dev in pre_devs]]

        # ref_devs.append({'status': 'OPEN', 'code': 0, 'name': 'CNC-TI-3-3WK', 'type':'HPCC','serviceIp': None,\
        #        'serialNumber': '060120b3g8', 'host': '218.24.18.85', 'deviceId': None, 'firstLayer': False,\
        #             'port': 21108})
        # pre_devs.append({'status': 'OPEN', 'code': 0, 'name': 'CNC-TI-3-3WK', 'type':'HPCC','serviceIp': None,\
        #        'serialNumber': '060120b3g8', 'host': '218.24.18.85', 'deviceId': None, 'firstLayer': False,\
        #             'port': 31108})
        # pre_devs.append({'status': 'OPEN', 'code': 1, 'name': 'BNC-BJ-2-3W6', 'type':'HPCC','serviceIp': None,\
        #        'serialNumber': '060120b3g8', 'host': '59.109.99.167', 'deviceId': None, 'firstLayer': False,\
        #             'port': 31108})
        # pre_devs.append({'status': 'OPEN', 'code': 0, 'name': 'BGP-SM-3-3gG', 'type':'HPCC','serviceIp': None,\
        #        'serialNumber': '060120b3g7', 'host': '223.202.201.167', 'deviceId': None, 'firstLayer': True,\
        #             'port': 31108})

        dev_id = s1_db.preload_dev.insert(
            {"devices": create_send_dev_dict(pre_devs + ref_devs), "created_time": datetime.now(),
             "channel_code": channel_code, "unprocess": len(pre_devs + ref_devs)})
        return dev_id, pre_devs, ref_devs
    except Exception:
        logger.debug("init_pre_devs error:%s " % traceback.format_exc())


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


def create_send_dev_dict(devs, old_dev_dict={}):
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
            dev_dict[dev.get('name')] = dev
        return dev_dict
    except Exception:
        logger.debug("create_dev_dict error:%s " % e)


def layer_worker(urls, pre_devs, ref_devs, first_layer_preload_len=0):
    """
    处理第一层设备
    :param urls:
    :param pre_devs:
    :param ref_devs:
    """
    try:
        refresh_results = r_postal.do_send_url(urls, ref_devs)
        r_postal.do_send_url(urls, [dev for dev in pre_devs if dev.get("firstLayer")])
        logger.debug('urls:%s, type:%s' % (urls, type(urls)))
        logger.debug('pre_devs:%s, type:%s' % (pre_devs, type(pre_devs)))
        r_postal.do_send_url(urls, [dev for dev in pre_devs if not dev.get("firstLayer")])
        # command = command_factory.get_command(urls, urls[0].get("action"))

        preload_results = send(pre_devs, urls, first_layer_preload_len=first_layer_preload_len)
        save_fail_task(preload_results, urls[0].get("dev_id"), urls, first_layer_preload_len=first_layer_preload_len, test=4)
        update_db_dev(urls[0].get("dev_id"), refresh_results + preload_results)
    except Exception:
        logger.debug("layer_worker error:%s " % e)


def worker(urls, pre_devs, first_layer_preload_len=0):
    """
    处理除第一层设备
    :param urls:
    :param pre_devs:
    """
    try:
        # command = command_factory.get_command(urls, urls[0].get("action"))
        r_postal.do_send_url(urls, pre_devs)

        # conn_num, speed = get_bandwidth(pre_devs, urls[0].get('limit_speed'))
        # logger.debug('send conn_num:%s, speed:%s' % (conn_num, speed))
        results = send(pre_devs, urls, first_layer_preload_len=first_layer_preload_len, test=1)
        save_fail_task(results, urls[0].get("dev_id"), urls, first_layer_preload_len=first_layer_preload_len, test=2)
        update_db_dev(urls[0].get("dev_id"), results)
    except Exception:
        logger.debug("layer_worker error:%s " % e)


def update_db_dev(dev_id, results):
    """
     更新任务状态,preload_dev
    :param dev_id:
    :param results:
    """
    try:
        db_dev = s1_db.preload_dev.find_one({"_id": ObjectId(dev_id)})
        db_dev["finish_time"] = datetime.now()
        db_dev["finish_time_timestamp"] = time.mktime(datetime.now().timetuple())
        devices = db_dev.get("devices")
        # logger.debug("test_rubin update_db_dev , devices:%s" % (devices))
        # logger.debug("test_rubin update_db_dev , results:%s" % (results))
        for ret in results:
            # logger.debug("test_rubin update_db_dev ret:%s" % ret)
            devices.get(ret.get("name"))["code"] = ret.get("code", 0)
            devices.get(ret.get("name"))["a_code"] = ret.get("a_code", 0)
            devices.get(ret.get("name"))["r_code"] = ret.get("r_code", 0)
            db_dev["unprocess"] = int(db_dev.get("unprocess")) - 1
        try:
            # logger.debug(db_dev)
            s1_db.preload_dev.save(db_dev)
        except:
            #3.0.3 pymongo update
            update_dev = copy.deepcopy(db_dev)
            if '_id' in update_dev:
                update_dev.pop('_id')
            s1_db.preload_dev.update_one({"_id": ObjectId(dev_id)}, {'$set': update_dev})
    except Exception:
        logger.debug("update_db_dev error:%s " % traceback.format_exc())


def send(devs, urls, first_layer_preload_len=0, test=0):
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

        pre_ret, pre_ret_faild = postal.doloop(devs, urls, first_layer_preload_len=first_layer_preload_len, test=test)
        logger.debug("send pre_ret:%s, pre_ret_faild:%s" % (pre_ret, pre_ret_faild))
        results, error_result = postal.process_loop_ret(pre_ret, dev_map, "pre_ret", first_layer_preload_len=first_layer_preload_len)
        # process the result of failed
        pre_results_faild_dic = postal.process_loop_ret_faild(pre_ret_faild, dev_map, first_layer_preload_len=first_layer_preload_len)
        if dev_map:
            # the failure in the successful information    join the failure of the info list
            # results += postal.retry(dev_map.values(), urls, "pre_ret", pre_results_faild_dic)
            try:
                pre_results_faild_dic.update(error_result)
                retry_results = postal.retry(list(dev_map.values()), urls, "pre_ret", pre_results_faild_dic,
                                             first_layer_preload_len=first_layer_preload_len, test=test)
            except Exception:
                logger.error(traceback.format_exc())
            results += retry_results

        return results
    except Exception:
        logger.debug("send error:%s " % traceback.format_exc())


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
            # 平均到每台机器限制速度太小，每台机器开一个链接，速度是１
            logger.debug("get_bandwidth　　conn_num:1, single_conn_speed:1")
            return 1, 1
    else:
        # 不限速
        logger.debug('get_bandwidth not speed limit:%s' % speed_temp)
        return 0, 0

    # if speed_temp:
    #     try:
    #         speed_current = (speed_temp / dev_len) / 8
    #     except Exception, e:
    #         logger.debug("division error:%s" % traceback.format_exc())
    # logger.debug('get_bandwidth speed_current:%s' % speed_current)
    # return speed_current


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
            return 1, 1
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
            return two_point_search(middle_conn + 1, max_conn, min_speed, max_speed, speed, flag=0)
        else:
            return two_point_search(middle_conn, max_conn, min_speed, max_speed, speed, flag=0)


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


def save_fail_task(results, dev_id, urls, first_layer_preload_len=0, test=0):
    """
    处理失败的任务,目前只针对503进行判断，如果是503即为失败,存入preload_error_task
    :param results:
    :param dev_id:
    :param command:
    """
    try:
        for result in results:
            if result.get('code') == STATUS_CONNECT_FAILED:
                logger.debug("save_faile_task first_layer_preload_len:%s, firstLayer:%s" %
                                     (first_layer_preload_len, result.get('firstLayer')))
                if first_layer_preload_len:
                    if result.get('firstLayer'):
                        logger.debug("save_faile_task first_layer_preload_len:%s, firstLayer:%s" %
                                     (first_layer_preload_len, result.get('firstLayer')))
                        s1_db.preload_error_task.insert(
                        {'dev_id': dev_id, 'command': command_factory.get_command(urls, urls[0].get("action"),
                        result.get('host'), conn_num=urls[0].get('conn_num'), speed=urls[0].get('single_limit_speed'), test=test),
                        'host': result.get('host'), 'type': 'send_failed', 'last_retrytime': datetime.now()})
                    else:
                        s1_db.preload_error_task.insert(
                        {'dev_id': dev_id, 'command': command_factory.get_command(urls, urls[0].get("action"),
                        result.get('host'), test=test),
                        'host': result.get('host'), 'type': 'send_failed', 'last_retrytime': datetime.now()})
                else:
                    s1_db.preload_error_task.insert(
                        {'dev_id': dev_id, 'command': command_factory.get_command(urls, urls[0].get("action"),
                        result.get('host'), conn_num=urls[0].get('conn_num'), speed=urls[0].get('single_limit_speed'), test=test),
                        'host': result.get('host'), 'type': 'send_failed', 'last_retrytime': datetime.now()})



    except Exception:
        logger.debug("save_fail_task error:%s " % traceback.format_exc())


def get_error_tasks(host):
    """
    获取指定IP，发送失败的任务（12小时内的100条），
    及preload任务没有被领取的任务（"grapped": False，12小时之内，到10分钟之前，少于总数100）
    重试3次，间隔10分钟
    :param host:
    :return:
    """
    import datetime as f_datetime
    send_task = [task for task in s1_db.preload_error_task.find({"type": 'send_failed', "host": host, "last_retrytime": {
        "$gte": datetime.now() - f_datetime.timedelta(hours=12)}}).limit(2)]
    if len(send_task) < 100:
        preload_task = [task for task in s1_db.preload_error_task.find(
            {"host": host, "grapped": False, "last_retrytime": {"$gte": datetime.now() - f_datetime.timedelta(hours=12),
                                                                "$lte": datetime.now() - f_datetime.timedelta(
                                                                    seconds=int(600))}}).limit(100 - len(send_task))]
    return send_task, preload_task


@task(ignore_result=True, default_retry_delay=10, max_retries=3)
def reset_error_tasks(send_task, preload_task, host):
    for db_dev in s1_db.preload_dev.find({"_id": {"$in": [task.get("dev_id") for task in send_task]}}):
        db_dev["finish_time"] = datetime.now()
        for device in list(db_dev.get("devices").values()):
            if device.get('host') == host:
                db_dev.get("devices").get(device.get('name'))[
                    "code"] = STATUS_RETRY_SUCCESS
                try:
                    s1_db.preload_dev.save(db_dev)
                except:
                    #3.0.3 pymongo update
                    update_dev = copy.deepcopy(db_dev)
                    update_id = update_dev.pop('_id')
                    s1_db.preload_dev.update_one({"_id": update_id}, {"$set": update_dev})
    for url in preload_task:
        db_update(s1_db.preload_error_task, {'url_id': url.get('url_id'), 'host': url.get('host')}, {
            '$set': {'last_retrytime': datetime.now(), 'grapped': True}})
    logger.debug("remove sendtask :%s" % send_task)
    s1_db.preload_error_task.remove(
        {"dev_id": {'$in': [task.get("dev_id") for task in send_task]}, "host": host})


def set_value(source_dict, new_dict, keys):
    for key in keys:
        if source_dict.get(key):
            new_dict[key] = source_dict.get(key)


def get_information(cache_body):
    """
    查询preload_result表的数据,计算完成比例
    :param cache_body: <type 'dict'>
    {'status': 'FINISHED', 'check_result': '', 'check_type': 'BASIC',
    'task_id': 'c32f4eaa-c56a-485e-99ba-0dfffa43bb37', 'lock': False,
    'devices': {'CHN-ZI-2-3g9': {'content_length': '-', 'check_result': '-',
    'name': 'CHN-ZI-2-3g9', 'download_mean_rate': '-', 'host': '222.186.47.10',
     'firstLayer': False, 'preload_status': 0, 'check_type': '-'},'unprocess': 99,
     '_id': ObjectId('53b4b5da3770e1604118b954'), 'channel_code': '56893'}
    :return:
    """
    count = 0
    file_size = 0
    total_count = 0
    firstLayer_count = 0
    firstLayer_success = 0
    for dev in list(cache_body.get('devices', {}).values()):
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
    if (firstLayer_count - firstLayer_success) == 0 and (True if ((total_count - firstLayer_count) == 0) else (
                round((float(count - firstLayer_success) / (float(total_count - firstLayer_count))), 2) >= 0.8)):
        percent = 100
    else:
        percent = round(
            float(count) / float(len(cache_body.get('devices', {})) if len(cache_body.get('devices', {})) else 1),
            2) * 100
    if total_count==0:
        percent=0 
    # print {"percent": percent, "file_size": float(file_size), "total_count": total_count, "count": count}
    return {"percent": percent, "file_size": float(file_size), "total_count": total_count, "count": count}


def get_lvs_value(root):
    try:
        return get_nodevalue(get_xmlnode(root, 'lvs_address')[0])
    except:
        return ''


def get_attrvalue(node, attrname):
    return node.getAttribute(attrname) if node else ''


def get_nodevalue(node, index=0):
    return node.childNodes[index].nodeValue if node else ''


def get_xmlnode(node, name):
    return node.getElementsByTagName(name) if node else []


def get_firstChild(node, name, index=0):
    first_node = get_xmlnode(node, name)
    return first_node[index].firstChild.data if first_node[index].firstChild else ''


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
                logger.debug("preload_callback email error: %s url_id: %s " % (traceback.format_exc(), callback_body.get("url_id")))
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
        logger.debug("preload_callback error: %s url_id: %s " % (e, callback_body.get("url_id")))
