# -*- coding:utf-8 -*-
"""
Created on 2017-3-22

@author: junyu.guo
"""
import sys
import imp
imp.reload(sys)

import traceback
import time
import simplejson as json
import logging
import zlib
import asyncio
from .asyncpostal import AioClient, doTheLoop

from . import redisfactory
from .config import config
from .models import STATUS_CONNECT_FAILED, STATUS_SUCCESS
from util import log_utils


RETRY_DELAY_TIME = 3
RETRY_COUNT = 2
logger = log_utils.get_cert_postal_Logger()


def doloop(devs, tasks,  connect_timeout=5, response_timeout=8):
    """
    调用asyncore，创建信道，与设备通过socket连接,端口61108
    :param devs:
    :param command:
    :return:
    """
    clients = []
    # http_results = []
    my_map = {}
    port = 51108
    pre_ret = []
    pre_ret_faild = []

    command = zlib.compress(get_command(tasks))

    for dev in devs:
        clients.append(AioClient(dev['host'], port, '', command, connect_timeout, response_timeout))

    results = doTheLoop(clients, logger)

    for r in results:

        response_body = r.get('response_body')
        total_cost = r.get('total_cost')
        connect_cost = r.get('connect_cost')
        response_cost = r.get('response_cost')
        response_code = r.get('response_code')

        if response_body:
            try:
                pre_ret.append(r.get('host') + '\r\n' + response_body.split('\r\n\r\n')[1] + '\r\n%d\r\n%.2f\r\n%.2f\r\n%.2f' % (
                    response_code, total_cost, connect_cost, response_cost))
                # logger.warn("devs: %s doloop response_body: %s" % (devs, response_body))
                logger.debug("pre_host_test:%s, response_code_test:%s, response_body:%s" %
                             (r.get('host'), response_code, response_body))
            except Exception:
                logger.error("pre_devs: %s doloop response_body error: %s" % (devs, response_body))
                logger.error("doloop error: %s" % traceback.format_exc())
        else:
            # handling the case without response_body
            pre_ret_faild.append(r.get('host') + '\r\n%d\r\n%.2f\r\n%.2f\r\n%.2f' % (
                response_code, total_cost, connect_cost, response_cost))

    return pre_ret, pre_ret_faild


def process_loop_ret(http_results, dev_map):
    """
    处理返回值
    :param http_results:
    :param dev_map:需要执行的设备
    """
    results = []
    error_result = {}
    for result in http_results:
        try:
            host, _body, a_code, total_cost, connect_cost, response_cost = result.split('\r\n')
            dev = dev_map.pop(host)
        except Exception:
            logger.debug("cert_trans_postal process_loop_ret result has problem:%s, error:%s" %
                         (result, traceback.format_exc()))
            host, str_temp = result.split('\r\n', 1)
            dev = dev_map.pop(host)
            results.append(getPostStatus(dev, 0, 0, 0, 0, 0, 0))
            continue
        try:

            json_obj = json.loads(_body)
            _code = json_obj['status']

            if _code == 200:
                results.append(
                    getPostStatus(dev, _code, total_cost, connect_cost, response_cost, int(a_code)))
            else:
                error_result[host] = getPostStatus(
                    dev, _code, total_cost, connect_cost, response_cost, int(a_code))
                dev_map.setdefault(host, dev)
                logger.error("%s response error,code: %s" % (host, _code))
        except Exception:
            dev_map.setdefault(host, dev)
            error_result[host] = getPostStatus(
                dev, STATUS_CONNECT_FAILED, total_cost, connect_cost, response_cost, int(a_code))
            logger.error("cert %s response 500 error,%s: %s" % (host, len(_body), _body))
            logger.error(traceback.format_exc())

    return results, error_result


def process_loop_ret_faild(ret, dev_map):
    """
    处理失败的返回
    :param ret:
    :return:
    """
    results = {}
    for result in ret:
        host, a_code, total_cost, connect_cost, response_cost = result.split('\r\n')
        dev = dev_map.pop(host)
        try:

            results[host] = getPostStatus(dev, STATUS_CONNECT_FAILED,
                                          total_cost, connect_cost, response_cost, int(a_code))
            dev_map.setdefault(host, dev)

        except Exception:
            dev_map.setdefault(host, dev)
            logger.error('process_loop_ret_faild error ')
            logger.error(traceback.format_exc())
    return results


def retry(devs, urls, results_faild_dic):
    """
    失败后重新下发命令
    :param devs:
    :param command:
    :param node_name:
    :return:
    """

    ret_map = {}
    connect_timeout = 7
    response_timeout = 10
    for dev in devs:

        try:
            ret_map.setdefault(dev.get("host"), results_faild_dic[dev.get("host")])
        except Exception:
            logger.debug('retry dev error:{0},{1}'.format(dev.get("host"), results_faild_dic))

    for retry_count in range(RETRY_COUNT):
        logger.debug('%s retry cert begin len devs %s' % (retry_count, len(devs)))
        time.sleep(RETRY_DELAY_TIME)

        ret, ret_faild = doloop(devs, urls, connect_timeout, response_timeout)

        for result in ret:
            try:
                host, _body, a_code, total_cost, connect_cost, response_cost = result.split('\r\n')
            except Exception:
                logger.error("retry %s response error result: %s" % (host, result))
            try:
                json_obj = json.loads(_body)
                ret_map.get(host)["code"] = json_obj['status']
                ret_map.get(host)["connect_cost"] = connect_cost
                ret_map.get(host)["response_cost"] = response_cost
                ret_map.get(host)["total_cost"] = total_cost
                ret_map.get(host)["r_code"] = int(a_code)
                ret_map.get(host)["times"] = 1
                logger.debug("retry host_test1:%s, code_test1:%s, r_code_test1:%s" %
                             (host, _body, a_code))
            except Exception:
                logger.error("retry %s response error _body: %s" % (host, _body))
                logger.error(traceback.format_exc())

        for w in ret_faild:
            try:
                host, a_code, total_cost, connect_cost, response_cost = w.split('\r\n')
            except Exception:
                logger.error("retry %s response error result: %s" % (host, w))
            try:
                ret_map.get(host)["connect_cost"] = connect_cost
                ret_map.get(host)["response_cost"] = response_cost
                ret_map.get(host)["total_cost"] = total_cost
                ret_map.get(host)["r_code"] = int(a_code)
                ret_map.get(host)["times"] = 1
                logger.debug("host_test2:%s, r_code_test2:%s" % (host, a_code))
            except Exception:
                logger.error("%s response error" % (host))
                logger.error(traceback.format_exc())

    return list(ret_map.values())


def getPostStatus(dev, statusCode, total_cost=0, connect_cost=0, response_cost=0, a_code=200, r_code=200):
    return {"host": dev.get('host'),
            "name": dev.get('name'), "code": statusCode, "total_cost": total_cost, "connect_cost": connect_cost,
            "response_cost": response_cost, "a_code": a_code, "r_code": r_code, "times": 0,
            }


def get_command(tasks):
    '''
    生成下发命令
    '''
    commands = []

    for t in tasks:
        co = {'cert': t.get('cert', ''), 'p_key': t.get('p_key', ''), 's_name': t.get('s_name'), 'task_id': t.get(
            '_id', ''), 'seed': t.get('seed', ''), 'op_type': t.get('op_type', ''), 's_dir': t.get('s_dir', '')}
        commands.append(co)

    return json.dumps(commands)
