# -*- coding:utf-8 -*-
"""
Created on 2011-5-31

@author: wenwen
"""
import sys
import imp
imp.reload(sys)

import httplib2 as httplib
import  asyncore ,traceback  ,time
from xml.dom.minidom import parseString
import simplejson as json
import logging
from .asyncpostal import AioClient, doTheLoop

from . import redisfactory
from .config import config
from .models import  STATUS_CONNECT_FAILED,STATUS_SUCCESS
from util import log_utils
from .command_factory import get_command, get_command_json
import requests

DIR_COMMAND_EXPIRE = 12 * 3600
RETRY_DELAY_TIME = int(config.get("preload_retry","delay_time"))
RETRY_COUNT = int(config.get("preload_retry","count"))
blackListDB = redisfactory.getDB(1)
# logger = logging.getLogger('preload_postal')
# logger.setLevel(logging.DEBUG)
logger = log_utils.get_postal_Logger()

def doloop(devs, urls, connect_timeout=5, response_timeout=8):
    """
    调用asyncore，创建信道，与FC 通过socket连接,端口31108
    :param devs:
    :param command:
    :return:
    """
    clients = []
    # http_results = []
    my_map = {}
    port = 31108
    pre_ret = []
    pre_ret_faild = []
    have_first_layer = any([d.get('firstLayer') for d in devs])
    for dev in devs:
        logger.debug("doloop have_first_layer: %s|| firstLayer: %s" % (have_first_layer, dev.get('firstLayer')))
        if have_first_layer:
            if dev.get('firstLayer'):
                clients.append(AioClient(dev.get('host'), port, '', get_command_json(urls, urls[0].get("action"), dev, check_conn=True), connect_timeout, response_timeout))
            else:
                clients.append(AioClient(dev.get('host'), port, '', get_command_json(urls, urls[0].get("action"), dev), connect_timeout, response_timeout))
        else:
            clients.append(AioClient(dev.get('host'), port, '', get_command_json(urls, urls[0].get("action"), dev, check_conn=True), connect_timeout, response_timeout))

    results = doTheLoop(clients, logger)
    # results: [{'response_body': '{"pre_ret_list":[{"code":200,"id":"5bdadaf13b7750a74daa0008"}],"sessionid":"3cb13f1eddc411e8afd8000c29629177"}', 'total_cost': 0.0890894599724561, 'connect_cost': 0.029646086040884256, 'response_cost': 0.05891382892150432, 'response_code': 200, 'host': '61.147.92.6', 'strerror': 'no_error'}]

    for r in results:
        response_body, total_cost, connect_cost, response_cost, response_code = r.get('response_body'), r.get('total_cost'), r.get('connect_cost'), r.get('response_cost'), r.get('response_code')

        if response_body:
            try:
                pre_ret.append(r.get('host') + '\r\n' + response_body + '\r\n%d\r\n%.2f\r\n%.2f\r\n%.2f' % (
                    response_code, total_cost, connect_cost, response_cost))
                # logger.warn("devs: %s doloop response_body: %s" % (devs, response_body))
                logger.debug("doloop pre_host_test: %s|| response_code_test: %s|| response_body: %s" % (
                    r.get('host'), response_code, response_body))
            except Exception:
                logger.error("doloop [error] pre_devs: %s|| response_body: %s" % (devs, response_body))
                logger.error("doloop error: %s" % traceback.format_exc())
        else:
            pre_ret_faild.append(r.get('host') + '\r\n%d\r\n%.2f\r\n%.2f\r\n%.2f' % (response_code, total_cost, connect_cost, response_cost))

    logger.debug("doloop results: %s|| pre_ret: %s|| pre_ret_faild: %s" % (results, pre_ret, pre_ret_faild))
    return pre_ret, pre_ret_faild


def process_loop_ret(http_results, dev_map):
    """
    处理发送给FC后，FC返回的XML结果 parse
    :param http_results:
    :param dev_map:需要执行的设备
    :return:
    """
    results = []
    error_result = {}
    # logger.debug("process_loop_ret http_results: %s|| dev_map: %s" % (http_results, dev_map))
    for result in http_results:
        try:
            host, body, a_code, total_cost, connect_cost, response_cost = result.split('\r\n')
            dev = dev_map.pop(host)
        except Exception:
            logger.debug("process_loop_ret result has problem: %s|| error: %s" % (result, traceback.format_exc()))
            host, str_temp = result.split('\r\n', 1)
            dev = dev_map.pop(host)
            results.append(getPostStatus(dev, 0, 0, 0, 0, 0, 0))
            continue
        try:
            has_error = False
            json_obj = json.loads(body)
            for _info in json_obj['pre_ret_list']:
                _info_code = _info['code']
                if _info_code == '404' or _info_code == '408':
                    dev_map.setdefault(host, dev)
                    has_error = True
                    error_result[host] = getPostStatus(dev, int(_info_code), total_cost, connect_cost, response_cost, int(a_code))
                    logger.error("%s response error,code: %s" % (host, _info_code))
                    break

           # for node in parseString(xml_body).getElementsByTagName(node_name):
           #     if node.firstChild.data == '404' or node.firstChild.data == '408':
           #         dev_map.setdefault(host, dev)
           #         has_error = True
           #         error_result[host] = getPostStatus(dev, int(node.firstChild.data), total_cost, connect_cost, response_cost, int(a_code))
           #         logger.error("%s response error,code: %s" % (host, node.firstChild.data))
           #         break
            if not has_error:
                results.append(
                    getPostStatus(dev, int(json_obj['pre_ret_list'][0]['code']), total_cost, connect_cost, response_cost, int(a_code)))
        except Exception:
            dev_map.setdefault(host, dev)
            error_result[host] = getPostStatus(dev, STATUS_CONNECT_FAILED, total_cost, connect_cost, response_cost, int(a_code))
            logger.error("%s response error,%s: %s" % (host, len(body), body))
            logger.error(traceback.format_exc())
    return results, error_result


# copy from core/postal.py
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
            results[host] = getPostStatus(dev, STATUS_CONNECT_FAILED, total_cost, connect_cost, response_cost, int(a_code))
            dev_map.setdefault(host, dev)
        except Exception:
            dev_map.setdefault(host, dev)
            logger.error(traceback.format_exc())
    return results

def retry(devs, urls, pre_results_faild_dic):
    """
    失败后重新下发命令
    :param devs:
    :param command:
    :param node_name:
    :return:
    """

    ret_map = {}
    connect_timeout = 6
    response_timeout = 10
    for dev in devs:
        # original code
        # ret_map.setdefault(dev.get("host"), getPostStatus(dev, STATUS_CONNECT_FAILED))
        try:
            ret_map.setdefault(dev.get("host"), pre_results_faild_dic[dev.get("host")])
        except Exception:
            logger.debug('retry dev error:{0},{1}'.format(dev.get("host"), pre_results_faild_dic))
    #for retry_count in range(RETRY_COUNT):
    for retry_count in range(3):
        #time.sleep(RETRY_DELAY_TIME)
        time.sleep(2)
        ret, ret_faild = doloop(devs, urls, connect_timeout, response_timeout)

        for result in ret:
            try:
                host, body, a_code, total_cost, connect_cost, response_cost = result.split('\r\n')
            except Exception:
                logger.error("%s response error result: %s" % (host, result))
            try:
                json_obj = json.loads(body)
                ret_map.get(host)["code"] = int(json_obj['pre_ret_list'][0]['code'])
                ret_map.get(host)["connect_cost"] = connect_cost
                ret_map.get(host)["response_cost"] = response_cost
                ret_map.get(host)["total_cost"] = total_cost
                ret_map.get(host)["r_code"] = int(a_code)
                ret_map.get(host)["times"] = 1
                logger.debug("host_test1:%s, code_test1:%s, r_code_test1:%s" % (host, body, a_code))
            except Exception:
                logger.error("%s response error xml_body: %s" % (host, body))
                logger.error(traceback.format_exc())

        for w in ret_faild:
            try:
                host, a_code, total_cost, connect_cost, response_cost = w.split('\r\n')
            except Exception:
                logger.error("%s response error result: %s" % (host, w))
            try:
                ret_map.get(host)["connect_cost"] = connect_cost
                ret_map.get(host)["response_cost"] = response_cost
                ret_map.get(host)["total_cost"] = total_cost
                ret_map.get(host)["r_code"] = int(a_code)
                ret_map.get(host)["times"] = 1
                logger.debug("host_test2:%s, r_code_test2:%s" % (host, a_code))
            except Exception:
                logger.error("%s response error xml_body: %s" % (host, body))
                logger.error(traceback.format_exc())

        # not asyn to send task
        # if retry_send(ret_map, urls, node_name):
        #     break
    return list(ret_map.values())


#未引用
def retry_send(ret_map, urls, node_name):
    """
    失败后重新发送命令,不采用asyncore发送,直接用http发送
    :param ret_map:
    :param command:
    :param node_name:
    :return:
    """
    devs = [dev for dev in list(ret_map.values()) if dev.get("code") == STATUS_CONNECT_FAILED]
    ret, wrongRet = doSend_HTTP(devs, urls)
    for result in ret:
        try:
            host, xml_body, total_cost = result.split('\r\n')
        except Exception:
            logger.error("%s response error result: %s" % (host, result))
        try:
            ret_map.get(host)["code"] = getCodeFromXml(xml_body, node_name)
            ret_map.get(host)["r_cost"] = total_cost
            ret_map.get(host)["r_code"] = STATUS_SUCCESS
        except Exception:
            logger.error("%s response error xml_body: %s" % (host, xml_body))
            logger.error(traceback.format_exc())
    for w in wrongRet:
        try:
            host, r_code, total_cost = w.split('\r\n')
        except Exception:
            logger.error("%s response error result: %s" % (host, w))
        try:
            ret_map.get(host)["r_cost"] = total_cost
            ret_map.get(host)["r_code"] = int(r_code)
        except Exception:
            logger.error("%s response error xml_body: %s" % (host, xml_body))
            logger.error(traceback.format_exc())
    if len(devs) == len(ret):
        return True
        

def getCodeFromXml(xmlBody,nodeName):
    node = parseString(xmlBody).getElementsByTagName(nodeName)[0]
    return int(node.firstChild.data)
# original code
# def getPostStatus(dev, statusCode):
#     return {"host": dev.get('host'), "firstLayer": dev.get('firstLayer'),
#             "name": dev.get('name'), "code": statusCode}


def getPostStatus(dev, statusCode, total_cost=0, connect_cost=0, response_cost=0, a_code=200, r_code=200):
    return {"host": dev.get('host'), "firstLayer": dev.get('firstLayer'),
            "name": dev.get('name'), "code": statusCode, "total_cost": total_cost, "connect_cost": connect_cost,
            "response_cost": response_cost, "a_code": a_code, "r_code": r_code, "times": 0}


def doSend_HTTP(devs, urls):
    """
     重试时直接用requests发送，会增加一个返回码的判断
    :param devs:
    :param command:
    :return:
    """
    results = []
    wrongRet = []
    for dev in devs:
        r_code = 200
        try:
            start_time = time.time()
            rc = requests.post("http://%s:%d" % (dev['host'], 31108), data=get_command(urls, urls[0].get("action"), dev['host']), timeout=(2, 10))#connect_timeout 2s reponse_timeout 5s
            rc.raise_for_status()

            response_body = rc.text
            total_cost = time.time() - start_time

            results.append(dev['host'] + '\r\n' + response_body + '\r\n%.2f' % total_cost)

        except requests.ConnectionError as e:
            r_code = 503
            total_cost = time.time() - start_time
            wrongRet.append(dev['host'] + '\r\n%d\r\n%.2f' % (r_code, total_cost))
        except requests.Timeout:
            r_code = 501
            total_cost = time.time() - start_time
            wrongRet.append(dev['host'] + '\r\n%d\r\n%.2f' % (r_code, total_cost))
        except Exception:
            r_code = 502
            total_cost = time.time() - start_time
            wrongRet.append(dev['host'] + '\r\n%d\r\n%.2f' % (r_code, total_cost))
            logger.error("%s connect error." % dev.get('host'))
            logger.error("connect error :%s ." % (traceback.format_exc()))
        logger.debug('retry %s  r_code: %d r_cost: %.2f' % (dev['host'], r_code, total_cost))
    return results, wrongRet



if __name__ == '__main__':
    urls = [{'action': 'preload', 'priority': 1, 'is_override': 0, 'check_type': "BASIC",
             'url': 'http://flv4.people.com.cn/hds-vod/1.html', 'check_value': '-', 'report_address': '223.202.203.52',"_id": '123'}]
    devs = [{'host': "119.188.138.38"}]
    pre_ret, pre_ret_faild = doloop(devs, urls)
    print("pre_ret:%s" % pre_ret)
    print("pre_ret_faild:%s" % pre_ret_faild)

    pass



