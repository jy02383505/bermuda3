# encoding=utf8

import sys
import traceback
import logging
from datetime import datetime, timedelta
from core import queue
import os

from xml.dom.minidom import parseString
from bson.objectid import ObjectId
from core.models import  STATUS_CONNECT_FAILED
from core.postal import getUrlCommand, getDirCommand
# from pymongo import ReplicaSetConnection, Connection
from core.database import query_db_session
from receiver.retry_task import get_rcms_devices
import copy
from core.asyncpostal import AioClient, doTheLoop
import asyncore

RETRY_COUNT = 4

LOG_FILENAME = '/Application/bermuda3/logs/fail_details.log'
logging.basicConfig(filename=LOG_FILENAME,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger('fail_url_task')
logger.setLevel(logging.DEBUG)

# db = Connection("172.16.21.205", 27017)['bermuda']
# db = ReplicaSetConnection('%s:27017,%s:27017,%s:27017' % ('172.16.12.136', '172.16.12.135', '172.16.12.134'), replicaSet ='bermuda_db')['bermuda']
db = query_db_session()


def get_ref_errs(begin_date, end_date):
    ref_err_dic = {}
    user_List = getUserList()
    # find_dic = {"datetime": {"$gte": begin_date, "$lt": end_date}}
    #find_dic = {"datetime": {"$gte": begin_date, "$lt": end_date}, "retry_success": None}
    #find_dic = {"datetime": {"$gte": begin_date, "$lt": end_date}, "username": {'$in': user_List}}
    find_dic = {"datetime": {"$gte": begin_date, "$lt": end_date}, "username": {'$in': user_List}, "retry_success":{'$exists':False}}
    return db.ref_err.find(find_dic)
    # return db.ref_err.find().limit(100)


def get_key_customers_monitor():
    config_dic = {}
    key_customers_monitor = db['key_customers_monitor']
    for config in key_customers_monitor.find():
        key = '%s_%s' % (str(config.get('USERNAME', '')), str(config.get('Channel_Code', '')))
        config_dic[key] = config
    return config_dic
def doloop(devs, command, connect_timeout=1.5, response_timeout=1.5):
# def doloop(devs, command, connect_timeout=1.5, response_timeout=10):
    """
     调用asyncore，创建信道，与FC 通过socket连接,端口21108
    :param devs:
    :param command:
    :return:
    """
    clients = []
    ret = []
    ret_faild = []
    my_map = {}
    port = 21108
    for dev in devs:
        clients.append(AioClient(dev['host'], port, '', command, connect_timeout,response_timeout))

    results = doTheLoop(clients, logger)

    for r in results:
        response_body = r.get('response_body')
        total_cost = r.get('total_cost')
        connect_cost = r.get('connect_cost')
        response_cost = r.get('response_cost')
        response_code = r.get('response_code')

        if response_body:
            try:
                ret.append(r.get('host') + '\r\n' + response_body.split('\r\n\r\n')[1] + '\r\n%d\r\n%.2f\r\n%.2f\r\n%.2f' % (
                    response_code, total_cost, connect_cost, response_cost))
                # logger.warn("devs: %s doloop response_body: %s" % (devs, response_body))
                logger.debug("have response_body host:%s, response_code:%s, response_body:%s" % (r.get('host'), response_code, response_body))
            except Exception:
                # logger.error("devs: %s doloop response_body error: %s" % (devs, response_body))
                logger.error("doloop error: %s" % traceback.format_exc())
        else:
            logger.debug("not have response_body host:%s, response_code:%s" % (r.get('host'), response_code))
            ret_faild.append(r.get('host') + '\r\n%d\r\n%.2f\r\n%.2f\r\n%.2f' % (response_code, total_cost, connect_cost, response_cost))
    return ret, ret_faild

def get_failed_dev(failed_dev):
    """
    get all failed dev
    :param failed_dev:
     "devices" : [
        {
            "code" : "503",
            "ip" : "221.204.171.27",
            "hostname" : "CNC-WB-b-3gD",
            "firstLayer" : true
        },
        {
            "code" : "503",
            "ip" : "124.14.4.240",
            "hostname" : "GWB-ZE-2-3g4",
            "firstLayer" : false
        },
        {
            "code" : "503",
            "ip" : "106.48.13.49",
            "hostname" : "USA-LA-5-3SI",
            "firstLayer" : false
        }
    ]
    :return:
    """
    str = "\r\n"
    try:
        if failed_dev:
            for dev_content in failed_dev:
                code = dev_content.get('code', '')
                host = dev_content.get('ip', '')
                hostname = dev_content.get('hostname', '')
                str += 'code: ' + code + '    设备名称:' + hostname + '    IP:' + host + '\r\n'
    except Exception:
        logger.debug('error get content:%s' % e)
    return str


def getCodeFromXml(xmlBody, node_name):
    node = parseString(xmlBody).getElementsByTagName(node_name)[0]
    return int(node.firstChild.data)


def get_url(uid):
    obj_url = db.url.find_one({"_id": ObjectId(uid)})
    if obj_url:
        return obj_url
    else:
        return None


def process_loop_ret_faild(ret, dev_map):
    """
    处理发送给FC后，失败的设备文档内容
    :param ret:
    :return:
    """
    results = {}
    for result in ret:
        host, a_code, total_cost, connect_cost, response_cost = result.split('\r\n')
        dev = dev_map.pop(host)
        try:
            results[host] = getPostStatus(dev, STATUS_CONNECT_FAILED, total_cost, connect_cost, response_cost,
                                          int(a_code))
            dev_map.setdefault(host, dev)
        except Exception:
            dev_map.setdefault(host, dev)
            logger.error(traceback.format_exc())
    return results


def process_loop_ret_uid(ret, dev_map, node_name):
    """
    处理发送给FC后，FC返回的XML结果
    :param ret:['121.63.247.151\r\n<?xml version="1.0" encoding="UTF-8"?>\n<url_purge_response sessionid="7844e960e40b11e4a74900e0ed25a740">\n<url_ret id="0">200</url_ret>\n</url_purge_response>\r\n0\r\n0\r\n0']
    :param dev_map:
    :param node_name:
    :return:
    """
    results = []
    error_result = {}
    for result in ret:
        try:
            host, xml_body, a_code, total_cost, connect_cost, response_cost = result.split('\r\n')
            dev = dev_map.pop(host)
        except Exception:
            logger.debug("process_loop_ret result has problem:%s, error:%s" % (result, e))
            host, str_temp = result.split('\r\n', 1)
            dev = dev_map.pop(host)
            results.append(getPostStatus(dev, 0, 0, 0, 0, 0, 0))
            continue
        try:
            has_error = False
            for node in parseString(xml_body).getElementsByTagName(node_name):
                if node.firstChild.data == '404' or node.firstChild.data == '408':
                    dev_map.setdefault(host, dev)
                    has_error = True
                    error_result[host] = getPostStatus(dev, int(node.firstChild.data), total_cost, connect_cost,
                                                       response_cost, int(a_code))
                    logger.error("%s response error,code: %s" % (host, node.firstChild.data))
                    break
            if not has_error:
                # results.append(getPostStatus(dev, getCodeFromXml(xml_body, node_name), total_cost, connect_cost, response_cost, int(a_code)))
                dicc = getPostStatus(dev, getCodeFromXml(xml_body, node_name), total_cost, connect_cost, response_cost,
                                     int(a_code))
                results.append(dicc)
        except Exception:
            dev_map.setdefault(host, dev)
            error_result[host] = getPostStatus(dev, STATUS_CONNECT_FAILED, total_cost, connect_cost, response_cost,
                                               int(a_code))
            logger.error("%s response error,%s: %s" % (host, len(xml_body), xml_body))
            logger.error(traceback.format_exc())
    return results, error_result


def getPostStatus(dev, statusCode, total_cost=0, connect_cost=0, response_cost=0, a_code=200, r_code=200):
    return {"host": dev.get('host'), "firstLayer": dev.get('firstLayer'),
            "name": dev.get('name'), "code": statusCode, "total_cost": total_cost, "connect_cost": connect_cost,
            "response_cost": response_cost, "a_code": a_code, "r_code": r_code, "times": 0}


def retry_fail_dev(urls_list, command, dev_map, dev_id, count,isdir):
    count = count + 1

    try:
        logger.debug("retry start")
        ret, ret_faild = doloop(list(dev_map.values()), command, connect_timeout=1.5, response_timeout=1.5)  # dict dev_list_f
        if isdir:
            results, error_result = process_loop_ret_uid(ret, dev_map, "ret")
            results_faild_dic = process_loop_ret_faild(ret_faild, dev_map)
        else:
            results, error_result = process_loop_ret_uid(ret, dev_map, "url_ret")
            results_faild_dic = process_loop_ret_faild(ret_faild, dev_map)
        logger.debug("retry stop")
    except Exception:
        logger.error(traceback.format_exc())
        return None

    logger.debug("retry sucess num %s" % len(results))
    if results:
        for resu in results:
            host = resu["host"]
            name = resu["name"]
            code = resu["code"]
            firstLayer = resu["firstLayer"]
            retry_time = datetime.now()
            for uid in urls_list:
                db.retry_re.insert(
                    {"uid": uid, "host": host, "name": name, "firstLayer": firstLayer, "code": code,
                     "num": count,"retry_time":retry_time})
    if error_result or results_faild_dic:
        if count == RETRY_COUNT:
            # print '------------errror-------------'
            # print error_result
            # print results_faild_dic
            logger.info("retry fail start insert mongodb ")
            fail_list = [error_result, results_faild_dic]
            for fail_dev_list in fail_list:
                for k, resu in list(fail_dev_list.items()):
                    host = resu["host"]
                    name = resu["name"]
                    code = resu["code"]
                    firstLayer = resu["firstLayer"]
                    retry_time = datetime.now()
                    for uid in urls_list:
                        db.retry_re.insert(
                            {"uid": uid, "host": host, "name": name, "firstLayer": firstLayer, "code": code,
                             "num": count,"retry_time":retry_time})
        return None
    return dev_id


def getUserList():
    userList = []
    key_customers_monitor = db['key_customers_monitor']
    for config in key_customers_monitor.find():
        try:
            userList.append(str(config.get('USERNAME')))
        except Exception:
            logger.info(e.message)
    return userList


def get_dev(dev_id):
    url_ref = db.ref_err.find_one({"dev_id": dev_id})
    url_url = db.url.find_one({"dev_id": dev_id})

    dev_list_sup_name = url_ref["f_devs"]
    dev_list_sub_name = url_ref["failed"]
    dev_list_sup_map = {}
    dev_list_sub_map = {}

    rcms_dev_s, rcms_dev_f = get_rcms_devices([url_url])

    # print  type(dev_list_sup_name)
    if len(dev_list_sup_name) > 0:
        for name, ip in list(dev_list_sup_name.items()):
            if name in rcms_dev_f:
                info = {"name": name, "host": ip, 'firstLayer': True, "status": "OPEN"}
                dev_list_sup_map.setdefault(ip, info)
    for dev_x in dev_list_sub_name:
        for devices in dev_x['devices']:
            for name, ip in list(devices.items()):
                info = {"name": name, "host": ip, 'firstLayer': False, "status": "OPEN"}
                dev_list_sub_map.setdefault(ip, info)
    return dev_list_sup_map, dev_list_sub_map


def retry_send(pre_time, cur_time):
    logger.debug('retry start start_time:%s---end_time:%s' % (pre_time, cur_time))
    user_List = getUserList()
    """
    目标：重试多次
    1.ref_err --->dev_id---->[urls,urls]
    2.urls1.devices----->先刷上层，后刷下层 doolp
    3.getCodeFromXml
    4.都成功成功
    5.[dev_id,.......] 记录成功的Dev_id
    """

    find_dic = {"datetime": {"$gte": pre_time, "$lt": cur_time}, "username": {'$in': user_List}, "retry_success":{'$exists':False}}
    #find_result = db.ref_err.find(find_dic)
    field_dic = {"uid": 1, "dev_id": 1}
    find_result = db.ref_err.find(find_dic,field_dic)
    dev_id_map = {}
    for err_url in find_result:
        #dev_id_uid_list = dev_id_map.get(err_url['dev_id'], [])
        #dev_id_uid_list.append(err_url['uid'])
        #dev_id_map[err_url['dev_id']] = dev_id_uid_list
        logger.debug(err_url['uid'])
        dev_id_map.setdefault(err_url['dev_id'], []).append(err_url['uid'])
    print(dev_id_map)
    success_list = []
    for dev_id, uid_list in list(dev_id_map.items()):
        print(uid_list)
        logger.debug(uid_list)
        # try:
        url_list_result = db.url.find({'_id': {'$in': uid_list}})
        retry_url_list = []
        for url in url_list_result:
            url['id'] = str(url.pop('_id'))
            retry_url_list.append(url)
        # print retry_url_list
        if retry_url_list:
            print('-------------do_retry------------')
            logger.debug('--------------do_retry----------------')
            success_list += do_retry(uid_list, dev_id, retry_url_list)
            # except Exception,e:
            # logger.error('retry error :%s' % traceback.format_exc())
    return success_list


def getcommand(url_list_result):
    command = ''
    isdir = False
    if len(url_list_result) == 1 and url_list_result[0]['isdir']:
        ssid, command = getDirCommand(url_list_result)
        isdir = True
    else:
        command = getUrlCommand(url_list_result)
        isdir = False
    return isdir, command


def do_retry(uid_list, dev_id, retry_url_list):
    print('retry-----------')
    retry_time = datetime.now()
    # print uid_list
    db.url.update({"_id": {'$in': uid_list}}, {'$set': {'retry_num': 'RETRY','retry_time':retry_time}}, multi=True)

    dev_list_sup_map, dev_list_sub_map = get_dev(dev_id)
    isdir, command = getcommand(retry_url_list)
    # print 'command-----------'
    print(command)
    # print dev_list_sup_map
    # print 'command-----------'
    uid_success_list = []
    sup_result = retry_count(uid_list, command, dev_list_sup_map, dev_id,isdir)
    print(sup_result)
    logger.debug(sup_result)
    if sup_result:
        uid_success_list = retry_count(uid_list, command, dev_list_sub_map, dev_id,isdir)
    print(uid_success_list)
    logger.debug(uid_success_list)
    if uid_success_list:
        db.url.update({"_id": {'$in': uid_list}}, {'$set': {'status': 'FINISHED'}}, multi=True)
        db.ref_err.update({"uid": {'$in': uid_list}}, {"$set": {"retry_success": 1}}, multi=True)
    return uid_success_list


def retry_count(uid_list, command, dev_list_map, dev_id,isdir):
    sucess_uid = []
    for count in range(RETRY_COUNT):
        result = retry_fail_dev(uid_list, command, dev_list_map, dev_id, count,isdir)
        if result:
            sucess_uid = uid_list
            break
    return sucess_uid


def run():
    # global now, start_str, emails, cur_time, pre_time, config_dic, ref_err, key, key1, config, emailResult, email
    now = datetime.now()
    start_str = 'start script on {datetime}'.format(datetime=now)
    logger.info(start_str)
    emails = {}
    # cur_time = datetime.combine(now.date(), now.time().replace(minute=0, second=0, microsecond=0))
    cur_time = datetime.combine(now.date(), now.time().replace(second=0, microsecond=0))
    # pre_time = cur_time + timedelta(hours=1)
    future_time = cur_time + timedelta(minutes=10)
    pre_time = cur_time - timedelta(minutes=30)
    #future_time = cur_time - timedelta(minutes=1)
    #pre_time = cur_time - timedelta(minutes=30)
    logger.info('begin_date:%s  end_date:%s' % (pre_time, cur_time))
    config_dic = get_key_customers_monitor()
    uid_succss_list = []

    try:
        print(start_str)
        uid_succss_list = retry_send(pre_time, future_time)
        end_time = datetime.now()
        end_str = 'finish script on {datetime}, use {time}'.format(datetime=end_time, time=end_time - now)
        print(end_str)
        logger.debug("get retry success list {0}".format(uid_succss_list))
    except Exception:
        logger.debug('retry_send error:%s' % traceback.format_exc())
    print("---------------uid------------------")
    print(uid_succss_list)
    logger.debug(uid_succss_list)
    for ref_err in get_ref_errs(pre_time, cur_time):
        if ref_err['uid'] in uid_succss_list:
            continue
        try:
            key = '%s_%s' % (str(ref_err.get('username', '')), str(ref_err.get('channel_code', '')))
            key1 = '%s_' % str(ref_err.get('username', ''))
            config = config_dic.get(key, config_dic.get(key1, ''))
            logger.debug('key:%s, key1:%s, config:%s' % (key, key1, config))
            # logger.debug("ref_err:%s" % ref_err)
            print("---------------")
            print(config)
            if config:
                logger.debug(' config:%s' % config)
                str_flag = str(config.get('USERNAME', '')) + '_' + str(config.get('Channel_Code', ''))
                if str_flag not in emails:
                    emailResult = '\r\n%s 客户下存在刷新失败\n\n' % ref_err.get('username', '')
                emailResult += '\n%s\n' % ref_err.get('url', '')
                emailResult += get_failed_dev(ref_err.get('devices', ''))
                emailResult += '\r\n----------------------------------------------------------------------------' \
                               '----------\r\n'
                email = [{"username": ref_err.get('username', ''), "to_addrs": config.get('Monitor_Email', []),
                          "title": '刷新失败任务', "body": emailResult}]
                # emails['%s_%s' % (str(config.get('USERNAME', '')), str(config.get('Channel_Code', '')))] = email

                if str_flag in emails:
                    email_temp = emails[str_flag]
                    email_temp[0]['body'] += emailResult

                    emails[str_flag] = email_temp
                else:
                    emails[str_flag] = email
                emailResult = ''
        except Exception:
            logger.debug('error:%s' % e)
    logger.info(emails)
    for email in list(emails.values()):
        queue.put_json2('email', email)
    os._exit(0)


if __name__ == "__main__":
    run()


