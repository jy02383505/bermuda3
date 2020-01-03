# -*- coding:utf-8 -*-
from sys import exit
from xml.dom import minidom
from xml.dom.minidom import parseString
from datetime import datetime, timedelta
import logging
import cache.util_redis_api as redisutil
import hashlib
import time
# import bson
from core.generate_id import ObjectId
from flask import Blueprint, request, make_response
from flask import jsonify
from werkzeug.exceptions import Forbidden, HTTPException
import simplejson as json
from util import log_utils
from core import rcmsapi, authentication, preload_worker, preload_worker_new, database, redisfactory, queue
from core.models import PRELOAD_URL_OVERLOAD_PER_HOUR
from core.rcmsapi import get_channelname_from_url
from core.config import config
from util.tools import load_task, get_preload_overload_cache
import traceback
import urllib.request, urllib.parse, urllib.error
import urllib.request, urllib.error, urllib.parse
import socket
from util.webluker_tools import get_urls_preload
from core.preload_webluker import task_forward

query_db = database.query_db_session()
s1_db = database.s1_db_session()

# logger = logging.getLogger('receiver')
# logger.setLevel(logging.DEBUG)
logger = log_utils.get_preload_Logger()

PRELOAD_CACHE = redisfactory.getDB(1)
COUNTER_CACHE = redisfactory.getDB(4)
PRELOAD_DEVS = redisfactory.getDB(5)
CHECK_CACHE = redisfactory.getDB(8)

preload = Blueprint('preload', __name__,
                    template_folder='templates', static_folder='static')

RECEIVER_HOST = socket.gethostname()


@preload.route('/preload_api', methods=['GET', 'POST'])
def preload_api():
    '''
    这个接口主要起到转化参数的作用，让新的参数组织方式能够更好的适配之前的各个接口。
    '''
    st = time.time()
    logger.debug('preload_api request.data: %s|| remote_addr: %s|| request.headers.get("X-Real-Ip"): %s' % (request.data, request.remote_addr, request.headers.get("X-Real-Ip")))
    try:
        remote_ip = request.headers.get('X-Real-Ip')
        logger.debug('preload_api remote_ip: %s' % (remote_ip))
        request.remote_ip = remote_ip
        logger.debug('preload_api request.remote_ip: %s|| request.remote_addr: %s' % (request.remote_ip, request.remote_addr))
        r = receiver_preload_json()
        logger.debug('preload_api [transfer request done.] It takes %s seconds.' % (time.time()-st, ))
        return r

    except Exception:
        logger.error('preload_api [error]: %s' % (traceback.format_exc(), ))
        return jsonify({"code": 500, "msg": "Request Transferred Fail."})


@preload.route('/internal/preload', methods=['GET', 'POST'])
def receiver_preload_json():
    # logger.debug('receiver_preload_json request: %s|| request.headers: %s' % (request, request.headers))
    st = time.time()
    logger.debug('receiver_preload_json request.data: %s|| remote_addr: %s' % (request.data, request.remote_addr))
    try:
        data = json.loads(request.data)
        if data.get('isSub', None):
            return jsonify(receiver_preload_json_new(request, type=data.get('type', 'portal')))
        else:
            return jsonify(receiver_preload_json_bak(request, st=st, iname='/internal/preload'))
    except ChannelError as e:
        return jsonify({"code": 405, "msg": e.__str__()})
    except OverloadError as e:
        return jsonify({"code": 406, "msg": e.__str__()})
    except InputError as e:
        return jsonify({"code": e.__code__(), "msg": e.__str__()})
    except Forbidden as e:
        return jsonify({"code": 403, "msg": e.description})
    except Exception as e:
        logger.error('receiver_preload_json [error: %s]: %s' % (e.__str__(), traceback.format_exc(), ))
        return jsonify({"code": 500, "msg": "The schema of request is error."})


@preload.route('/internal/preload/avoid', methods=['GET', 'POST'])
def preload_avoid():
    st = time.time()
    logger.debug('preload_avoid request.data: %s, request.remote_addr: %s' % (request.data, request.remote_addr))
    try:
        data = json.loads(request.data)
        return_dict = {
            "err": "noerror",
            "effect": "unknown",
            "values": [
                ### {"itemid":34235, "result":0},
                ### {"itemid":34235, "result":2},
                ### {"itemid":34235, "result":-1},
            ]
        }

        url_list = [{'url': 'http:/' + i['url'], 'itemid': i['itemid']}
                    if i['url'].startswith('/') else {'url': i['url'], 'itemid': i['itemid']} for i in data.get('addfile', [])]
        data['tasks'] = []
        data['validationType'] = 'BASIC'
        for u in url_list:
            return_value = {}
            return_value['itemid'] = u.get('itemid')
            return_value['result'] = 0  # url received successfully
            # cut the urls repeated for qq
            if not data.get('is_repeated') and had_preload_url('qq', u.get('url')):
                return_value['result'] = 2  # url repeated
                return_dict['values'].append(return_value)
                continue
            return_dict['values'].append(return_value)
            task = {}
            task['url'] = u.get('url')
            task['id'] = hashlib.md5(u.get('url', '')).hexdigest() + '_qq'
            data['tasks'].append(task)

        channel_set = set()
        [channel_set.add(get_channelname_from_url(u.get('url'))) for u in url_list]
        for c in channel_set:
            if c in ['http://vhotlx.video.qq.com', 'http://vkplx.video.qq.com', 'http://ltslx.qq.com', 'http://stslx.qq.com']:
                data['username'] = 'qq'
                break
        logger.debug('preload_avoid channel_set: %s, url_list: %s, return_dict: %s, data: %s' %
                     (channel_set, url_list, return_dict, data))

        request.data = json.dumps(data)
        if data.get('isSub', None):
            return jsonify(receiver_preload_json_new(request, type=data.get('type', 'portal')))
        else:
            return jsonify(receiver_preload_json_bak(request, return_dict=return_dict, st=st, iname='/internal/preload/avoid'))

    except ChannelError as ex:
        return_dict.update({"code": 405, "msg": ex.__str__()})
    except OverloadError as ex:
        return_dict.update({"code": 406, "msg": ex.__str__()})
    except InputError as e:
        return_dict.update({"code": e.__code__(), "msg": e.__str__()})
    except Forbidden as e:
        return_dict.update({"code": 403, "msg": e.description})
    except Exception:
        logger.debug(traceback.format_exc())
        logger.debug(e.__str__())
        return_dict.update({"code": 500, "msg": "The schema of request is error."})
    return_value['result'] = -1  # url repeated
    return jsonify(return_dict)


@preload.route('/internal/preload/high', methods=['GET', 'POST'])
def receiver_preload_json_high():
    st = time.time()
    logger.debug('preload high data:%s   remote_addr:%s' % (request.data, request.remote_addr))
    try:
        data = json.loads(request.data)
        if data.get('isSub', None):
            return jsonify(receiver_preload_json_new(request, type=data.get('type', 'portal')))
        elif data.get('queue_name'):
            return jsonify(receiver_preload_json_bak(request, queue_name=data.get('queue_name'), st=st))
        else:
            return jsonify(receiver_preload_json_bak(request, queue_name='preload_task_h', st=st))
    except ChannelError as ex:
        return jsonify({"code": 405, "msg": ex.__str__()})
    except OverloadError as ex:
        return jsonify({"code": 406, "msg": ex.__str__()})
    except InputError as e:
        return jsonify({"code": e.__code__(), "msg": e.__str__()})
    except Forbidden as e:
        return jsonify({"code": 403, "msg": e.description})
    except Exception:
        logger.debug(traceback.format_exc())
        logger.debug(e.__str__())
        return jsonify({"code": 500, "msg": "The schema of request is error."})


@preload.route('/internal/preloadDevice', methods=['GET', 'POST'])
def receiver_preload_device():
    # 多玩需求，发任务同时带设备，收到任务判断有没有设备，没有直接返回提示
    try:
        st = time.time()
        logger.debug('preload data:%s remote_addr:%s' % (request.form, request.remote_addr))
        # username = request.form.get('username', '').lower()
        username = request.form.get('username', '')
        ticket = authentication.internal_verify(username, request.remote_addr)
        message = {}
        task_list, invalids = get_preload_devices(request, ticket, type='API')
        logger.debug("receiver_preload_device task_list:%s" % task_list)
        if task_list:
            logger.debug("receiver_preload_device[/internal/preloadDevice -- takes(before putjson2)]: %s seconds." % (time.time() - st))
            queue.put_json2("preload_task", task_list)
            # queue.put_json2("preload_task", task_list, st=st, iname='/internal/preloadDevice')
            logger.debug("receiver_preload_device[/internal/preloadDevice -- takes(after putjson2)]: %s seconds." % (time.time() - st))
            if invalids:
                message['invalids'] = invalids
                message['code'] = 201
            else:
                message['code'] = 0
                message['msg'] = 'ok'
        else:
            message['code'] = 202
            message['msg'] = 'urls is error'
        return jsonify(message)
    except ChannelError as ex:
        return jsonify({"code": 405, "msg": ex.__str__()})
    except OverloadError as ex:
        return jsonify({"code": 406, "msg": ex.__str__()})
    except NoDevicesError as ex:
        return jsonify({"code": 407, "msg": ex.__str__()})
    except InputError as e:
        return jsonify({"code": e.__code__(), "msg": e.__str__()})
    except NoChannelError as ex:
        return jsonify({"code": 408, "msg": ex.__str__()})
    except HTTPException as ex:
        raise ex
    except Exception:
        logger.debug(e.__str__())
        logger.debug('exception error:%s' % traceback.format_exc())
        return jsonify({"code": 500, "msg": "The schema of request is error."})


@preload.route('/internal/preload/devices', methods=['GET', 'POST'])
def preload_with_devices():
    '''
    General preload interface with customized device_list.
    '''
    try:

        logger.debug('preload_with_devices data:%s remote_addr:%s' % (request.data, request.remote_addr))
        data = json.loads(request.data)
        username = data.get('username', '')
        tasks = data.get('tasks')
        user_type = data.get('user_type') # if == 'webluker'; get devices from webluker interface
        username_wlk = data.get('username_wlk')
        sign_wlk = data.get('sign_wlk')
        domains_wlk = data.get('domains_wlk')
        if user_type == 'webluker' and (not username_wlk or not sign_wlk or not domains_wlk):
            return jsonify({"code": 409, "msg": 'Parameters are not correct for webluker tasks.'})

        isValidStartTime(data.get("startTime"))

        url_0 = tasks[0].get('url')
        channel_name = get_channelname_from_url(url_0)

        if username not in ['duowan']:
            had_config = PRELOAD_DEVS.exists(channel_name)
            if not had_config:
                logger.debug('%s not config channel' % channel_name)
                raise ChannelError('%s not config channel' % channel_name)

        message = {}
        device_list = data.get('device_list', [])
        if not device_list and user_type != 'webluker':
            return jsonify({"code": 407, "msg": 'No devices.'})

        if user_type not in ['webluker']:
            isValid, is_multilayer, channel_code, ignore_case = rcmsapi.isValidUrl(username, url_0)
            logger.debug("preload_with_devices isValid: %s|| is_multilayer: %s|| channel_code: %s|| ignore_case: %s" % (isValid, is_multilayer, channel_code, ignore_case))

            c_code = channel_code
            devs_all = PRELOAD_DEVS.get('%s_devs' % channel_name)
            if not devs_all:
                from core.preload_worker_new import init_pre_devs
                devs_all = init_pre_devs(channel_code, True)
                PRELOAD_DEVS.set('%s_devs' % channel_name, json.dumps(devs_all))
                PRELOAD_DEVS.expire('%s_devs' % channel_name, 60*20)
            else:
                devs_all = json.loads(devs_all)
        else:
            c_code = 'webluker'
            devs_all = PRELOAD_DEVS.get('%s_devs_wlk' % channel_name)
            if not devs_all:
                devs_all = get_wlk_devices(username_wlk, sign_wlk, domains_wlk)
                PRELOAD_DEVS.set('%s_devs_wlk' % channel_name, json.dumps(devs_all))
                PRELOAD_DEVS.expire('%s_devs_wlk' % channel_name, 60*20)
            else:
                devs_all = json.loads(devs_all)
        task_list = generate_preload_data(request, devs_all, c_code)
        logger.debug("preload_with_devices task_list: %s" % task_list)
        if task_list:
            queue.put_json2("preload_task", task_list)
            message['code'] = 0
            message['msg'] = 'ok'
        else:
            message['code'] = 202
            message['msg'] = 'task_list has errors.'
        return jsonify(message)
    except ChannelError as ex:
        return jsonify({"code": 405, "msg": ex.__str__()})
    except OverloadError as ex:
        return jsonify({"code": 406, "msg": ex.__str__()})
    except InputError as e:
        return jsonify({"code": e.__code__(), "msg": e.__str__()})
    except NoDevicesError as ex:
        return jsonify({"code": 407, "msg": ex.__str__()})
    except NoChannelError as ex:
        return jsonify({"code": 408, "msg": ex.__str__()})
    except HTTPException as ex:
        raise ex
    except Exception:
        logger.debug('preload_with_devices[error]: %s' % (traceback.format_exc(), ))
        return jsonify({"code": 500, "msg": "The schema of request is error."})


def receiver_preload_json_bak(request, queue_name='preload_task', return_dict=None, st=0, iname='/internal/preload/high'):
    data = json.loads(request.data)
    username = request.args.get('cloud_client_name') if request.args.get('cloud_client_name') else data.get("username", "")
    user_overload_max = get_preload_overload_cache(username)
    logger.debug('receiver_preload_json_bak user_overload_max: %s|| request.args: %s' % (user_overload_max, request.args))
    channel_set = set()
    for task in data.get('tasks'):
        channel_name = get_channelname_from_url(task.get('url', ''))
        channel_set.add(channel_name)
        had_config = PRELOAD_DEVS.exists(channel_name)
        if not had_config:
            logger.debug('%s not config channel' % channel_name)
            raise ChannelError('%s not config channel' % channel_name)
        else:
            if set_preload_overload(username) > int(user_overload_max):
                raise OverloadError("PRELOAD_URL_OVERLOAD_PER_HOUR")

    if data.get('speed') and data['speed'] not in ['0']:
        channel_num = len(channel_set)
        if '.' not in data.get('speed'):
            import re
            from math import ceil
            limit_pattern = r'(\d+)\s?(\w+)'
            match_obj = re.match(limit_pattern, data['speed'])
            # Without Words - Josh Vietti
            data['speed'] = '%d%s' % (int(ceil(int(match_obj.group(1)) / float(channel_num))), match_obj.group(2))
            logger.debug("receiver_preload_json_bak data: %s|| channel_num: %s" % (data, channel_num))
        else:
            return {"code": 403, "msg": "Parameter: speed is not Integer."}

    if username in ['qq']:
        class R(object):

            def __init__(self, data):
                self.data = data
        r = R(data)
        r.data = json.dumps(data)
        r.remote_addr = request.remote_ip if hasattr(request, 'remote_ip') else request.remote_addr
        p_task = get_preload(r, type=data.get('type', 'API'))
    else:
        p_task = get_preload(request, type=data.get('type', 'API'))

    logger.debug('receiver_preload_json_bak p_task_len: %s' % len(p_task))
    if p_task:
        logger.debug('receiver_preload_json_bak[%s -- Taking seconds before put_json2]: %s' % (iname, (time.time() - st)))
        queue.put_json2(queue_name, p_task)
        logger.debug('receiver_preload_json_bak[%s -- Taking seconds after put_json2]: %s' % (iname, (time.time() - st)))
    if not return_dict:
        return {"code": 0, "msg": "ok"}
    else:
        return_dict.update({"code": 0, "msg": "ok"})
        return return_dict


def set_dev_hpcc(d):
    if d.get('firstLayer') not in [True, 'True', 'true']:
        d['type'] = 'HPCC'
    return d


def get_wlk_devices(username, sign, domains=[]):
    '''    
    username -> webluker's username. 是专属于webluker的用户名.
    sign -> 不同的用户不同的sign.
    *domains -> channels list.
    '''
    try:
        # params = {
        #     'username': "huanjushidai-test",
        #     'domains': ['www.huanjushidai13.novacdn.com']
        # }

        params = {
            'username': username,
            'domains': domains
        }

        params['sign'] = getSign(params, sign)
        big_preload_url = "http://agent.webluker.com/api/getfcdevice/"
        # big_preload_url = "http://agent.webluker.com/api/getfcips/"
        params = urllib.parse.urlencode(params)
        res = urllib.request.urlopen(big_preload_url, data=params)
        r = json.loads(res.read())
        if r.get('head') != 'success':
            if isinstance(r.get('body'), str):
                msg = r.get('body')
            elif isinstance(r.get('body'), dict):
                msg = r.get('body').get('status')
            else:
                msg = 'Unknown error.body type is: %s|| body: %s' % (type(r.get('body')), r.get('body'))
            raise NoDevicesError('wlk_devs[error]: %s' % msg)
        devices = [set_dev_hpcc(i) for i in r.get('body') if i.get('status').lower() == 'open']
        return devices
    except NoDevicesError as e:
        raise NoDevicesError(msg)
    except Exception:
        logger.debug('get_wlk_devices[error]: %s' % (traceback.format_exc(), ))


def receiver_preload_json_new(request, type):
    message = {}
    task_list, invalids = get_preload_new(request, type=type)
    if task_list:
        queue.put_json2("preload_task", task_list)
        if invalids:
            message['code'] = 201
            message['invalids'] = invalids
        else:
            message['code'] = 0
            message['msg'] = 'ok'
    else:
        message['code'] = 202
        message['msg'] = 'urls is error'
    return message


@preload.route('/internal/preload/cancel', methods=['GET', 'POST'])
def receiver_preloadcancel_json():
    username, task_list = get_tasks(request)
    preload_worker.preload_cancel.delay(username, task_list)
    return jsonify({"code": 0, "msg": "ok"})


@preload.route('/internal/preload/channels', methods=['GET', 'POST'])
def query_cust():
    message = []
    for channel in query_db.preload_channel.find({"is_live": 0}, {'username': 1, 'channel_name': 1, '_id': 0}):
        message.append(
            {'channel': channel.get('channel_name'), 'username': channel.get('username')})
    response = make_response(json.dumps(message))
    response.headers['Content-Type'] = 'application/json'
    return response


@preload.route('/internal/preload/billing/channels', methods=['GET', 'POST'])
def query_billing_cust():
    """
    给计费的预加载接口
    开通了文件预推送的频道全列表接口

    :return:
    """
    message = []
    for channel in query_db.preload_channel.find({}, {'username': 1, 'channel_name': 1, 'channel_code': 1, '_id': 0}):
        message.append(
            {'channel': channel.get('channel_name'), 'username': channel.get('username'),
             'channel_code': channel.get('channel_code')})
    response = make_response(json.dumps(message))
    response.headers['Content-Type'] = 'application/json'
    return response


@preload.route('/internal/preload/search', methods=['GET', 'POST'])
def query_task():
    """
    任务状态查询接口

    :return:
    """
    try:
        logger.debug('query_task data: %s|| remote_addr: %s' % (request.data, request.remote_addr))
        count, tasks = get_query_task(request.data)
        find_result = {}
        find_result['totalCount'] = count
        find_result['tasks'] = []
        for task in tasks:
            info = percent_filesize(task.get('_id'), task.get('status'))
            find_result['tasks'].append(
                {'id': task.get('task_id'), 'url': task.get('url'), 'fileSize': conversion(info.get('file_size')),
                 'status': task.get('status'), 'startTime': task.get('start_time').strftime(
                    '%Y-%m-%d %H:%M:%S') if task.get('status') == 'TIMER' else task.get('created_time').strftime(
                    '%Y-%m-%d %H:%M:%S'),
                 'finishTime': task.get('finish_time').strftime('%Y-%m-%d %H:%M:%S') if task.get(
                     'finish_time') else '----', 'validationType': task.get('check_type'),
                 'percent': info.get('percent')})
        return jsonify(find_result)
    except InputError:
        return jsonify({"code": 500, "msg": "The schema of request is error."})


def get_tasks_from_api(ticket, tasks_list, status_list):
    """
    {"username": "verycd",
    "status":{"$in": ["PROGRESS","INVALID"]},
    "task_id": {"$in":["4698647","4698649"]}

     }
    :param ticket:
    :param tasks_list:
    :param status_list:
    :return: :raise InputError:
    """
    try:
        condition = {}
        if ticket.get('isSub', False):
            condition["username"] = ticket.get('name', '')
        else:
            condition["parent"] = ticket.get('parent', '')
        condition["task_id"] = {"$in": tasks_list}
        if status_list:
            condition["status"] = {"$in": status_list}

        logger.debug("get_query_task condition  from api %s" % condition)
        count = s1_db.preload_url.find(condition).count()

        tasks = s1_db.preload_url.find(condition).sort("created_time", -1).limit(100)
        return count, tasks
    except Exception:
        logger.debug(e)
        raise InputError(500, "The schema of request is error.")


def get_tasks_from_api_w(ticket, tasks_list, status_list):
    """
    {"username": "verycd",
    "status":{"$in": ["PROGRESS","INVALID"]},
    "task_id": {"$in":["4698647","4698649"]}

     }
    :param ticket:
    :param tasks_list:
    :param status_list:
    :return: :raise InputError:
    """
    try:
        condition = {}
        # if ticket.get('isSub', False):
        condition["username"] = ticket.get('name', '')
        # else:
        #     condition["parent"] = ticket.get('parent', '')
        condition["task_id"] = {"$in": tasks_list}
        if status_list:
            condition["status"] = {"$in": status_list}

        logger.debug("get_query_task condition  from api %s" % condition)
        count = s1_db.preload_url.find(condition).count()

        tasks = s1_db.preload_url.find(
            condition).sort("created_time", -1).limit(100)
        return count, tasks
    except Exception:
        logger.debug(e)
        raise InputError(500, "The schema of request is error.")


@preload.route('/content/preload/search', methods=['GET', 'POST'])
def query_task_api():
    """
    API任务状态查询接口
    :param data:
    {'username':'verycd',
         'password':'verycd@cc',
         'tasks': '[1,2,3]',
         # 'created_time':'2014-11-14 14:00:00',
         'status':["TIMER","PROGRESS","INVALID","FINISHED","FAILED"]
        }
    return:
        {
        total_count: xxx
        task:[
        {'task_id':xxx
        'url':xxx
        'status':xxx
        'percent':xxx},
        {.....},......
        ]

        }

    :return:
    """
    st = time.time()
    try:
        openapi_flag = request.headers.get('X-Forwarded-Host').strip() if request.headers.get('X-Forwarded-Host') else ''

        logger.debug('query_task_api data: %s|| remote_addr: %s|| openapi_flag: %s' % (request.data, request.remote_addr, openapi_flag))
        json_str = json.loads(request.data)
        username = request.args.get('cloud_client_name') if request.args.get('cloud_client_name') else json_str.get("username", "")
        logger.debug("query_task_api username: %s" % username)

        tasks_list = json_str.get('tasks', [])
        status_list = json_str.get('status', [])

        if openapi_flag != 'openapi.chinacache.com':
            ticket = authentication.verify(username, json_str.get("password", ""), request.remote_addr)
            count, tasks = get_tasks_from_api(ticket, tasks_list, status_list)
        else:
            count, tasks = get_tasks_from_api({'parent': username}, tasks_list, status_list)

        # get the preload result of webluker
        find_result_web = query_task_forward_from_webluker(username, tasks_list, status_list)
        logger.debug("query_task_api find_result_web: %s" % find_result_web)


        find_result = {}
        find_result['totalCount'] = count
        find_result['tasks'] = []
        for task in tasks:
            info = percent_filesize(task.get('_id'), task.get('status'))
            find_result['tasks'].append(
                {'task_id': task.get('task_id'), 'url': task.get('url'), 'status': task.get('status'),
                 'percent': info.get('percent')})
        find_result['tasks'] = process_webluker_cc(find_result['tasks'], find_result_web)
        # find_result['totalCount'] += find_result_web['totalCount']
        # find_result['tasks'].extend(find_result_web['tasks'])
        find_result['totalCount'] = len(find_result.get('tasks'))
        logger.debug("query_task_api[%s -- Taking seconds]: %s" % ('/content/preload/search', (time.time()-st)))
        return jsonify(find_result)

    except Forbidden as e:
        return jsonify({"code": 403, "msg": e.description})
    except HTTPException as e:
        if e.description in ['NO_USER_EXISTS', 'WRONG_PASSWORD', 'CONTRACT_EXPIRED', 'INPUT_ERROR']:
            return jsonify({"code": 403, "msg": e.description})
        else:
            raise e
    except InputError:
        return jsonify({"code": 500, "msg": "The schema of request is error."})


@preload.route('/internal/preload/search_w', methods=['GET', 'POST'])
def query_task_api_w():
    """
    API任务状态查询接口
    :param data:
    {'username':'verycd',
         'password':'verycd@cc',
         'tasks': '[1,2,3]',
         # 'created_time':'2014-11-14 14:00:00',
         'status':[TIMER,PROGRESS,INVALID,FINISHED,FAILED]
        }
    return:
        {
        total_count: xxx
        task:[
        {'task_id':xxx
        'url':xxx
        'status':xxx
        'percent':xxx},
        {.....},......
        ]

        }

    :return:
    """
    try:
        logger.debug('query_task_api data:%s remote_addr:%s' %
                     (request.data, request.remote_addr))
        json_str = json.loads(request.data)
        username = json_str.get("username", "")
        ticket = authentication.internal_verify(
            username, request.remote_addr)
        tasks_list = json_str.get('tasks', [])
        status_list = json_str.get('status', [])

        # try:
        #     forward_users = config.get('task_forward', 'usernames')
        # except:
        #     forward_users = []
        # if username in eval(forward_users):
        # find_result_web = query_task_forward(username, tasks_list, status_list)
        # return jsonify(find_result)

        count, tasks = get_tasks_from_api_w(ticket, tasks_list, status_list)

        find_result = {}
        find_result['totalCount'] = count
        find_result['tasks'] = []

        for task in tasks:
            info = percent_filesize(task.get('_id'), task.get('status'))
            find_result['tasks'].append(
                {'task_id': task.get('task_id'), 'url': task.get('url'), 'status': task.get('status'),
                 'percent': info.get('percent')})
        # find_result['totalCount'] += find_result_web['totalCount']
        # find_result['tasks'].extend(find_result_web['tasks'])
        return jsonify(find_result)
    except Forbidden as e:
        return jsonify({"code": 403, "msg": e.description})
    except InputError:
        return jsonify({"code": 500, "msg": "The schema of request is error."})


@preload.route('/internal/preload/retry', methods=['GET', 'POST'])
def retry_task():
    logger.debug('retry_task data: %s|| remote_addr: %s' % (request.data, request.remote_addr))
    username, task_list = get_tasks(request)
    preload_worker.execute_retry_task.delay(username, task_list)
    return jsonify({"code": 0, "msg": "ok"})


@preload.route('/internal/preload/channel/<channel_code>/time/<query_time>', methods=['GET', 'POST'])
def query_billing(channel_code, query_time):
    """
    计费调用接口，同步昨日数据
    参数：
    channel_code 12345
    query_time 2013-05-02
    * 参数说明：
    + channel_code : 频道ID
    + query_time : 查询时间，格式(yyyy-MM-dd)
    :param channel_code:
    :param query_time:
    :return:
    """
    return jsonify(get_billing(channel_code, datetime.strptime(query_time, "%Y-%m-%d")))


@preload.route('/preload_Api/preload_main.php', methods=['GET', 'POST'])
def receiver_preload():
    try:
        logger.debug('preload_main  op:%s context:%s remote_addr:%s' %
                     (request.args.get('op', ''), request.args.get('context', ''), request.remote_addr))
        if request.args.get('op', '') == 'preload':
            queue.put_json2("preload_task", get_context(
                request.args.get('context', ''), request.remote_addr))
        elif request.args.get('op', '') == 'cancel':
            username, task_list = get_cancel_context(
                request.args.get('context', ''))
            preload_worker.preload_cancel.delay(username, task_list)
        return doResponse('<result>SUCESS</result><detail>SUCESS</detail>')
    except InputError as ie:
        return doResponse('<result>FAILURE</result><detail>%s</detail>' % ie.__str__())


class ChannelError(Exception):

    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class OverloadError(Exception):

    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class NoDevicesError(Exception):

    def __init__(self, value):
        self.value = value

    def __str__(self):
        if isinstance(self.value, str):
            return self.value
        return repr(self.value)


class NoChannelError(Exception):

    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


@preload.route('/content/preload', methods=['GET', 'POST'])
def receiver_new_preload():
    '''
    预加载API接口，与portal进行验证,并将任务放入rabbitmq中，preload_task,
    再由routerd处理存入的内容
    Parameters:
         :
    Returns:
    '''
    st = time.time()
    try:
        logger.debug('receiver_new_preload body: %s|| remote_addr: %s' % (request.data, request.remote_addr, ))
        data = json.loads(request.data)
        # username = data.get("username", "")
        ticket = authentication.verify(
            data.get("username", ""), data.get("password", ""), request.remote_addr)

        # try:
        #     forward_users = config.get('task_forward', 'usernames')
        # except:
        #     forward_users = []
        # if username in eval(forward_users):
        #     res = task_forward(data)
        #     return jsonify({'code':0, 'msg':'ok'})

        message = {}
        task_list, invalids = get_preload_new(request, ticket, type='API')
        logger.debug("receiver_new_preload task_list:%s" % task_list)
        if task_list:
            logger.debug("receiver_new_preload[%s -- Taking seconds before put_json2]: %s" % ('/content/preload', (time.time()-st)))
            queue.put_json2("preload_task", task_list)
            logger.debug("receiver_new_preload[%s -- Taking seconds after put_json2]: %s" % ('/content/preload', (time.time()-st)))
            if invalids:
                message['invalids'] = invalids
                message['code'] = 201
            else:
                message['code'] = 0
                message['msg'] = 'ok'
        else:
            message['code'] = 0
            message['msg'] = 'ok'
        return jsonify(message)
    except ChannelError as ex:
        return jsonify({"code": 405, "msg": ex.__str__()})
    except OverloadError as ex:
        return jsonify({"code": 406, "msg": ex.__str__()})
    except InputError as e:
        return jsonify({"code": e.__code__(), "msg": e.__str__()})
    except HTTPException as ex:
        if ex.description in ['NO_USER_EXISTS', 'WRONG_PASSWORD', 'CONTRACT_EXPIRED', 'INPUT_ERROR']:
            return jsonify({"code": 403, "msg": ex.description})
        else:
            raise ex
    except Exception:
        logger.debug(e.__str__())
        logger.debug('exception error:%s' % traceback.format_exc())
        return jsonify({"code": 500, "msg": "The schema of request is error."})


@preload.route('/content/cancel', methods=['GET', 'POST'])
def receiver_new_cancel():
    try:
        logger.debug('body:%s remote_addr:%s' %
                     (request.data, request.remote_addr))
        data = json.loads(request.data)
        authentication.verify(
            data.get("username", ""), data.get("password", ""), request.remote_addr)
        username, task_list = get_tasks(request)
        preload_worker.preload_cancel.delay(username, task_list)
        return jsonify({"code": 0, "msg": "ok"})
    except InputError as e:
        return jsonify({"code": e.__code__(), "msg": e.__str__()})
    except Forbidden as e:
        return jsonify({"code": 403, "msg": e.description})
    except Exception:
        if e.description in ['NO_USER_EXISTS', 'WRONG_PASSWORD', 'CONTRACT_EXPIRED', 'INPUT_ERROR']:
            return jsonify({"code": 403, "msg": e.description})
        return jsonify({"code": 500, "msg": "The schema of request is error."})


@preload.route('/content/preload_report', methods=['GET', 'POST'])
def preload_report():
    """
    接收预加载任务结果

    :return:
    """
    st = time.time()
    try:
        logger.debug('preload_report data:%s remote_addr:%s' %
                     (request.data, request.remote_addr))
        send_type = config.get("preload_send", "send_type")
        if send_type == 'xml':
            report_body = get_fc_report(request.data)
        else:
            report_body = get_fc_report_json(request.data)
        # report_body = load_task(request.data)
        if report_body['lvs_address']:
            report_body['remote_addr'] = report_body['lvs_address']
        else:
            report_body['remote_addr'] = request.remote_addr
        logger.debug('preload_report report_body is %s' % (report_body))
        if send_type == 'xml':
            preload_worker.save_fc_report.delay(report_body)
        else:
            logger.debug('preload_report[/content/preload_report -- Taking seconds before save_fc_report.delay]: %s' % (time.time()-st))
            preload_worker_new.save_fc_report.delay(report_body)
            logger.debug('preload_report[/content/preload_report -- Taking seconds after save_fc_report.delay]: %s' % (time.time()-st))
        logger.debug('preload_report delay end')
        return 'ok'
    except Exception:
        logger.debug('preload_report error: %s|| data:%s|| remote_addr:%s' %
                     (traceback.format_exc(), request.data, request.remote_addr))
        return 'error', 500


@preload.route('/preload/error_task', methods=['GET', 'POST'])
def get_error_task():
    """
    FC获取失败信息接口,preload是定时任务

    :return:
    """
    try:
        logger.debug('get error_task  remote_addr:%s' % request.remote_addr)
        send_type = config.get("preload_send", "send_type")
        task_send = ''
        if send_type == 'xml':
            send_task, preload_task = preload_worker.get_error_tasks(
                request.remote_addr)
            if send_task + preload_task:
                logger.debug('get error_task  remote_addr:%s grap %s tasks' %
                             (request.remote_addr, len(send_task + preload_task)))
                preload_worker.reset_error_tasks.delay(
                    send_task, preload_task, request.remote_addr)
                for task in send_task + preload_task:
                    task_send += task.get('command') + '\n'
            logger.debug('get error_task  send:%s' % task_send)
            return task_send
        else:
            preload_task = preload_worker_new.get_error_tasks(request.remote_addr)
            preload_worker_new.reset_error_tasks.delay(preload_task)
            for t in preload_task:
                task_send += t.get('command') + '\n'
            return task_send

    except Exception:
        return doResponse('<result>FAILURE</result><detail>%s</detail>' % e.__str__())


@preload.route('/content/snda_preload', methods=['GET', 'POST'])
def receiver_snda_preload():
    try:
        logger.debug('body:%s remote_addr:%s' %
                     (request.form, request.remote_addr))

        task_list, op, username = get_snda_preload(request.form, request.remote_addr)
        if op == 'preload':
            queue.put_json2("preload_task", task_list)
        elif op == 'cancel':
            preload_worker.preload_cancel.delay(username,
                                                [task.get('task_id') for task in task_list])
        return jsonify({"success": True, "message": "ok"})
    except InputError as e:
        return jsonify({"success": False, "message": e.__str__()})
    except Forbidden as e:
        return jsonify({"success": False, "message": e.description})
    except Exception:
        return jsonify({"success": False, "message": "The schema of request is error."})


def verify_md5(user_id):
    user = query_db.preload_user.find_one({"user_id": user_id})
    if not user:
        logger.debug('NO_USER_EXISTS user_id:%s...' % user_id)
        raise InputError(403, "NO_USER_EXISTS")
    return user.get("name")


def verify_snda(username, password, time):
    KEY = username + 'qetsfh!3' + time
    md5 = hashlib.md5(KEY.encode('utf-8'))
    if password != md5.hexdigest():
        logger.debug(
            'verify_snda WRONG_PASSWORD username:%s  time:%s password:%s md5:%s ' %
            (username, time, 'qetsfh!3', md5.hexdigest()))
        raise InputError(403, "WRONG_PASSWORD")


def get_context(context, remote_addr):
    try:
        root = minidom.parseString(context).documentElement
        task_list = []
        user_id = preload_worker.get_nodevalue(
            preload_worker.get_xmlnode(root, 'cust_id')[0])
        username = verify_md5(user_id)
        for task in preload_worker.get_xmlnode(root, 'task'):
            isValid, is_multilayer, channel_code, ignore_case = rcmsapi.isValidUrl(
                username, preload_worker.get_firstChild(task, 'publish_url'))
            task_list.append(
                {'task_id': preload_worker.get_attrvalue(task, 'id'), 'username': username, 'user_id': user_id,
                 'channel_code': channel_code, 'status': 'PROGRESS' if isValid else 'INVALID',
                 'url': preload_worker.get_firstChild(task, 'publish_url'),
                 'get_url_speed': preload_worker.get_firstChild(task, 'speed') if preload_worker.get_firstChild(
                     task, 'speed') else "", 'created_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                 'md5': preload_worker.get_firstChild(task, 'md5'),
                 'check_type': 'MD5' if preload_worker.get_firstChild(task, 'md5') else 'BASIC',
                 'action': 'refresh,preload' if preload_worker.get_firstChild(task, 'whether_refresh') else 'preload',
                 'is_multilayer': is_multilayer, 'remote_addr': remote_addr})
        return task_list
    except:
        raise InputError(500, "The schema of request is error.")


def get_preload(request, ticket={}, type='other'):
    '''
        将request信息转为JSON，传入RCMS进行验证
    '''
    message = json.loads(request.data)
    message['username'] = request.args.get('cloud_client_name') if request.args.get('cloud_client_name') else message.get('username')

    isValidStartTime(message.get("startTime"))

    compressed = message.get('compressed', False)
    if isinstance(compressed, str):
        compressed = True if compressed.upper() == 'TRUE' else False
    task_list = []
    logger.debug('get_preload message: %s' % message)

    # rubin add
    urls_cc, urls_web = get_urls_preload(message.get('username'), message.get('tasks'))
    if type == 'portal_webluker':
        urls_cc = message.get('tasks')
        urls_web = []

    if urls_web:
        task_forward.delay(urls_web, message.get('username'))
    if urls_cc:
        urls_cc_temp = [url.get('url') for url in urls_cc]
        for task in message.get('tasks'):
            if task.get('url') not in urls_cc_temp:
                continue
            _url = task.get('url', '')
            if _url and (message.get("username", "") not in ['qq']):
                if not message.get('is_repeated') and had_preload_url(message.get("username", ""), _url):
                    continue

            isValid, is_multilayer, channel_code, ignore_case = rcmsapi.isValidUrl(message.get("username"), task.get('url', ''))
            logger.info('get_preload isValid: %s|| is_multilayer: %s|| channel_code: %s|| ignore_case: %s' % (isValid, is_multilayer, channel_code, ignore_case))
            task = {
                'header_list': [d for d in message.get("header_list")] if message.get('header_list', []) else [],
                'md5': task.get('md5', ''), 'task_id': str(task.get('id')), 'username': message.get("username", ""),
                'user_id': message.get("user_id", ''), 'channel_code': channel_code,
                'status': 'PROGRESS' if isValid else 'INVALID', 'parent': message.get("username", ""),
                'url': task.get('url'), 'get_url_speed': message.get("speed") if message.get("speed") else "",
                'limit_speed': message.get('speed') if message.get('speed') else "",
                'created_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'created_time_timestamp': time.mktime(datetime.now().timetuple()),
                'check_type': message.get("validationType"), 'start_time': message.get("startTime", ""),
                'action': 'refresh,preload', 'is_multilayer': is_multilayer, 'priority': message.get("priority", 0),
                'nest_track_level': message.get("nest_track_level", 0), 'type': type,
                'preload_address': message.get('preload_address', '127.0.0.1:80'),
                'compressed': compressed, 'remote_addr': request.remote_ip if hasattr(request, 'remote_ip') else request.remote_addr,
                'recev_host': RECEIVER_HOST, 'is_avoid': message.get('is_avoid')}
            if task.get("start_time") and task.get('status') == 'PROGRESS':
                task['status'] = 'TIMER'
            # for avoid period tasks
            is_avoid, avoid_period_length = get_avoid_channel(task.get('channel_code'))
            # logger.debug('get_preload is_avoid: %s, avoid_period_length: %s' % (is_avoid, avoid_period_length))
            if is_avoid:
                task['status'] = 'TIMER'
                task['avoid_period_length'] = avoid_period_length
                task['start_time'] = datetime.strftime(
                    (datetime.now() + timedelta(seconds=avoid_period_length)), "%Y-%m-%d %H:%M:%S")
            task_list.append(task)

    logger.debug('get_preload task_list: %s' % task_list)
    return task_list


def generate_preload_data(request, devs_all, channel_code, request_type='customized_devices'):
    '''
    customized devices list
    '''
    try:
        logger.info('generate_preload_data message: %s' % request.data)
        data = json.loads(request.data)
        username = data.get("username", "")
        compressed = True if data.get('compressed') in ['true', 'True', True] else False
        user_overload_max = get_preload_overload_cache(username)
        task_list = []
        devices = data.get('device_list', '')
        if not len(devices):
            raise NoDevicesError("NO_DEVICES")
        error_msg = ''
        try:
            socket.inet_aton(devices[0])
            f_name = 'host'
        except Exception:
            f_name = 'name'
            error_msg = traceback.format_exc()
        devices = [d_all for d_all in devs_all for d in devices if d == d_all.get(f_name)]
        logger.info('generate_preload_data len(devices): %s' % (len(devices), ))
        if not devices and error_msg:
            logger.info('generate_preload_data error_msg: %s' % (error_msg, ))

        is_multilayer = False
        for dev in devices:
            if dev.get('firstLayer') == True:
                is_multilayer = True

        tasks = data.get('tasks', {})
        for task in tasks:
            channel_name = get_channelname_from_url(task.get('url', ''))
            if not channel_name:
                raise NoChannelError('NO CHANNEL')
            elif set_preload_overload(username) > int(user_overload_max):
                raise OverloadError("PRELOAD_URL_OVERLOAD_PER_HOUR")

            url_id = ObjectId()
            task = {
                'header_list': [d for d in data.get("header_list")] if data.get('header_list', []) else [],
                'md5': task.get('md5', ''), 'task_id': str(task.get('id')), 'username': username,
                'user_id': data.get("user_id", ''), 'channel_code': channel_code, '_id': str(url_id),
                'status': 'PROGRESS', 'url': task.get('url'), 'parent': username,
                'get_url_speed': data.get("speed") if data.get("speed") else "",
                'limit_speed': data.get('speed') if data.get('speed') else "",
                'created_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'created_time_timestamp': time.mktime(datetime.now().timetuple()),
                'check_type': data.get("validationType"), 'start_time': data.get("startTime", ""),
                'action': 'refresh,preload', 'is_multilayer': is_multilayer, 'priority': data.get("priority", 0),
                'nest_track_level': data.get("nest_track_level", 0), 'type': request_type,
                'preload_address': data.get('preload_address', '127.0.0.1:80'),
                'compressed': compressed,
                'remote_addr': request.remote_addr, 'devices': devices, 'recev_host': RECEIVER_HOST}
            if task.get("start_time") and task.get('status') == 'PROGRESS':
                task['status'] = 'TIMER'
            task_list.append(task)
        return task_list
    except Exception:
        logger.debug('generate_preload_data[error]: %s' % (traceback.format_exc(), ))
        raise


def getSign(data, key):
    dataList = list(data.keys())
    dataList.sort()
    sList = []
    for d in dataList:
        sList.append(d + '=' + str(data[d]))
    s = '&'.join(sList)
    s1 = s + key
    s2 = s1.encode('utf-8')
    m = hashlib.md5(s2)
    m.digest()
    sign = m.hexdigest()
    return sign


def get_preload_devices(request, ticket={}, type='webluker'):
    '''
        就是一个直接指定设备下发任务的测试接口,2018-01-19下午把md5相关的字段采集补全!
    '''
    isValidStartTime(request.form.get("startTime"))

    parent = request.form.get("parent", ticket.get("parent")) if (request.form.get(
        'isSub', False) or ticket.get('isSub', False)) else request.form.get('username', '')
    compressed = request.form.get('compressed', False)
    username = request.form.get("username", "")
    logger.debug('get_preload_devices username:%s' % request.form.get('username'))
    if isinstance(compressed, str):
        compressed = True if compressed.upper() == 'TRUE' else False
    user_overload_max = get_preload_overload_cache(username)
    task_list = []
    invalids = []

    task_utf = request.form.get('tasks', {}).encode("utf-8")
    logger.debug('get_preload_devices task_utf: %s' % task_utf)
    device_utf = request.form.get('devices', '').encode("utf-8")
    if not device_utf:
        raise NoDevicesError("NO_DEVICES")
    else:
        devices = load_task(device_utf)

    # filter devices
    logger.debug('get_preload_devices[beforeFiltering] len(devices): %s' % len(devices))
    devices = [d for d in devices if d.get('status') == 'OPEN']
    if not devices:
        raise NoDevicesError('No devices after filtering.')
    logger.debug('get_preload_devices[afterFiltering] len(devices): %s' % len(devices))

    for task in load_task(task_utf):
        channel_name = get_channelname_from_url(task.get('url', ''))
        if not channel_name:
            # not_config.append(task.get('url', ''))
            raise NoChannelError('NO CHANNEL')
        elif set_preload_overload(username) > int(user_overload_max):
            raise OverloadError("PRELOAD_URL_OVERLOAD_PER_HOUR")

        url_id = ObjectId()
        is_multilayer = False
        for dev in devices:
            if dev.get('firstLayer'):
                is_multilayer = True
                break

        task = {
            'md5': task.get('md5', ''), 'task_id': str(task.get('id')), 'username': request.form.get("username", ""),
            'user_id': request.form.get("user_id", ''), 'channel_code': 'webluker', '_id': str(url_id),
            'status': 'PROGRESS', 'parent': parent, 'url': task.get('url'),
            'get_url_speed': request.form.get("speed") if request.form.get("speed") else "",
            'limit_speed': request.form.get('speed') if request.form.get('speed') else "",
            'created_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'created_time_timestamp': time.mktime(datetime.now().timetuple()),
            'check_type': request.form.get("validationType"), 'start_time': request.form.get("startTime", ""),
            'action': 'refresh,preload', 'is_multilayer': is_multilayer, 'priority': request.form.get("priority", 0),
            'nest_track_level': request.form.get("nest_track_level", 0), 'type': type,
            'preload_address': request.form.get('preload_address', '127.0.0.1:80'),
            'compressed': compressed,
            'remote_addr': request.remote_addr, 'devices': devices, 'recev_host': RECEIVER_HOST}
        if task.get("start_time") and task.get('status') == 'PROGRESS':
            task['status'] = 'TIMER'
        task_list.append(task)
    logger.debug('get_preload_devices task_list: %s' % (task_list, ))
    return task_list, invalids


def get_preload_new(request, ticket={}, type='other'):
    '''
        将request信息转为JSON，传入RCMS进行验证
    Parameters:
        request :
        ticket :
    Returns:
    '''
    message = json.loads(request.data)

    isValidStartTime(message.get("startTime"))

    parent = message.get("parent", ticket.get("parent")) if (
        message.get('isSub', False) or ticket.get('isSub', False)) else message.get('username', '')
    compressed = message.get('compressed', False)
    username = message.get("username", "")

    if isinstance(compressed, str):
        compressed = True if compressed.upper() == 'TRUE' else False
    user_overload_max = get_preload_overload_cache(username)
    task_list = []
    invalids = []

    urls_cc, urls_web = get_urls_preload(message.get('username'), message.get('tasks'))
    if type == 'portal_webluker':
        urls_cc = message.get('tasks')
        urls_web = []

    if urls_web:
        task_forward.delay(urls_web, message.get('username'))
    if urls_cc:
        urls_cc_temp = [url.get('url') for url in urls_cc]
        for task in message.get('tasks'):
            if task.get('url') not in urls_cc_temp:
                continue
            url_list = []
            if task.get('url', '')[0] == '*':
                channel_name = task.get('url', '').split('/', 1)[0][1:]
                unchannel_name = task.get('url', '').split('/', 1)[1]
                username_key = redisutil.rediscache.CHANNELS_PORTAL_PREFIX % username
                logger.info("username_key::::%s" % username_key)
                logger.info("channel_name::::%s" % channel_name)
                # key='cp_by_111-test
                all_username_channel = redisutil.portal_cache.hgetall(username_key)
                logger.debug("all_username_channel::::%s" % all_username_channel)
                if all_username_channel:
                    for key, value in list(all_username_channel.items()):

                        if key.endswith(channel_name):
                            logger.debug("key:::%s" % key)
                            had_config = PRELOAD_DEVS.exists(key)
                            if had_config:
                                logger.debug("key:::%s" % key)
                                url_list.append(key + '/' + unchannel_name)
                                # url_list.append(task.get('url', ''))
                                # if set_preload_overload(username) > int(user_overload_max):
                                #    raise OverloadError("PRELOAD_URL_OVERLOAD_PER_HOUR")
                else:
                    url_search = "https://portal-api.chinacache.com:444/api/internal/getBusinessInfo.do?allCustomerBusinesses=true&username=" + \
                        str(username)
                    user = json.loads(urllib.request.urlopen(url_search).read())
                    businesses = user.get('businesses', [])
                    for business in businesses:
                        if not business.get('productCode', ''):
                            continue
                        for channel in business.get('channels', []):
                            if channel['channelName'].endswith(channel_name):
                                had_config = PRELOAD_DEVS.exists(channel['channelName'])
                                if had_config:
                                    url_list.append(channel['channelName'] + '/' + unchannel_name)
                if len(url_list):
                    url_list.append(task.get('url', ''))

                if set_preload_overload(username) > int(user_overload_max):
                    raise OverloadError("PRELOAD_URL_OVERLOAD_PER_HOUR")
            else:
                channel_name = get_channelname_from_url(task.get('url', ''))
                had_config = PRELOAD_DEVS.exists(channel_name)
                if not had_config:
                    # not_config.append(task.get('url', ''))
                    raise ChannelError('%s not config channel' % channel_name)
                else:
                    if set_preload_overload(username) > int(user_overload_max):
                        raise OverloadError("PRELOAD_URL_OVERLOAD_PER_HOUR")
                url_list.append(task.get('url', ''))
            logger.debug("url_list::::%s" % url_list)
            if len(url_list):
                for line in url_list:
                    url_id = ObjectId()
                    if message.get('isSub', False) or ticket.get('isSub', False):
                        isValid, is_multilayer, channel_code, ignore_case = rcmsapi.isValidUrlByPortal(
                            message.get("username"), parent, line)
                    else:
                        isValid, is_multilayer, channel_code, ignore_case = rcmsapi.isValidUrl(
                            message.get("username"), line)
                    if not isValid:
                        logger.debug('%s not in %s' % (channel_name, message.get('username', '')))
                        invalids.append(str(url_id))
                    task = {
                        'header_list': [d for d in message.get("header_list")] if message.get('header_list', []) else None,
                        'md5': task.get('md5', ''), 'task_id': str(task.get('id')),
                        'username': message.get("username", ""),
                        'user_id': message.get("user_id", ''), 'channel_code': channel_code, '_id': str(url_id),
                        'status': 'PROGRESS' if isValid else 'INVALID', 'parent': parent,
                        'url': line, 'get_url_speed': message.get("speed") if message.get("speed") else "",
                        'limit_speed': message.get('speed') if message.get('speed') else "",
                        'created_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'created_time_timestamp': time.mktime(datetime.now().timetuple()),
                        'check_type': message.get("validationType"), 'start_time': message.get("startTime", ""),
                        'action': 'refresh,preload', 'is_multilayer': is_multilayer,
                        'priority': message.get("priority", 0),
                        'nest_track_level': message.get("nest_track_level", 0), 'type': type,
                        'preload_address': message.get('preload_address', '127.0.0.1:80'),
                        'compressed': compressed,
                        'remote_addr': request.remote_addr, 'recev_host': RECEIVER_HOST
                    }
                    if task.get("start_time") and task.get('status') == 'PROGRESS':
                        task['status'] = 'TIMER'
                    task_list.append(task)

    logger.debug(task_list)
    return task_list, invalids


def get_snda_preload(request, addr):
    try:
        username = request.get("username", "")
        password = request.get("password", "")
        time = request.get("time", "")
        op = request.get("op", "")
        content = json.loads(request.get("content", "{}"))
        verify_snda(username, password, time)
        task_list = []
        if op == 'preload':
            for task in content:
                isValid, is_multilayer, channel_code, ignore_case = rcmsapi.isValidUrl(
                    username, task.get('publish_url', ''))
                task = {
                    'md5': task.get('md5', ''), 'task_id': task.get('task_id'), 'username': username, 'user_id': '',
                    'channel_code': channel_code, 'status': 'PROGRESS' if isValid else 'INVALID',
                    'url': task.get('publish_url'), 'parent': username,
                    'get_url_speed': task.get("speed") if task.get("speed") else "",
                    'created_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'check_type': 'MD5' if task.get('md5') != '' else 'BASIC', 'start_time': "",
                    'action': 'refresh,preload' if task.get('whether_refresh') else 'preload',
                    'is_multilayer': is_multilayer, 'priority': 0, 'nest_track_level': 0,
                    'preload_address': '127.0.0.1:80', 'type': 'snda',
                    'remote_addr': addr}
                task_list.append(task)
        elif op == 'cancel':
            for task in content:
                task_list.append(task.get('task_id'))
        return task_list, op, username
    except Exception:
        logger.debug(e)
        raise InputError(500, "The schema of request is error.")


def doResponse(nodeStr):
    responseMessage = parseString('<ccsc>%s</ccsc>' % nodeStr)
    response = make_response(responseMessage.toxml('utf-8'))
    logger.debug('ntese response :%s' % responseMessage.toxml('utf-8'))
    response.headers['Content-Type'] = 'text/xml;charset=UTF-8'
    return response


def get_cancel_context(context):
    try:
        root = minidom.parseString(context).documentElement
        task_list = []
        user_id = preload_worker.get_nodevalue(
            preload_worker.get_xmlnode(root, 'cust_id')[0])
        password = preload_worker.get_nodevalue(
            preload_worker.get_xmlnode(root, 'passwd')[0])
        user_key = preload_worker.get_attrvalue(
            preload_worker.get_xmlnode(root, 'task')[0], 'id')
        username = verify_md5(user_id, password, user_key)
        for task in preload_worker.get_xmlnode(root, 'task'):
            task_list.append(preload_worker.get_attrvalue(task, 'id'))
        return username, task_list
    except:
        raise InputError(500, "The schema of request is error.")


def check_report_value(key, data):
    """
    验证FC发送的数据
    :param key:
    :param data:
    :return:
    """
    if key in ["content_length", "download_mean_rate"]:
        try:
            data = float(data)
        except:
            data = 0
    # elif key in ["last_modified", "response_time"]:
    #     GMT_FORMAT = '%a, %d %b %Y %H:%M:%S GMT'
    #     try:
    #         data = datetime.strptime(data, GMT_FORMAT)
    #     except:
    #         data = datetime.strptime('1900-01-01', '%Y-%m-%d')
    else:
        data = data

    return data


def get_fc_report(request_data):
    """
     解析XML文件
    :param request_data:
    :return: :raise InputError:
    """
    try:
        root = minidom.parseString(request_data).documentElement
        try:
            http_status_code_value = preload_worker.get_nodevalue(
                preload_worker.get_xmlnode(root, 'http_status_code')[0])
        except Exception:
            logger.debug("http_status_code %s" % traceback.format_exc())
            http_status_code_value = 'None'
        logger.debug("http_status_code_value %s" % http_status_code_value)
        try:
            http_status_value = preload_worker.get_nodevalue(preload_worker.get_xmlnode(root, 'http_status')[0])
        except Exception:
            logger.debug("http_status_code %s" % traceback.format_exc())
            http_status_value = 'None'
        if http_status_code_value == 'None':
            http_status_code = http_status_value
        else:
            http_status_code = http_status_code_value
        preload_result = {
            'sessionid': preload_worker.get_attrvalue(root, 'sessionid'),
            'preload_status': int(preload_worker.get_nodevalue(preload_worker.get_xmlnode(root, 'preload_status')[0])),
            'url_id': preload_worker.get_nodevalue(preload_worker.get_xmlnode(root, 'url_id')[0]),
            'download_mean_rate': check_report_value('download_mean_rate', preload_worker.get_nodevalue(
                preload_worker.get_xmlnode(root, 'download_mean_rate')[0])),
            'cache_status': preload_worker.get_nodevalue(preload_worker.get_xmlnode(root, 'cache_status')[0]),
            'http_status_code': http_status_code,
            'response_time': check_report_value('response_time', preload_worker.get_nodevalue(
                preload_worker.get_xmlnode(root, 'date')[0])),
            'last_modified': check_report_value('last_modified', preload_worker.get_nodevalue(
                preload_worker.get_xmlnode(root, 'last_modified')[0])),
            'content_length': check_report_value('content_length', preload_worker.get_nodevalue(
                preload_worker.get_xmlnode(root, 'content_length')[0])),
            'check_type': preload_worker.get_attrvalue(preload_worker.get_xmlnode(root, 'check_result')[0], 'type'),
            'check_result': preload_worker.get_firstChild(root, 'check_result'),
            'finish_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'lvs_address':  preload_worker.get_lvs_value(root)
        }
        return preload_result
    except Exception:
        logger.debug("get_fc_report error %s" % e)
        raise InputError(500, "The schema of request is error.")


def get_fc_report_json(request_data):
    '''
    解析json
    '''
    try:
        request_obj = json.loads(request_data)
        preload_result = {}
        preload_result['sessionid'] = request_obj.get('sessionid', '')
        preload_result['preload_status'] = int(request_obj.get('preload_status', 0))
        preload_result['url_id'] = request_obj.get('url_id', '')
        preload_result['download_mean_rate'] = request_obj.get('download_mean_rate', '')
        preload_result['cache_status'] = request_obj.get('cache_status', '')
        preload_result['http_status_code'] = request_obj.get('http_status_code', request_obj.get('http_status', ''))
        preload_result['response_time'] = request_obj.get('response_time', '')
        preload_result['last_modified'] = request_obj.get('last_modified', '')
        preload_result['content_length'] = request_obj.get('content_length', '')
        preload_result['check_type'] = request_obj.get('check_type', '')
        preload_result['check_result'] = request_obj.get('check_result', '')
        preload_result['lvs_address'] = request_obj.get('lvs_address', '')
        preload_result['finish_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        preload_result['final_status'] = request_obj.get('status', '')
        return preload_result

    except Exception:
        logger.debug("get_fc_report json error %s" % traceback.format_exc())
        raise InputError(500, "The schema of request is error.")


def get_query_task(request_data):
    try:
        message = json.loads(request_data)
        condition = {}

        message['username'] = request.args.get('cloud_client_name') if request.args.get('cloud_client_name') else message.get('username')

        if message.get('isSub', False):
            preload_worker_new.set_value(message, condition, ['username', 'url', 'status'])
        else:
            message['parent'] = message.get('parent', message.get('username'))
            preload_worker_new.set_value(message, condition, ['parent', 'url', 'status'])
        if message.get('startTime') and message.get('startTime').get('startTime') or message.get(
                'startTime') and message.get('startTime').get('endTime'):
            condition['created_time'] = {}
            if message.get('startTime').get('startTime'):
                condition['created_time']['$gte'] = datetime.strptime(
                    message.get('startTime').get('startTime'), "%Y-%m-%d %H:%M:%S")
            if message.get('startTime').get('endTime'):
                condition['created_time']['$lte'] = datetime.strptime(
                    message.get('startTime').get('endTime'), "%Y-%m-%d %H:%M:%S")
        if message.get('finishTime') and message.get('finishTime').get('startTime') or message.get(
                'finishTime') and message.get('finishTime').get('endTime'):
            condition['finish_time'] = {}
            if message.get('finishTime').get('startTime'):
                condition['finish_time']['$gte'] = datetime.strptime(
                    message.get('finishTime').get('startTime'), "%Y-%m-%d %H:%M:%S")
            if message.get('finishTime').get('endTime'):
                condition['finish_time']['$lte'] = datetime.strptime(
                    message.get('finishTime').get('endTime'), "%Y-%m-%d %H:%M:%S")
        logger.debug("get_query_task condition %s" % condition)
        count = s1_db.preload_url.find(condition).count()
        if message.get('startNo') < message.get('endNo'):
            tasks = s1_db.preload_url.find(condition).sort("created_time", -1).skip(
                message.get('startNo') - 1).limit(message.get('endNo') - message.get('startNo'))
        else:
            tasks = s1_db.preload_url.find(
                condition).sort("created_time", -1).limit(20)
        return count, tasks
    except Exception:
        logger.error('get_query_task [error]: %s' % (traceback.format_exc()))
        raise InputError(500, "get_query_task The schema of request is error.")


def get_tasks(request):
    try:
        message = json.loads(request.data)
        task_list = []
        for task in message.get('tasks'):
            task_list.append(task.get('id'))
        return message.get('username', ''), task_list
    except Exception:
        logger.debug('get_tasks [error]: {}'.format(traceback.format_exc()))
        raise InputError(500, "The schema of request is error.")


def get_billing(channel_code, query_day):
    """
    查询 preload_url，统计计费所需数据
    :param channel_code: 频道code
    :param query_day: 查询的日期
    :return:
    """
    ret = {}
    for i in range(24):
        begin = query_day + timedelta(hours=i)
        end = begin + timedelta(hours=1)
        count = 0
        file_size = 0
        for url in s1_db.preload_url.find(
                {"channel_code": channel_code, "created_time": {"$gte": begin, "$lte": end}}):
            count += 1
            # if url.get("status") == "FINISHED":#执行中的也计算文件大小
            info = percent_filesize(url.get('_id'), url.get('status'))
            file_size += info.get("file_size")
        ret.setdefault(i, {"count": int(count), "filesize": int(file_size)})
    return ret


def conversion(file_size):
    if file_size == 0:
        size = "----"
    elif 0 < file_size < 1024:
        size = str(file_size) + " (Byte)"
    elif file_size < (1024 * 1024):
        size = str(round(file_size / 1024, 2)) + " (K)"
    elif file_size < (1024 * 1024 * 1024):
        size = str(round(file_size / 1024 / 1024, 2)) + " (M)"
    elif file_size < (1024 * 1024 * 1024 * 1024):
        size = str(round(file_size / 1024 / 1024 / 1024, 2)) + " (G)"
    return size


def percent_filesize(url_id, status):
    """
    获取文件大小
    :param url_id:
    :param status:
    :return:
    """
    try:
        if status in ['FINISHED', 'FAILURE', 'FAILED']:
            cache_body = s1_db.preload_result.find_one({'_id': url_id})
            send_type = config.get("preload_send", "send_type")

            if send_type == 'xml':
                return preload_worker.get_information(cache_body if cache_body else {})
            else:
                dev_cache = cache_body.get('devices', {})
                return preload_worker_new.get_information(dev_cache)
        elif status == 'PROGRESS':
            cache_body = PRELOAD_CACHE.get(url_id)
            send_type = config.get("preload_send", "send_type")
            if send_type == 'xml':
                return preload_worker.get_information(json.loads(cache_body if cache_body else '{}'))
            else:
                logger.debug("progress cache_body:%s" % cache_body)
                dev_id = json.loads(cache_body if cache_body else {}).get('dev_id')
                res = PRELOAD_CACHE.hgetall("%s_dev" % dev_id)
                res_dict = {}
                if res:
                    for k, v in list(res.items()):
                        res_dict[k] = json.loads(v)

                return preload_worker_new.get_information(res_dict)
        else:
            return {'percent': 0, 'file_size': 0, 'total_count': 0, 'count': 0}
    except Exception:
        logger.debug('percent_filesize try error: %s' % traceback.format_exc())
        return {'percent': 0, 'file_size': 0, 'total_count': 0, 'count': 0}


def getUserKey(username):
    hour = time.strftime("%Y%m%d%H", time.localtime(time.time()))
    return '%s_preload_%s' % (hour, username)


def set_preload_overload(username):

    if not username:
        logger.debug('%s set preload overload error' % username)
        return 0
    user_key = getUserKey(username)
    if not COUNTER_CACHE.exists(user_key):
        res = COUNTER_CACHE.incr(user_key, 1)
        # expire过期时间
        COUNTER_CACHE.expire(user_key, 3600)
    else:
        res = COUNTER_CACHE.incr(user_key, 1)
    return res


class InputError(Exception):

    def __init__(self, code, error_info):
        self.code = code
        self.error_info = error_info

    def __str__(self):
        return self.error_info

    def __code__(self):
        return self.code


# def task_forward(data, username):
#     '''
#     任务转发第三方
#     '''
#     try:
#         forward_url = config.get('task_forward', 'forward_ip') + '/nova/domain/prestrain/'
#
#         username = username
#         tasks = data
#         urls = []
#         task_ids = []
#         records = []
#
#         for k in tasks:
#             if not k.get('id'):
#                 raise
#             if not k.get('url'):
#                 raise
#             task_ids.append(str(k.get('id')))
#             urls.append(k.get('url'))
#             records.append({'type':'preload','created_time':datetime.now(), 'task_id': k.get('id'), 'url': k.get('url'),
#                             'username': username, 'both': k.get('both')})
#
#         if not task_ids or not urls:
#             raise
#
#         headers = {"Content-type":"application/json"}
#         data = json.dumps({'task_ids': ','.join(task_ids), 'urls': ','.join(urls)})
#         req = urllib.request.Request(forward_url, data, headers)
#         response = urllib.request.urlopen(req, timeout=10)
#         res = response.read()
#
#         for r in records:
#             r['res'] = res
#
#         s1_db.task_forward.insert_many(records)
#
#         logger.debug('trans res %s'%(res))
#         return res
#
#     except Exception, e:
#         logger.debug('trans error %s'%(e))


def query_task_forward(username, tasks_list, status_list):
    '''
    查询任务转发,
    '''
    find_result = {'totalCount': 0, 'tasks': []}
    if not tasks_list:
        return find_result
    if status_list and not 'FINISHED' in status_list:
        return find_result

    all_task = s1_db.task_forward.find(
        {'task_id': {"$in": tasks_list}, 'type': 'preload', "username": username, "both": False})
    find_result['totalCount'] = all_task.count()
    for t in all_task:
        find_result['tasks'].append({'task_id': t['task_id'], 'url': t['url'], 'status': 'FINISHED', 'percent': 100})

    return find_result


def query_task_forward_from_webluker(username, tasks_list, status_list):
    """
    get the result of preload of webluker
    :param username:  the user of the task work,  not use now
    :param tasks_list: ["1","2","3"]
    :param status_list:  not use, now
    :return: {"1234": {"http://lxcdn.miaopai.com/test/2.html": {"status": "FAIL"}},
              "49543": {"http://lxcdn.miaopai.com/test/1.html": {"status": "FAIL"}}
            }
    """

    s_data = {"task_ids": ','.join(tasks_list), "username": username}
    test_data_urlencode = json.dumps(s_data)
    try:
        requrl = config.get('task_forward', "webluker_preload_search")
    except Exception:
        logger.error('query_task_forward_from_webluker error:%s' % traceback.format_exc())
        #requrl = 'http://223.202.202.37/nova/get/domain/preload/status/'
        requrl = 'http://api.novacdn.com/nova/get/domain/preload/status/'

    try:
        req = urllib.request.Request(url=requrl, data=test_data_urlencode, headers={'Content-type': 'application/json'})
        res_data = urllib.request.urlopen(req, timeout=10)
        res = res_data.read()
        logger.debug('get data from webluker res:%s' % res)
        result = json.loads(res)
        if result:
            result_r = result.get("result_desc")
            return result_r
        return {}
    except Exception:
        print(('query_task_forward_from_webluker get data from webluker error:%s' % traceback.format_exc()))
        return {}


def process_webluker_cc(find_result, find_result_web):
    """
    combine find_result and find_result_web
    :param find_result:[
        {'task_id':xxx
        'url':xxx
        'status':xxx
        'percent':xxx},
        {.....},......
        ]
    :param find_result_web:
    :return:
    """
    logger.debug("process_webluker_cc find_result:%s, find_result_web:%s" % (find_result, find_result_web))
    if find_result:
        for result_t in find_result:
            try:
                task_id = result_t.get('task_id')
                url = result_t.get('url')
                status = result_t.get('status')
                if task_id in find_result_web:
                    # the task also send to webluker
                    if url in find_result_web.get(task_id):
                        # success case
                        if status == "FINISHED" and find_result_web.get(task_id).get(url).get("status") == "SUCCESS":
                            del find_result_web.get(task_id)[url]
                            # del the value is None
                            if not find_result_web.get(task_id):
                                del find_result_web[task_id]
                        # failed case
                        elif find_result_web.get(task_id).get(url).get("status") != "SUCCESS":
                            if find_result_web.get(task_id).get(url).get("status") == "FAIL":
                                result_t['status'] = "FAILED"
                            else:
                                result_t['status'] = "PROGRESS"
                            result_t['percent'] = 0
                            del find_result_web.get(task_id)[url]
                            # del value is None
                            if not find_result_web.get(task_id):
                                del find_result_web[task_id]
            except Exception:
                logger.debug("process_webluker_cc error:%s" % traceback.format_exc())
    if not find_result:
        find_result = []
    logger.debug("process_webluker_cc find_result_web:%s" % find_result_web)
    # {"49543": {"http://lxcdn.miaopai.com/test/1.html": {"status": "FAIL"}}}
    if find_result_web:
        for task_id_key in find_result_web:
            value_task_id = find_result_web.get(task_id_key)
            for url_key in value_task_id:
                url_values = value_task_id.get(url_key)
                if url_values.get('status') == "SUCCESS":
                    find_result.append({"task_id": task_id_key, "url": url_key, "status": "FINISHED", "percent": 100})

                elif url_values.get('status') == "UNKNOWN":
                    find_result.append({"task_id": task_id_key, "url": url_key, "status": "PROGRESS", "percent": 0})
                else:
                    find_result.append({"task_id": task_id_key, "url": url_key, "status": "FAILED", "percent": 0})

    logger.debug('process_webluker_cc  last_result find_result:%s' % find_result)
    return find_result


@preload.route('/internal/preload/finish', methods=['GET', 'POST'])
def finishd_preload():
    '''
    开放API 改变任务状态
    '''
    try:
        logger.debug('finishd_preload api body:%s remote_addr:%s' %
                     (request.data, request.remote_addr))
        data = json.loads(request.data)

        url_id = data['url_id']
        date_s = data['date_s']
        url_status = data.get('status', 'FINISHED')
        preload_worker_new.set_finished_by_api(url_id, date_s, url_status)

        return jsonify({"code": 200})

    except Exception:

        logger.debug('finishd_preload api exception error:%s' % traceback.format_exc())
        return jsonify({"code": 500, "msg": "The schema of request is error."})


def had_preload_url(username, url):

    try:

        u_md5 = hashlib.md5(url)
        u_md5_str = u_md5.hexdigest()
        key = u_md5_str + username
        if CHECK_CACHE.exists(key):
            logger.debug('had_preload_url key: %s, had preload_url True %s' % (key, url))
            return True
        else:
            CHECK_CACHE.set(key, 1)
            CHECK_CACHE.expire(key, 259200)
            return False
    except Exception:
        logger.debug('had preload_url error %s' % (traceback.format_exc()))
        return False


def get_avoid_channel(channel_code=''):
    try:
        avoid_channel = query_db.preload_channel.find_one({'channel_code': channel_code})
        is_avoid_channel = True if avoid_channel.get("status") == "AVOID" else False
        if is_avoid_channel:
            avoid_period_s = avoid_channel.get('avoid_period_s')
            avoid_period_e = avoid_channel.get('avoid_period_e')
            avoid_period_length = avoid_channel.get('period_length')
            today_str = time.strftime('%Y%m%d')
            avoid_starttime = datetime.strptime(today_str + avoid_period_s, '%Y%m%d%H:%M')
            avoid_endtime = datetime.strptime(today_str + avoid_period_e, '%Y%m%d%H:%M')
            if avoid_starttime <= datetime.now() and datetime.now() <= avoid_endtime:
                return True, avoid_period_length
        return False, 0
    except Exception:
        logger.debug('get_avoid_channel[error]: %s' % (traceback.format_exc()))
        return False, 0


def isValidStartTime(startTime, safeSeconds=1800):
    if startTime:
        startTime = time.strptime(startTime, "%Y-%m-%d %H:%M:%S")
        startTime = time.mktime(startTime)
        if startTime - time.time() < safeSeconds:
            raise InputError(410, "The startTime of task must be 30 mins later at least.")


if __name__ == "__main__":

    pass
