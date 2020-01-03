#!-*- coding=utf-8 -*-
"""
@author: rubin
@create time: 2016/6/28 14:29
central information processing
"""

import time
from util import log_utils
import simplejson as json
from core.database import query_db_session, db_session, s1_db_session
from bson.objectid import ObjectId
import uuid
from xml.dom.minidom import parseString
import socket
import fcntl
import struct
import core.redisfactory as redisfactory
# import receiver
from util.tools import JSONEncoder, load_task, delete_urlid_host, get_mongo_str
from core.config import config
from celery.task import task
# STATUS_RESOLVE_FAILED = 500
from core.models import STATUS_RETRY_SUCCESS, STATUS_RESOLVE_FAILED
import datetime
import traceback



db = db_session()
q_db = query_db_session()
db_s1 = s1_db_session()
# link detection in redis
dev_detect = redisfactory.getDB(7)
logger = log_utils.get_receiver_Logger()
expire_time = 3600


def assemble_command_info(rid, host):
    """
    according url _id and host info, assembly infomation
    :param id_host:str of id,host
    :param id: url collection, _id
    :param host: device id
    :return:
    """
    # RL = RedisLock()
    # has_lock, value = RL.lock(id_host)
    # if has_lock:
    #     assemble_command_info(id_host, id, host)
    # if number is 0 ,all the branch center can pull data,
    number = config.get('retry_branch', 'grasp_max')
    if not dev_detect.exists(rid):
        value = dev_detect.hincrby(rid, host)
        dev_detect.expire(rid, expire_time)
    else:
        value = dev_detect.hincrby(rid, host)  # .exists(rid)

    # logger.debug('redis not have key id_host:%s' % id_host)
    #     return json.dumps({'content': 'redis not have key id_host:%s' % id_host})
    # value = dev_detect.incr(id_host)
    # logger.debug("receiver_branch vlaue:%s, type value:%s, number:%s, type number:%s" % (value, type(value),
    #                                                                                      number, type(number)))
    if value <= 0 or (int(number) != 0 and value > int(number)):
        # RL.unlock(id_host)
        logger.debug("the request of sub center more than limit or more than an hour without treatment, "
                     "rid:%s, host:%s" % (rid, host))
        return json.dumps({'content': 'the request of sub center more than  limit or' \
                                      ' more than an hour without treatment'})
    else:
        logger.debug("receiver_branch value:%s" % value)
        # specific processing information
        # RL.unlock(id_host)
        try:
            result_xml = q_db.retry_branch_xml.find_one({"_id": ObjectId(rid)})
        except Exception:
            logger.debug("receiver_branch query mongo error:%s" % e)
            return json.dumps({'content': "receiver_branch query mongo error:%s" % e})
        # judge is not dir, if dir node_name = 'ret', else   node_name = 'url_ret'
        # isdir = result_url.get('isdir', False)
        # node_name = 'url_ret'
        # if str(isdir).lower() == 'true':
        #     node_name = 'ret'
        #
        # urls = []
        # urls.append(result_url)
        # content = getUrlCommand_branch(urls)
        if not result_xml:
            return json.dumps({'content': 'in mongo cannot find content'})
        else:
            refresh_type = 'refresh'
            content = result_xml.get('xml', None)
            node_name = result_xml.get('flag', None)
            preload_rid = result_xml.get('preload_rid', None)

            if preload_rid:
                rid = preload_rid
                refresh_type = 'preload'

            if node_name == 'cert_task':
                refresh_type = 'cert_task'

        logger.debug("receiver_branch content:%s,dst_addresss:%s, rid:%s, node_name: %s" %
                     (content, host, rid, node_name))
        # logger.debug("receiber_branch dst_address:%s" % host)
        # logger.debug("receiver_branch retry_branch_id:%s" % result_url.get("retry_branch_id", None))
        # add port to subcenter
        # if node_name:
        #     if node_name == 'pre_ret':
        #         port = 31108
        #     else:
        #         port = 21108
        # else:
        #     return json.dumps({'content': "can't get node_name"})
        return JSONEncoder().encode({'content': content, 'dst_address': 'http://' + str(host) , \
                                              'rid': rid, 'node_name': node_name, 'refresh_type': refresh_type})
        # return json.dump({'msg': 'ok', 'result':content, 'dst_address': host})


# def get_ip_address(ifname='eth0'):
#     """
#     by default, eth0 is the network address
#     :param ifname:
#     :return:
#     """
#     s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
#     return socket.inet_ntoa(fcntl.ioctl(
#         s.fileno(),
#         0x8915,  # SIOCGIFADDR
#         struct.pack('256s', ifname[:15])
#     )[20:24])


def getUrlCommand_branch(urls):
    """
    按接口格式，格式化url
    :param urls:
    :return:
    """
    sid = uuid.uuid1().hex
    content = parseString('<method name="url_expire" sessionid="%s"><recursion>0</recursion></method>' % sid)
    if urls[0].get('action') == 'purge':
        content = parseString('<method name="url_purge" sessionid="%s"><recursion>0</recursion></method>' % sid)
    url_list = parseString('<url_list></url_list>')
    tmp = {}
    logger.debug('urls information:%s' % urls)
    for url in urls:
        if url.get("url") in tmp:
            continue
        qurl = url.get("url").lower() if url.get('ignore_case', False) else url.get("url")
        uelement = content.createElement('url')
        # uelement.setAttribute('id', str(idx))
        uelement.setAttribute('id', str(url.get("_id", '')))  # store url.id  in id
        logger.debug("receiver_branch id:%s" % url.get("_id", ''))

        uelement.appendChild(content.createTextNode(qurl))
        url_list.documentElement.appendChild(uelement)
        tmp[url.get("url")] = ''
    content.documentElement.appendChild(url_list.documentElement)
    return content.toxml('utf-8')


def update_retry_branch(retry_branch_id, branch_code, host, sub_center_ip, rid, refresh_type):
    """
    according retry_device_branch, update device info
    :param retry_branch_id:major key
    :param branch_code: device refresh result status code
    :param host:  the ip of device
    :param sub_center_ip: the ip of sub center ip
    :param rid:if success, delete xml collection
    :param refresh_type: the type of refresh
    :return:{'msg':xxx, 'result':xxxxx}
    """
    logger.debug("receiver_branch  receve :%s,%s,%s" % (retry_branch_id, branch_code, host))
    try:
        result = q_db.retry_device_branch.find_one({"_id": ObjectId(retry_branch_id)})
    except Exception:
        logger.debug("receiver_branch  update_retry_branch query mongo error:%s" % e)
        return json.dumps({'msg': 'error', "result": "receiver_branch  update_retry_branch query mongo error:%s" % e})
    if not result:
        logger.debug("receiver_branch update_retry_branch result is null")
        return json.dumps({'msg': 'error', 'result': "receiver_branch update_retry_branch result is null"})
    else:
        device_list = []
        devices = result.get('devices', None)
        if not devices:
            return json.dumps({'msg': 'error', 'result': 'receiver_branch update_retry_branch devices is null'})
        else:
            fail_num = 0
            # the time distribute lower subcenter
            create_time = result.get('create_time', datetime.datetime.now())
            create_time_timestamp = time.mktime(create_time.timetuple())
            for dev in devices:
                dev_dic = {}
                if dev.get('host', None) == host and dev.get("branch_code", 0) != 200:
                    dev['branch_code'] = int(branch_code)
                    dev['sub_center_ip'] = sub_center_ip
                    dev['subcenter_return_time'] = datetime.datetime.now()
                    # the subcenter total time spent
                    dev['consume_time'] = time.mktime(dev['subcenter_return_time'].timetuple()) - create_time_timestamp
                    dev_dic = dev.copy()
                else:
                    dev_dic = dev.copy()
                if dev_dic.get("branch_code", 0) != 200:
                    fail_num += 1
                device_list.append(dev_dic)
            # logger.debug("receiver_branch  device_list :%s" % (device_list))
            try:
                db.retry_device_branch.update_one({"_id": ObjectId(retry_branch_id)},
                                                  {"$set": {"devices": device_list}})
            except Exception:
                logger.debug("receiver_branch update_retry_branch  update error:%s" % e)
                return json.dumps({'msg': 'error', 'result': "receiver_branch update_retry_branch "
                                                             " update error:%s" % e})
            logger.debug("receiver_branch  fail_num :%d" % (fail_num))
            if refresh_type == 'refresh':
                if fail_num == 0:
                    url_dic = None
                    try:
                        url_dic = q_db.url.find_one({'retry_branch_id': ObjectId(retry_branch_id)})
                    except Exception:
                        logger.debug("receiver_branch  update_retry_branch query error:%s" % e)
                        return json.dumps({'msg': 'error', 'content': "receiver_branch  "
                                                                      "update_retry_branch query error:%s" % e})
                    try:
                        db.url.update_one({"_id": ObjectId(url_dic.get("_id"))},
                                          {"$set": {"new_status": 'FINISHED', 'status': 'FINISHED'}})
                        db.retry_branch_xml.delete_one({'_id': ObjectId(rid)})
                    except Exception:
                        logger.debug("receiver_branch update_retry_branch true update url error :%s" % e)
                        return json.dumps({'msg': 'error', 'result': "receiver_branch " \
                                                                     "update_retry_branch true update url error:%s" % e})
    return json.dumps({'msg': 'ok', 'result': 'update success'})


def getCodeFromXml(xmlBody, node_name):
    """
    in view of the dir and url xml is different, we analyze separately

    :param xmlBody:
             dir:
                  <?xml version="1.0" encoding="UTF-8"?>
    <dir_expire_response sessionid="577e00f52b8a682325248a83">
    <ret>200</ret>
    </dir_expire_response>

    url:
       <?xml version="1.0" encoding="UTF-8"?>
       <url_purge_response sessionid="1438716009_d17b8cd63add11e5939090e2ba343720">
         <url_ret id="577e00f52b8a682325248a87">200</url_ret>
         <url_ret id="577e00f52b8a682325248a84">200</url_ret>
         <url_ret id="577e00f52b8a682325248a85">200</url_ret>
       </url_purge_response>

    pre_ret preload   json   {'sessionid': '089790c08e8911e1910800247e10b29b','pre_ret_list': [{'id': 'sfsdf', 'code': 200}]}
    :param node_name:url-url_ret   dir-ret, pre_ret
    :return: {key:value, key:value}
    """
    node_dic = {}
    if node_name == 'url_ret':
        nodes = parseString(xmlBody).getElementsByTagName(node_name)

        for node in nodes:
            node_dic[node.getAttribute('id')] = node.firstChild.data
        return node_dic
    elif node_name == 'ret':
        nodes = parseString(xmlBody)
        code = nodes.getElementsByTagName(node_name)[0].firstChild.data
        node_id = nodes.documentElement.getAttribute('sessionid')
        node_dic[node_id] = code
        return node_dic
    elif node_name == 'pre_ret':
        nodes_body = load_task(xmlBody)
        if nodes_body:
            nodes = nodes_body.get('pre_ret_list', '')
            if nodes:
                for node in nodes:
                    node_dic[node.get('id')] = node.get('code')
    elif node_name == 'cert_task':
        nodes_body = load_task(xmlBody)
        if nodes_body:
            for t in nodes_body['task_ids']:
                node_dic[t] = nodes_body['status']
        return node_dic
    else:
        return node_dic


@task(ignore_result=True, default_retry_delay=10, max_retries=3)
def update_refresh_result(result, flag=1):
    """
    according result, update refresh_result collection of mongo
    :param result: the content need to be update
    :param flag: if flag == 1  url update, else dir update
    :return: json  {'msg':xxxx, 'content': xxxx}
    """
    # try:
    #     result_mongo = q_db.refresh_result.find_one({'session_id': result['session_id'], 'name': result['name']})
    #     logger.debug("find_one refresh_result, session_id:%s, name:%s" % (result['session_id'], result['name']))
    # except Exception, e:
    #     logger.debug("receiver_branch update_refresh_result get data from mongo error:%s" % e)
    #     result_mongo = None
    # if not result_mongo:
    #     try:
    #         db.refresh_result.insert_one(result)
    #     except Exception, e:
    #         logger.debug("receiver_branch update_refresh_result insert_one error:%s" % e)
    #         # return json.dumps(
    #         #         {'msg': 'error', 'content': "receiver_branch update_refresh_result insert_one error:%s" % e})
    # else:
    #     mongo_id = result_mongo.get("_id", 0)
    #     mongo_result = result_mongo.get('result', 0)
    #     if flag == 1:
    #         mongo_gzip = result_mongo.get('result_gzip', 0)
    #     if mongo_result == 200 or result['result'] == 200:
    #         result['result'] = 200
    #     if flag == 1:
    #         if mongo_gzip == 200 or result['result_gzip'] == 200:
    #             result['result_gzip'] = 200
    #     try:
    #         db.refresh_result.update_one({"_id": ObjectId(mongo_id)}, {"$set": result})
    #     except Exception, e:
    #         logger.debug("receiver_branch update_refresh_result update_one error:%s" % e)
    logger.debug('update_refresh_result result:%s, flag:%s' % (result, flag))
    url_id = result.get('session_id')
    host = result.get('host')
    result_code = result.get('result')
    if flag == 1:

        result_gzip_code = result.get('result_gzip', '0')
        if str(result_code) == '200' and str(result_gzip_code) == '200':
            delete_urlid_host(url_id, host)
    else:
        if str(result_code) == '200':
            delete_urlid_host(url_id, host)
    str_num = ''
    try:
        num_str =config.get('refresh_result', 'num')
        str_num = get_mongo_str(str(result.get('session_id')), num_str)
    except Exception:
        logger.debug('get number of refresh_result error:%s' % traceback.format_exc())

    try:
        db_s1['refresh_result' + str_num].find_one_and_update({'session_id': result.get('session_id'), 'host': result.get('host'),
                'result': '0'},{'$set': {'result': result.get('result'), 'result_gzip': result.get('result_gzip', 0),
                                         'time_result_return': datetime.datetime.now()}})
        logger.debug('update_refresh_result success, session_id:%s, host:%s' % (result.get('session_id'),
                                                                                result.get('host')))
    except Exception:
        logger.info('update_refresh_result error:%s, session_id:%s, host:%s' % (traceback.format_exc(),
                                                        result.get('session_id'), result.get('host')))

