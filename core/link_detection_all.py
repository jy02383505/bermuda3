#! -*- coding=utf-8 -*-
"""
@version: ??
@author: rubin
@license:
@contact: longjun.zhao@chinacache.com
@site:
@software: PyCharm
@file: link_detection_all.py
@time: 16-9-7 下午1:37
"""
from celery.task import task
from . import redisfactory
import http.client
import simplejson as json
from util import log_utils
from core.etcd_client import get_subcenters
import datetime
from core.postal import getDirCommand
from core.cert_trans_postal import get_command as get_cert_task_commond
from core import database
from core.update import db_update
from bson.objectid import ObjectId
import asyncio
from .asyncpostal import AioClient, doTheLoop
import socket, sys, time
from io import StringIO
import uuid
from xml.dom.minidom import parseString
from .config import config
from util.tools import JSONEncoder
import traceback

from core.subcenter_base import Subcenter_cert, Subcenter_Refresh_Dir, Subcenter_Refresh_Url, Subcenter_preload
from redis.exceptions import WatchError

# link detection in redis
# dev_detect = redisfactory.getDB(7)
# logger = log_utils.get_celery_Logger()
logger = log_utils.get_cert_query_postal_Logger()
# expire_time = 3600
db = database.db_session()
db_preload = database.s1_db_session()
db_cert = database.s1_db_session()
db_s1 = database.s1_db_session()
# store failed FC device information
import core.redisfactory as redisfactory

FAILED_DEV_FC = redisfactory.getDB(5)
expire_time = 60 * 60 * 24 * 5
SUBCENTER_REFRSH_UID = redisfactory.getDB(3)
subcenter_expire_time = 60 * 15


### old version for refresh
# @task(ignore_result=True, default_retry_delay=10, max_retries=3)
# def link_detection_refresh(urls, failed_dev_list, flag):
#     rid = insert_retry_db(urls, failed_dev_list, flag)
#     for url in urls:
#         logger.debug("insert into url start ...")
#         now_test = time.time()
#         try:
#             branch_id = db.retry_device_branch.insert({'create_time': datetime.datetime.now(), 'rid': rid, 'devices': failed_dev_list, "uid": ObjectId(url.get("id"))})
#             logger.debug("insert retry_device_branch id:%s" % branch_id)
#             list_host = get_failed_dev(failed_dev_list)
#             # username = urls.get
#             if list_host:
#                 try:
#                     failed_dev_pipe = FAILED_DEV_FC.pipeline()
#                     key = "URLID_" + str(url.get('id'))+'_FC'
#                     for host_t in list_host:
#                         failed_dev_pipe.sadd(key, host_t)
#                     failed_dev_pipe.expire(key, expire_time)
#                     failed_dev_pipe.execute()
#                 except Exception, e:
#                     logger.debug('link_detection_refresh redis5 error:%s' % traceback.format_exc())
#         except Exception, e:
#             logger.debug("refresh insert retry_device_branch error:%s" % e)
#         db_update(db.url, {"_id": ObjectId(url.get("id"))},
#                 {"$set": {'retry_branch_id': branch_id}})
#         # logger.debug("link_detection urls:%s, failed_dev_list:%s" % (urls, failed_dev_list))
#         logger.debug("insert into usr end, url:%s, use time %s" % (url.get("id"), time.time() - now_test))
#     # branch_center_list = ['218.24.18.85:31109']
#     branch_center_list = []
#     branch_centers = get_subcenters()
#     if branch_centers:
#         branch_center_list = branch_centers.values()
#     # # rubin_test  delete
#     # branch_center_list = ['223.202.52.83:21109']
#     if branch_center_list:
#         send_subcenter(rid, failed_dev_list, branch_center_list, '/probetask', 21108)



### original subcent_preload
# @task(ignore_result=True, default_retry_delay=10, max_retries=3)
# def link_detection_preload(urls, failed_dev_list_refresh, flag_refresh, failed_dev_list_preload, flag_preload):
#     """
#     now that the URL is only a single record
#     :param urls:
#     :param failed_dev_list_refresh:
#     :param flag_refresh:
#     :param failed_dev_list_preload:
#     :param flag_preload:
#     :return:
#     """
#     rid = ObjectId()
#     # for url in urls:
#     # logger.debug("link_detection_preload urls:%s, failed_dev_list_refresh:%s, flag_refresh:%s, "
#     #              "failed_dev_list_preload:%s, flag_preload:%s" % (urls, failed_dev_list_refresh, flag_refresh,
#     #                                                               failed_dev_list_preload, flag_preload))
#     if urls:
#         url = urls[0]
#     else:
#         return
#     try:
#         branch_id = db.retry_device_branch.insert({'create_time': datetime.datetime.now(), 'rid': rid,
#                                                    'devices': failed_dev_list_refresh + failed_dev_list_preload,
#                                                    'uid': ObjectId(url.get('_id'))})
#         logger.debug('insert retry_device_branch id:%s' % branch_id)
#     except Exception, e:
#         logger.debug('preload insert retry_device_branch error:%s' % e)
#         return
#     # update preload_url, add retry_branch_id
#     db_update(db_preload.preload_url, {"_id": ObjectId(url.get("_id"))}, {"$set": {'retry_branch_id': branch_id}})
#     insert_retry_db_data = []
#     if failed_dev_list_refresh:
#         if flag_refresh == 'url_ret':
#             temp_xml = generate_data([url], '', flag_refresh)
#             insert_retry_db_data.append(temp_xml)
#     if failed_dev_list_preload:
#         for dev in failed_dev_list_preload:
#             if flag_preload == 'pre_ret':
#                 temp_xml = generate_data([url], dev.get('host'), flag_preload, rid=rid, action=url.get('action'))
#                 insert_retry_db_data.append(temp_xml)
#     try:
#         obj_id_list = db.retry_branch_xml.insert_many(insert_retry_db_data).inserted_ids
#         logger.debug('insert obj_id_list_ids:%s, %s' % (obj_id_list, type(obj_id_list)))

#     except Exception, e:
#         logger.debug('insert retry_branch_xml error:%s' % e)
#         return
#     # get branch center list
#     branch_center_list = []
#     branch_centers = get_subcenters()
#     if branch_centers:
#         branch_center_list = branch_centers.values()
#     # # rubin_test
#     # branch_center_list = ['123.94.24.2:21109']
#     if len(obj_id_list) > len(failed_dev_list_preload):

#         if branch_center_list:
#             logger.debug('obj_id_list[0]:%s' % obj_id_list[0])
#             send_subcenter(obj_id_list[0], failed_dev_list_refresh, branch_center_list, '/probetask', 21108)
#         if failed_dev_list_preload:
#             for i in range(0, len(failed_dev_list_preload)):
#                 logger.debug('obj_id_list[i+1]:%s' % obj_id_list[i + 1])
#                 send_subcenter(obj_id_list[i + 1], [failed_dev_list_preload[i]], branch_center_list,
#                                '/probetask', 31108)
#     elif len(obj_id_list) == len(failed_dev_list_preload):
#         if failed_dev_list_preload:
#             for i in range(0, len(failed_dev_list_preload)):
#                 logger.debug('obj_id_list[i]:%s' % obj_id_list[i])
#                 send_subcenter(obj_id_list[i], [failed_dev_list_preload[i]], branch_center_list,
#                                '/probetask', 31108)


def generate_data(urls, host, flag, rid=None, action=None):
    """
    generate xml or json
    :param urls: now urls  length   one
    :param host: the ip of host
    :param flag: url_ret, ret, preload_ret
    :param rid:
    :param action:
    :return:
    """

    temp_xml = {}
    logger.debug('generate_data urls:%s, host:%s, flag:%s, rid:%s, action:%s' % (urls, host, flag, rid, action))
    if flag == 'url_ret':
        xml_command = getUrlCommand_new(urls)
    elif flag == 'ret':
        ssid, xml_command = getDirCommand(urls)
    elif flag == 'pre_ret':
        xml_command = getPreloadCommand(urls, action, host)
        logger.debug('generate_data xml_command getPreloadCommand:%s' % xml_command)
    elif flag == 'cert_task':
        xml_command = get_cert_task_commond(urls)
        logger.debug('generate_data xml_command cert_task:%s' % xml_command)

    if rid:
        logger.debug('generate_data rid:%s' % rid)
        temp_xml['preload_rid'] = rid
    logger.debug('generate_data rid:%s' % rid)
    temp_xml['flag'] = flag
    temp_xml['create_time'] = datetime.datetime.now()
    # logger.debug('generate_data temp_xml:%s' % xml_command)
    temp_xml['xml'] = xml_command
    logger.debug('generate_data temp_xml:%s' % temp_xml)
    return temp_xml


def insert_retry_db(urls, failed_dev_list, flag):
    rid = None
    # xml_body = {}
    # if flag == "url_ret":
    #     xml_command = getUrlCommand_new(urls)
    # elif flag == 'ret':
    #     ssid, xml_command = getDirCommand(urls)
    # else:
    #     # here is modified to json
    #     xml_command = getPreloadCommand(urls)
    # xml_body['xml'] = xml_command
    # xml_body['create_time'] = datetime.datetime.now()
    # xml_body['flag'] = flag
    #
    xml_body = generate_data(urls, '', flag)
    try:
        rid = db.retry_branch_xml.insert(xml_body)
        logger.debug("insert retry_branch_xml rid:%s" % rid)
    except Exception:
        logger.debug("refresh insert retry_branch_xml error:%s" % e)

    return rid


def send_subcenter(rid, failed_dev_list, branch_center_list, path, edge_port):
    """
    from the queue to take out the list of url and failure of the device list, do device link detection
    :param urls: url information
    :param failed_dev_list: the list of failed device
    :param branch_center_list: registration center, equipment list
    :param path: route
    :param edge_port:
    :return:
    """
    # branch center list,ip list
    # logger.debug("link_detection  link_detection rid:%s, failed_dev_list:%s" % (rid, failed_dev_list))

    #
    # branch_center_list = ['58.67.207.6:21109']
    # branch_center_list = ['182.118.78.102:21109']
    # branch_center_list1 = get_subcenters().values()
    # logger.debug("link_detection link_detection branch_center_list:%s" % branch_center_list1)
    # branch_center_list = []
    # branch_centers = get_subcenters()
    # if branch_centers:
    #     branch_center_list = branch_centers.values()
    logger.debug("link_detection  link_detection branch_center_list:%s" % branch_center_list)
    dev_list = [(dev.get('host') + ':' + str(edge_port)) for dev in failed_dev_list]
    post_data = {'key': str(rid), 'host': dev_list}
    clients = []
    my_map = {}
    connect_timeout = 1.5
    response_timeout = 1.5
    fail_post_list = []
    # path = "/probetask"
    for dev in branch_center_list:
        try:
            dev_temp = dev.split(":")
            host = dev_temp[0]
            # the port of subcenter
            port = int(dev_temp[1])
            clients.append(
                AioClient(host, port, path, json.JSONEncoder().encode(post_data), connect_timeout, response_timeout, path))
        except Exception:
            logger.error(traceback.format_exc())

    results = doTheLoop(clients, logger)
    
    for r in results[0]:
        if r.get('response_code') != 200:
            fail_post_list.append(r)

    logger.debug("fail post subcenter %s" % (fail_post_list))


def getUrlCommand_new(urls):
    """
    in the form of the interface, format URLS, URL can be repeated,distinguished from postal/getUrlCommand
    :param urls:
    :return:
    """
    sid = uuid.uuid1().hex
    content = parseString('<method name="url_expire" sessionid="%s"><recursion>0</recursion></method>' % sid)
    if urls[0].get('action') == 'purge':
        content = parseString('<method name="url_purge" sessionid="%s"><recursion>0</recursion></method>' % sid)
    url_list = parseString('<url_list></url_list>')
    tmp = {}
    logger.debug('urls information')
    logger.debug(urls)
    for idx, url in enumerate(urls):
        # if url.get("url") in tmp:
        #     continue
        qurl = url.get("url").lower() if url.get('ignore_case', False) else url.get("url")
        uelement = content.createElement('url')
        # uelement.setAttribute('id', str(idx))
        uelement.setAttribute('id', url.get("id", str(idx)))  # store url.id  in id
        logger.debug("发送的url.id ")
        logger.debug(url.get("id"))
        uelement.appendChild(content.createTextNode(qurl))
        url_list.documentElement.appendChild(uelement)
        # tmp[url.get("url")] = ''
    content.documentElement.appendChild(url_list.documentElement)
    return content.toxml('utf-8')


def getPreloadCommand(urls, action, dev_ip):
    """
    assemble json, preload
    :param urls:
    :param action:
    :param dev_ip:
    :return:
    {'sessionid':xxx, 'action':xxx, 'priority':xxxx, 'nest_track_level':xxx, 'check_type':xxxx, 'check_value': xxx,
     'limit_rate': xxx, 'limit_rate': xxx, 'preload_address': xxx, 'lvs_address':xxx, 'report_address': xxx,
      'is_override': xxx, 'url_list': xxx, 'compressed_url_list':xxxx, 'url_list':[{'id': xxxx, 'url': xxxx}],
      'compressed_url_list': [{'id':xxx, 'url':xxxx}]}
    """
    result = {}
    try:
        sid = uuid.uuid1().hex
        result['sessionid'] = sid
        result['action'] = action
        result['priority'] = urls[0].get('priority')
        result['nest_track_level'] = urls[0].get('nest_track_level')
        result['check_type'] = urls[0].get('check_type')
        # this place need to be discussed
        result['check_value'] = urls[0].get('md5', '')
        result['limit_rate'] = urls[0].get('get_url_speed')
        result['preload_address'] = urls[0].get('preload_address')
        result['lvs_address'] = dev_ip
        result['report_address'] = config.get('server', 'preload_report')
        # result['report_address'] = config.get('server', 'preload_report')
        result['is_override'] = 1
        result['url_list'] = []
        result['compressed_url_list'] = []
        for url in urls:
            if not url.get('compressed'):
                temp = {}
                temp['id'] = str(url.get('_id'))
                temp['url'] = url.get('url')
                result['url_list'].append(temp)
            else:
                temp = {}
                temp['id'] = str(url.get('_id'))
                temp['url'] = url.get('url')
                result['compressed_url_list'].append(temp)
    except Exception:
        logger.debug('assemble json error, id:%s, error:%s' % (urls[0].get('_id'), e))
    logger.debug('result:%s' % result)
    try:
        return json.dumps(result)
    except Exception:
        logger.debug("json.dumps error:%s" % e)
        return json.dumps({})


def get_failed_pre(dev_id, preload_results):
    """

    :param dev_id:  preload_dev   _id
    :param preload_results: the result of preload result
    :return:
    """
    preload_failed_list = []
    try:
        db_dev = db_preload.preload_dev.find_one({"_id": ObjectId(dev_id)})
        devices = db_dev.get("devices")
        logger.debug('preload_result test:%s' % preload_results)
        logger.debug('device test:%s' % devices)
        if preload_results:
            for ret in preload_results:
                devices.get(ret.get("name"))["code"] = ret.get("code", 0)
                devices.get(ret.get("name"))["a_code"] = ret.get("a_code", 0)
                devices.get(ret.get("name"))["r_code"] = ret.get("r_code", 0)
                if ret.get('code', 0) not in [200, 204, 406]:
                    preload_failed_list.append(devices.get(ret.get('name')))
    except Exception:
        logger.debug('get_failed_pre error:%s' % e)
    return preload_failed_list


def get_failed_cert_devs(dev_id, results, dev_type):
    '''
    获取失败设备信息
    '''
    failed_list = []
    try:
        # db_dev = db_cert.cert_trans_dev.find_one({"_id": ObjectId(dev_id)})
        db_dev = db_cert[dev_type].find_one({"_id": ObjectId(dev_id)})
        if dev_type == 'cert_query_dev':
            devices = db_dev.get("query_dev_ip")
        else:
            devices = db_dev.get("devices")
        for ret in results:
            devices.get(ret.get("name"))["code"] = ret.get("code", 0)
            devices.get(ret.get("name"))["a_code"] = ret.get("a_code", 0)
            devices.get(ret.get("name"))["r_code"] = ret.get("r_code", 0)
            devices.get(ret.get("name"))["status"] = "OPEN"
            devices.get(ret.get("name"))["firstLayer"] = "unknown"
            if ret.get('code', 0) not in [200, 204]:
                failed_list.append(devices.get(ret.get('name')))
            logger.debug("failed_list is %s" % failed_list)
    except Exception:
        logger.debug('get_failed_cert_devs error:%s' % e)

    return failed_list


# @task(ignore_result=True, default_retry_delay=10, max_retries=3)
# def link_detection_cert(tasks,failed_dev_list):
#
#     rid = insert_retry_db(tasks, failed_dev_list, 'cert_task')
#     logger.debug("link_detection_cert task ids %s, failed_dev_list %s"%([i['_id'] for i in tasks], failed_dev_list))
#     for task in tasks:
#         logger.debug("insert cert branch start ...")
#         now_test = time.time()
#         try:
#             branch_id = db.retry_device_branch.insert({'create_time': datetime.datetime.now(), 'rid': rid, 'devices': failed_dev_list, "task_id": ObjectId(task.get("task_id"))})
#             logger.debug("insert cert retry_device_branch id:%s" % branch_id)
#         except Exception, e:
#             logger.debug("cert insert retry_device_branch error:%s" % e)
#         db_update(db_cert.cert_trans_tasks, {"_id": ObjectId(task.get("_id"))},
#                 {"$set": {'retry_branch_id': branch_id}})
#         logger.debug("insert cert branch end, task:%s, use time %s" % (task.get("_id"), time.time() - now_test))
#
#     branch_center_list = []
#     branch_centers = get_subcenters()
#     if branch_centers:
#         branch_center_list = branch_centers.values()
#     if branch_center_list:
#         send_subcenter(rid, failed_dev_list, branch_center_list, '/probetask', 51108)


def get_failed_dev(failed_dev_list, type_t="FC"):
    """
    get all failed host, type_t default FC
    Args:
        failed_dev_list: [
        {
            "status" : "OPEN",
            "code" : NumberInt(503),
            "host" : "183.222.231.108",
            "firstLayer" : false,
            "port" : NumberInt(21108),
            "name" : "CMN-CD-3-345",
            "total_cost" : "2.06",
            "connect_cost" : "2.06",
            "serialNumber" : "0700283345",
            "a_code" : NumberInt(503),
            "r_code" : NumberInt(503),
            "response_cost" : "0.00",
            "type" : "FC"
        }
    ]
        type_t: FC HPCC  unknown

    Returns:["183.222.231.108"]

    """
    result_list = []
    try:
        if failed_dev_list:
            for dev_info in failed_dev_list:
                type_temp = dev_info.get('type')
                if type_temp == type_t:
                    host = dev_info.get('host')
                    result_list.append(host)
        return result_list
    except Exception:
        logger.debug('get_failed_dev error %s, failed_dev_list:%s, type_t:%s' % (traceback.format_exc(),
                                                                                 failed_dev_list, type_t))
        return result_list


@task(ignore_result=True, default_retry_delay=10, max_retries=3)
def link_detection_cert(tasks, failed_dev_list, Interface=None):
    branch_center_list = []
    branch_centers = get_subcenters()
    if branch_centers:
        branch_center_list = list(branch_centers.values())
    logger.debug('link_detection_cert branch_center_list:%s, urls:%s' % (branch_center_list, tasks))
    dict_sub = {}
    dict_sub['failed_dev_list'] = failed_dev_list
    dict_sub['branch_center_list'] = branch_center_list
    # dict_sub['sub_path'] = '/'
    dict_sub['subcenter_port'] = 21109
    dict_sub['edge_port'] = 51108
    dict_sub['edge_path'] = Interface
    dict_sub['relation_sub_failed_dev'] = {}
    dict_sub['db'] = db_cert
    dict_sub['subcenter_task_mq'] = "cert_subcenter_task"
    dict_sub['subcenter_result_mq'] = "cert_subcenter_result"
    if Interface == "checkcertisexits":
        dict_sub['task_mq'] = "cert_query_tasks"
    elif Interface == "transfer_cert":
        dict_sub['task_mq'] = "transfer_cert_tasks"
    else:
        dict_sub['task_mq'] = "cert_trans_tasks"
    dict_sub['is_compressed'] = True
    dict_sub['tasks'] = tasks
    dict_sub['return_path'] = 'http://r.chinacache.com/cert/receiveSubCenterResult'
    # dict_sub['relation_sub_failed_dev'] = get_best_road(failed_dev_list, branch_center_list)
    logger.debug("can delete  dict_sub['relation_sub_failed_dev']:%s" % dict_sub['relation_sub_failed_dev'])
    sub_center_cert_instance = Subcenter_cert(dict_sub)
    # sub_center_cert_instance.sub_dispatch()
    sub_center_cert_instance.insert_mongo()


@task(ignore_result=True, default_retry_delay=10, max_retries=3)
def link_detection_preload(urls, failed_dev_list):
    try:
        logger.debug("link_detection_preload urls: %s|| failed_dev_list: %s" % (urls, failed_dev_list))
        for url in urls:
            pre_id = str(url.get('_id', 0))
            SUBCENTER_REFRSH_UID.set('sub_preload_' + pre_id, [i.get('host') for i in failed_dev_list])
            SUBCENTER_REFRSH_UID.expire('sub_preload_' + pre_id, subcenter_expire_time)
        branch_centers = get_subcenters()
        branch_center_list = list(branch_centers.values()) if branch_centers else []
        logger.debug('link_detection_preload branch_center_list: %s|| urls: %s' % (branch_center_list, urls))
        dict_sub = {}
        dict_sub['failed_dev_list'] = failed_dev_list
        dict_sub['branch_center_list'] = branch_center_list
        # dict_sub['sub_path'] = '/'
        # dict_sub['subcenter_port'] = 21109 # online
        dict_sub['subcenter_port'] = 31109 # for test
        dict_sub['edge_port'] = 31108
        dict_sub['relation_sub_failed_dev'] = {}
        dict_sub['db'] = db_s1
        dict_sub['subcenter_task_mq'] = "subcenter_preload_task"
        dict_sub['subcenter_result_mq'] = "subcenter_preload_result"
        dict_sub['task_mq'] = "preload_url"
        dict_sub['is_compressed'] = False
        dict_sub['tasks'] = urls
        # dict_sub['heads'] = {"Content-type": "text/xml"}
        dict_sub['return_path'] = 'http://223.202.203.31/subcenter/preload'
        # dict_sub['return_path'] = 'http://r.chinacache.com/subcenter/preload'
        # dict_sub['relation_sub_failed_dev'] = get_best_road(failed_dev_list, branch_center_list)

        sub_center_url = Subcenter_preload(dict_sub)

        sub_center_url.orgin_ids = sub_center_url.generate_orgin_ids()
        sub_center_url.sub_task_id = sub_center_url.init_mongo()
        sub_center_url.command = sub_center_url.generate_command()
        sub_center_url.body = sub_center_url.generate_body()

        sub_center_url.insert_mongo()
    except Exception:
        logger.debug("link_detection_preload[error]: %s" % (traceback.format_exc()))


@task(ignore_result=True, default_retry_delay=10, max_retries=3)
def link_detection_refresh(urls, failed_dev_list, flag):
    # SUBCENTER_REFRSH_UID = redisfactory.getDB(3)
    # subcenter_expire_time = 60 * 15
    logger.info('-------------------------------link_detection_refresh------------------------------')
    for url in urls:
        ref_id = url.get('id', 0)
        dev_list = []
        for dev in failed_dev_list:
            dev_list.append(dev.get('host'))
        SUBCENTER_REFRSH_UID.set('sub_' + ref_id, dev_list)
        SUBCENTER_REFRSH_UID.expire('sub_' + ref_id, subcenter_expire_time)
    branch_center_list = []
    branch_centers = get_subcenters()
    if branch_centers:
        branch_center_list = list(branch_centers.values())
    logger.debug('link_detection_refresh branch_center_list:%s, urls:%s' % (branch_center_list, urls))
    dict_sub = {}
    dict_sub['failed_dev_list'] = failed_dev_list
    dict_sub['branch_center_list'] = branch_center_list
    # dict_sub['sub_path'] = '/'
    dict_sub['subcenter_port'] = 21109
    dict_sub['edge_port'] = 21108
    dict_sub['relation_sub_failed_dev'] = {}
    dict_sub['db'] = db_s1
    dict_sub['subcenter_task_mq'] = "subcenter_refresh_task"
    dict_sub['subcenter_result_mq'] = "subcenter_refresh_result"
    dict_sub['task_mq'] = "url"
    dict_sub['is_compressed'] = False
    dict_sub['tasks'] = urls
    dict_sub['heads'] = {"Content-type": "text/xml"}

    dict_sub['return_path'] = 'http://r.chinacache.com/subcenter/refresh'
    # dict_sub['relation_sub_failed_dev'] = get_best_road(failed_dev_list, branch_center_list)
    logger.debug("can delete  dict_sub['failed_dev_list']:%s" % dict_sub['failed_dev_list'])
    if flag == "url_ret":
        sub_center_url = Subcenter_Refresh_Url(dict_sub)
        sub_center_url.insert_mongo()
    else:
        sub_center_url = Subcenter_Refresh_Dir(dict_sub)
        sub_center_url.insert_mongo()


def get_refresh_result(xml_body):
    try:
        logger.debug('------------xml_body------------%s' % (xml_body))
        content = parseString(xml_body)
    except Exception:
        logger.debug(traceback.format_exc())
        # result = {'code': '503', 'status': 'failed'}
        result = {'code': '503', 'status': 'failed', 'xml_body': xml_body}
        return result

    result = {}
    request_id = 0
    url_list = []
    list_514 = []
    list_200 = []
    code = 513
    # print content
    xml_list = ['url_expire_response', 'url_purge_response', 'dir_expire_response', 'dir_purge_response']
    url_type_list = ['url_ret', 'ret']
    for node_first in xml_list:
        if content.getElementsByTagName(node_first):
            request_id = content.getElementsByTagName(node_first)[0].getAttribute('sessionid')
            if content.getElementsByTagName(node_first)[0]:
                for url_type in url_type_list:
                    if content.getElementsByTagName(node_first)[0].getElementsByTagName(url_type):
                        for node in content.getElementsByTagName(node_first)[0].getElementsByTagName(url_type):
                            logger.debug(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
                            logger.debug(type(node.childNodes[0].data))
                            logger.debug("<<<<<<<<<<<<<<<<<<<<<<<<<<<<<")
                            # if node.childNodes[0].data != '200':
                            if node.childNodes[0].data not in ['400', '200', '414']:
                                code = 514
                                list_code = [node.getAttribute('id') if node.getAttribute('id') else request_id]
                                list_514 = list_514 + list_code
                            else:
                                list_code = [node.getAttribute('id') if node.getAttribute('id') else request_id]
                                list_200 = list_200 + list_code
                            if node.getAttribute('id'):
                                url_list.append({node.getAttribute('id'): node.childNodes[0].data})
                            else:
                                url_list.append({request_id: node.childNodes[0].data})
    if url_list and code == 513:
        code = 200
    else:
        code = 514
    result['code'] = code
    result['code_200'] = list_200
    result['code_514'] = list_514
    result['request_id'] = request_id
    result['results'] = url_list
    result['status'] = 'success'
    return result


def set_edge_device(SUBCENTER_REFRSH_REDIS, uid, edge_host):
    '''
    dev_list = SUBCENTER_REFRSH_UID.get('sub_'+uid)
                dev_list = eval(dev_list)
                #logger.debug(type(dev_list))
                #logger.debug(dev_list)

                if not  dev_list:
                    continue
                else:
                    dev_set = set(dev_list)
                    #dev_set.remove(edge_host)
                    dev_set = dev_set - set([edge_host])
                    logger.debug("---------------%s------------%s"%('sub_'+uid,list(dev_set)))
                    #logger.debug(dev_set)
                    SUBCENTER_REFRSH_UID.set('sub_'+uid,list(dev_set))
    '''
    key = 'sub_' + uid
    with SUBCENTER_REFRSH_REDIS.pipeline() as pipe:
        while True:
            try:
                # 对序列号的键进行 WATCH
                pipe.watch(key)
                # WATCH 执行后，pipeline 被设置成立即执行模式直到我们通知它
                # 重新开始缓冲命令。
                # 这就允许我们获取序列号的值
                value = pipe.get(key)
                # 现在我们可以用 MULTI 命令把 pipeline 设置成缓冲模式
                pipe.multi()  # 标记事务开始

                dev_list = str(value)
                logger.debug('dev_list_type--------%s----' % (type(dev_list)))
                logger.debug('-------------%s---------' % (dev_list))
                dev_list = eval(dev_list)
                # logger.debug(type(dev_list))
                # logger.debug(dev_list)

                if dev_list:
                    logger.debug('---------------edge_host---------%s' % (edge_host))
                    if edge_host in dev_list:
                        dev_list.remove(edge_host)
                        pipe.set('sub_' + uid, dev_list)
                        pipe.expire(key, 600)
                        logger.debug('---------------dev_list---------%s' % (dev_list))
                        if len(dev_list) < 1:
                            url_dict = db.url.find_one({"_id": ObjectId(uid)}, {'url': 1, 'status': 1})
                            logger.debug('subcent refresh success id is %s db_url dict is %s' % (uid, str(url_dict)))
                            result_mq = db.url.update({"_id": ObjectId(uid)},
                                                      {"$set": {"status": "FINISHED", 'sub_status': "FINISHED"}})
                            logger.debug('success update %s result is %s ' % (uid, result_mq))

                pipe.execute()
                break
            except WatchError as e:
                logger.debug(e.message)
                continue