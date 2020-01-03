# -*- coding:utf-8 -*-
import sys
import traceback
from xml.dom.minidom import parseString
import logging
import os
import subprocess
import datetime

from flask import Flask, request, make_response, render_template
import simplejson as json
from werkzeug.exceptions import BadRequest, Forbidden, HTTPException
from flask import jsonify

from . import adapters
from . import result_tencent
from . import preload
from . import query
from . import certificate_transport
from core import splitter, splitter_new, authentication, report_server, splitter_autodesk, splitter_refreshDevice
from core.database import db_session, query_db_session, s1_db_session
from core.models import URL_OVERLOAD_PER_HOUR, DIR_OVERLOAD_PER_HOUR
from .retry_task import retry
from util import log_utils, webluker_tools
from bson.objectid import ObjectId
import time
from core.rcmsapi import isValidChannelByPortal
from .receiver_rewrite import rewrite_query_n_to_n, update_rewrite_id, update_rewrite_no_id, delete_rewrite_id
from .receiver_branch import update_retry_branch, assemble_command_info, update_refresh_result, getCodeFromXml
from util.tools import JSONEncoder, delete_fc_urlid_host
from core import rcmsapi
from cache.trans_outer_to_redis import OutSysToRedis
import core.redisfactory as redisfactory
from core.config import config
from core import queue
import copy
import hashlib
from core.subcenter_base import Subcenter_cert, Subcenter_preload
from core.link_detection_all import get_refresh_result, set_edge_device
from core.etcd_client import get_subcenters

from util.tools import get_channelname, get_channel_code, getcode_from_redis, get_uuid

from .util_rec import get_url_by_id, get_refresh_result_by_sessinId, get_urls_by_request, get_devs_by_id, get_request_by_request, send_result_error


PREFIX = 'WEBLUKER_USERNAME_URL_'


FAILED_DEV_FC = redisfactory.getDB(5)
USERNAME_URL_CACHE = redisfactory.getDB(14)

SUBCENTER_REFRSH_UID = redisfactory.getDB(3)

subcenter_factory = redisfactory.getDB(7)


# logger = logging.getLogger('receiver')
# logger.setLevel(logging.DEBUG)

logger = log_utils.get_receiver_Logger()
# filter = logging.Filter('receiver')
# logger.addFilter(filter)
# configuration
USERNAME_TENCENT = 'qq'
PASSWORD_KEY_TENCENT = 'qq@tencent@11.11'

CDN_KEY_NTESE = "c$25er1kb"
PASSWORD_KEY_NTESE = 'cc@ne.com'

SNDA_CALLBACK = 'http://116.211.20.45/api/refresh?cdn_id=1005'
SNDA_CALLBACK_DBUG = 'http://223.202.52.83/snda_callback_test'

db = query_db_session()

db_s1 = s1_db_session()
#cert_db = s1_db_session()
EXPIRETIME = 600
EXPIRETIME_BEST = 10
FIRST_HOST = 3


def split_url(urls, separator):
    if urls:
        if separator == '%0D%0A':
            urls = urls.replace('\r\n', '%0D%0A')
        if separator == '\r\n':
            urls = urls.replace('%0D%0A', '\r\n')
        return [url.strip() for url in urls.split(separator) if url]
    return []


def get_refresh3_parameters(request):
    if request.method == 'POST':
        return request.form.get('user', ''), request.form.get('pswd', ''), {
            "urls": split_url(request.form.get('urls'), '%0D%0A'),
            "dirs": split_url(request.form.get('dirs'), '%0D%0A')}
    else:
        return request.args.get('user', ''), request.args.get('pswd', ''), {
            "urls": split_url(request.args.get('urls'), '\r\n'), "dirs": split_url(request.args.get('dirs'), '\r\n')}


def create_app(db_session, query_db_session):
    '''


    Parameters:

        db_session :

        query_db_session :


    Returns:

    '''

    # application

    app = Flask(__name__)
    app.config.from_object(__name__)
    app.config.from_envvar('RECEIVER_SETTINGS', silent=True)
    app.register_blueprint(preload.preload)  # 注册preload
    app.register_blueprint(query.query)
    app.register_blueprint(retry)
    app.register_blueprint(certificate_transport.certificate_transport)

    @app.errorhandler(400)
    def page_not_found(e):
        return render_template('errors.html', message=e.description), 400

    # @app.errorhandler(201)
    # def access_exceed(e):
    #     logger.info(e.description)
    #     return jsonify(e.description), 201

    # 调整后的方式
    def access_exceed(e):
        logger.info(e.description)
        return jsonify(e.description), 201
    # 这里的None表示应用范畴，如果是应用级别的，则使用None。否则需指定对应的blueprint
    app.error_handler_spec[None][201] = access_exceed

    # @app.errorhandler(202)
    def access_all_exceed(e):
        return jsonify(e.description), 202
    app.error_handler_spec[None][202] = access_all_exceed

    # @app.errorhandler(203)
    def access_error_urls(e):
        return jsonify(e.description), 203
    app.error_handler_spec[None][203] = access_error_urls

    @app.errorhandler(401)
    def access_unauthorized(e):
        return render_template('errors.html', message=e.description), 401

    # @app.errorhandler(402)
    def access_payment_required(e):
        return render_template('errors.html', message=e.description), 402
    app.error_handler_spec[None][402] = access_payment_required

    @app.errorhandler(403)
    def access_forbidden(e):
        return render_template('errors.html', message=e.description), 403

    @app.errorhandler(404)
    def access_notfound(e):
        return render_template('errors.html', message=e.description), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        logger.error(traceback.format_exc())
        return render_template('errors.html', message="Internal Server Error."), 500

    @app.route("/content/refresh_api", methods=['POST'])
    def receive_Api():
        openapi_flag = request.headers.get(
            'X-Forwarded-Host').strip() if request.headers.get('X-Forwarded-Host') else ''
        request_data = request.args.to_dict()
        username = request_data.get('cloud_user_name', '')  # 用户名（portal中的用户名）
        # 用户类型（MAIN 为主帐户(0)，INTERNAL 为内部帐户（1），GROUP 为集团帐户(2)，FEATURE 为功能帐户(3)）
        user_type = request_data.get('cloud_user_type', '')
        cloud_client_name = request_data.get('cloud_client_name', '')  # 客户名（主账户）
        logger.debug('query_task_api data: %s|| remote_addr: %s|| openapi_flag: %s' %
                     (request.data, request.remote_addr, openapi_flag))
        task = json.loads(request.data)
        #logger.debug('-------------------------%s' % (task))
        parent = cloud_client_name if cloud_client_name else username
        isSub = True if user_type == 'FEATURE' else False

        logger.debug('request %s with {user:%s,remote_addr:%s}' %
                     (request.path, username, request.remote_addr))

        ticket = authentication.internal_verify(username, request.remote_addr)

        task["username"] = username
        task["remote_addr"] = request.remote_addr
        task["isSub"] = isSub
        task["parent"] = parent
        task["URL_OVERLOAD_PER_HOUR"] = ticket["URL_OVERLOAD_PER_HOUR"]
        task["DIR_OVERLOAD_PER_HOUR"] = ticket["DIR_OVERLOAD_PER_HOUR"]
        task['type'] = 'portal'  # request.form.get('type', 'portal')
        logger.info('task:%s' % task)

        task_all = {}
        task_all['username'] = username
        task_all['urls'] = task.get('urls')
        task_all['dirs'] = task.get('dirs')
        task_all['update_urls'] = task.get('update_urls', [])
        task_all['purge_dirs'] = task.get('purge_dirs', [])
        message = {}
        # else:
        urls_cc, urls_web = webluker_tools.get_urls(task['username'], task.get('urls'))
        dirs_cc, dirs_web = webluker_tools.get_urls(task['username'], task.get('dirs'))
        logger.debug("username:%s, urls_cc:%s, urls_web:%s, dirs_cc:%s,dirs_web:%s" %
                     (username, urls_cc, urls_web, dirs_cc, dirs_web))
        # add 2017-9-5
        update_urls_cc, update_urls_web = webluker_tools.get_urls(
            task['username'], task.get('update_urls'))
        purge_dirs_cc, purge_dirs_web = webluker_tools.get_urls(
            task['username'], task.get('purge_dirs'))
        logger.debug("/content/refresh username:%s, update_urls_cc:%s, update_urls_web:%s, purge_dirs_cc:%s, "
                     "purge_dirs_web:%s" % (
                         username, update_urls_cc, update_urls_web, purge_dirs_cc, purge_dirs_web))
        # add 2017-9-5
        web_flag = urls_web or dirs_web or update_urls_web or purge_dirs_web
        web_task = {}
        if web_flag:
            task_new = {}
            task_new['urls'] = urls_web
            if update_urls_web:
                task_new['urls'].extend(update_urls_web)
            task_new['dirs'] = dirs_web
            if purge_dirs_web:
                task_new['dirs'].extend(purge_dirs_web)
            logger.debug(
                "/content/refresh send to webluker task urls:%s, dirs:%s" % (task_new['urls'], task_new['dirs']))
            task_new['username'] = username
            web_task['task_new'] = task_new
            web_task['task_all'] = task_all

        if urls_cc or dirs_cc or update_urls_cc or purge_dirs_cc:
            task['urls'] = urls_cc
            task['dirs'] = dirs_cc
            if update_urls_cc:
                task['update_urls'] = update_urls_cc
            if purge_dirs_cc:
                task['purge_dirs'] = purge_dirs_cc
            task['web_task'] = web_task
            message = splitter_new.process(db_session, task, True)
        if not message.get('r_id') and web_flag:
            r_id = None
            message = webluker_tools.post_data_to_webluker(task_new, task_all, r_id)
        if message.get("urlExceed") or message.get("dirExceed"):
            raise gethTTPException(202, message)
        elif message.get("invalids"):
            raise gethTTPException(201, message)
        return jsonify(message)

    @app.route("/content/refresh", methods=['POST'])
    def receive():
        '''
            刷新对外提供的接口

        Parameters
        ----------
         username    刷新功能帐号或主账号
         password    密码
         task        刷新任务，JSON 格式

        Returns
        -------
        　　Http code 　　信息    　　解释
　　          200   { " r_id " : " xxx " }      标识刷新请求提交成功，返回值为本次提交请求的id 号，用于查询刷新请求的结果，或接收刷新系统的反馈结果。
　　          201   { " r_id " : " xxx " ,
                " urlexceed " : " xx " }    如果url提交超量，返回的body中有一项urlexceed: xx，其中xx表示含义如下：如果为正数，表示超
                过一个小时的量；如果为负数，其绝对值标识超过一天的量。
　　                { " r_id " : " xxx " ,
                " direxceed" : " xx " } 如果url提交超量，返回的body中有一项direxceed: xx，其中xx表示含义如下：direxceed的值如果
                为正数，表示超过当前10分钟规定的量，如果为-1，表示没有目录刷新的权限（用于强制关闭用户的恶意的目录刷新）。
　　          202   { " direxceed" : " xx ", " urlexceed" : " xx ", " error_urls " : [" xx "]} 超量，可能部分频道错误
              203   { " r_id " : " xxx " , " error_urls " : [" xx "] } 部分错误
                    { " error_urls " : [" xx "] } 所有urls或dirs 全错误
              401  INPUT_ERROR  　　参数不正确     　　
　　          402  WRONG_PASSWORD   　　用户名密码错误   　　
　　          403  NO_USER_EXISTS   　　用户被禁用     　　
　　          404   　　请求未找到 　　
　　          500   　　服务器错误 　　需要联系客服人员
        '''
        if len(request.form) > 0:
            username = request.form.get('username', '')
            password = request.form.get('password', '')
            task = load_task(request.form.get("task", "{}"))

        else:
            data = load_task(request.data)
            username = data.get('username', '')
            password = data.get('password', '')
            task = data.get('task')
            if isinstance(task, str):
                task = load_task(task)

        logger.debug(
            'request %s with {user:%s,remote_addr:%s,task:%s}' % (request.path, username, request.remote_addr, task))
        ticket = authentication.verify(username, password, request.remote_addr)
        task["username"] = ticket["name"]
        task["isSub"] = ticket.get("isSub", False)
        task["parent"] = ticket.get("parent", ticket["name"])
        task["remote_addr"] = request.remote_addr
        task["URL_OVERLOAD_PER_HOUR"] = ticket["URL_OVERLOAD_PER_HOUR"]
        task["DIR_OVERLOAD_PER_HOUR"] = ticket["DIR_OVERLOAD_PER_HOUR"]
        task['type'] = 'API'
        # try:
        #     user_list = eval(config.get('task_forward', 'usernames'))
        # except Exception, e:
        #     logger.debug('splitter_new submit error:%s' % traceback.format_exc())
        #     user_list = []
        task_all = {}
        task_all['username'] = username
        task_all['urls'] = task.get('urls')
        task_all['dirs'] = task.get('dirs')
        task_all['update_urls'] = task.get('update_urls')
        task_all['purge_dirs'] = task.get('purge_dirs')
        message = {}
        # if not USERNAME_URL_CACHE.exists(PREFIX + task['username']):
        #     logger.debug('this task go to the net of big')
        #     message = splitter_new.process(db_session, task, True)
        # else:
        urls_cc, urls_web = webluker_tools.get_urls(task['username'], task.get('urls'))
        dirs_cc, dirs_web = webluker_tools.get_urls(task['username'], task.get('dirs'))
        logger.debug("username:%s, urls_cc:%s, urls_web:%s, dirs_cc:%s,dirs_web:%s" %
                     (username, urls_cc, urls_web, dirs_cc, dirs_web))
        # add 2017-9-5
        update_urls_cc, update_urls_web = webluker_tools.get_urls(
            task['username'], task.get('update_urls'))
        purge_dirs_cc, purge_dirs_web = webluker_tools.get_urls(
            task['username'], task.get('purge_dirs'))
        logger.debug("/content/refresh username:%s, update_urls_cc:%s, update_urls_web:%s, purge_dirs_cc:%s, "
                     "purge_dirs_web:%s" % (username, update_urls_cc, update_urls_web, purge_dirs_cc, purge_dirs_web))
        # add 2017-9-5
        web_flag = urls_web or dirs_web or update_urls_web or purge_dirs_web
        web_task = {}
        if web_flag:
            task_new = {}
            task_new['urls'] = urls_web
            if update_urls_web:
                task_new['urls'].extend(update_urls_web)
            task_new['dirs'] = dirs_web
            if purge_dirs_web:
                task_new['dirs'].extend(purge_dirs_web)
            logger.debug(
                "/content/refresh send to webluker task urls:%s, dirs:%s" % (task_new['urls'], task_new['dirs']))
            task_new['username'] = username
            web_task['task_new'] = task_new
            web_task['task_all'] = task_all

        if urls_cc or dirs_cc or update_urls_cc or purge_dirs_cc:
            task['urls'] = urls_cc
            task['dirs'] = dirs_cc
            if update_urls_cc:
                task['update_urls'] = update_urls_cc
            if purge_dirs_cc:
                task['purge_dirs'] = purge_dirs_cc
            task['web_task'] = web_task
            message = splitter_new.process(db_session, task, True)
        # if urls_web or dirs_web or update_urls_web or purge_dirs_web:
        #     task_new = {}
        #     task_new['urls'] = urls_web
        #     if update_urls_web:
        #         task_new['urls'].extend(update_urls_web)
        #     task_new['dirs'] = dirs_web
        #     if purge_dirs_web:
        #         task_new['dirs'].extend(purge_dirs_web)
        #     logger.debug("/content/refresh send to webluker task urls:%s, dirs:%s" % (task_new['urls'], task_new['dirs']))
        #     task_new['username'] = username
            # get the r_id of message
        if not message.get('r_id') and web_flag:
            r_id = None
            message = webluker_tools.post_data_to_webluker(task_new, task_all, r_id)

        # if username in user_list:
        #     task_new = {}
        #     task_new['urls'] = task.get('urls', [])
        #     task_new['dirs'] = task.get('dirs', [])
        #     task_new['username'] = username
        #     webluker_tools.post_data_to_webluker(task_new)

        if message.get("urlExceed") or message.get("dirExceed"):
            raise gethTTPException(202, message)
        elif message.get("invalids"):
            raise gethTTPException(201, message)
        return jsonify(message)

    @app.route("/content/refresh_custom", methods=['POST'])
    def receive_custom():
        '''
            刷新对外提供的接口  autodesk

        Parameters
        ----------
         username    刷新功能帐号或主账号
         password    密码
         task        刷新任务，JSON 格式

        Returns
        -------
        　　Http code 　　信息    　　解释
　　          200   { " r_id " : " xxx " }      标识刷新请求提交成功，返回值为本次提交请求的id 号，用于查询刷新请求的结果，或接收刷新系统的反馈结果。
　　          201   { " r_id " : " xxx " ,
                " urlexceed " : " xx " }    如果url提交超量，返回的body中有一项urlexceed: xx，其中xx表示含义如下：如果为正数，表示超
                过一个小时的量；如果为负数，其绝对值标识超过一天的量。
　　                { " r_id " : " xxx " ,
                " direxceed" : " xx " } 如果url提交超量，返回的body中有一项direxceed: xx，其中xx表示含义如下：direxceed的值如果
                为正数，表示超过当前10分钟规定的量，如果为-1，表示没有目录刷新的权限（用于强制关闭用户的恶意的目录刷新）。
　　          202   { " direxceed" : " xx ", " urlexceed" : " xx ", " error_urls " : [" xx "]} 超量，可能部分频道错误
              203   { " r_id " : " xxx " , " error_urls " : [" xx "] } 部分错误
                    { " error_urls " : [" xx "] } 所有urls或dirs 全错误
              401  INPUT_ERROR  　　参数不正确     　　
　　          402  WRONG_PASSWORD   　　用户名密码错误   　　
　　          403  NO_USER_EXISTS   　　用户被禁用     　　
　　          404   　　请求未找到 　　
　　          500   　　服务器错误 　　需要联系客服人员
        '''
        if len(request.form) > 0:
            username = request.form.get('username', '')
            password = request.form.get('password', '')
            task = load_task(request.form.get("task", "{}"))

        else:
            data = load_task(request.data)
            logger.debug('/content/refresh_custom  data:%s, type:%s' % (data, type(data)))

            username = data.get('username', '')
            password = data.get('password', '')
            task = data.get('task')
            if isinstance(task, str):
                task = load_task(task)

        logger.debug(
            'request %s with {user:%s,remote_addr:%s,task:%s}' % (request.path, username, request.remote_addr, task))
        ticket = authentication.verify(username, password, request.remote_addr)
        # ticket = authentication.internal_verify(username, request.remote_addr)
        task["username"] = ticket["name"]
        task["isSub"] = ticket.get("isSub", False)
        task["parent"] = ticket.get("parent", ticket["name"])
        task["remote_addr"] = request.remote_addr
        task["URL_OVERLOAD_PER_HOUR"] = ticket["URL_OVERLOAD_PER_HOUR"]
        task["DIR_OVERLOAD_PER_HOUR"] = ticket["DIR_OVERLOAD_PER_HOUR"]
        task['type'] = 'API'
        message = splitter_autodesk.process(db_session, task, True)
        if message.get("urlExceed") or message.get("dirExceed"):
            raise gethTTPException(202, message)
        elif message.get("invalids"):
            raise gethTTPException(201, message)
        return jsonify(message)

#     @app.route("/internal/refresh_", methods=['POST'])
#     def receive():
#         '''
#             刷新对外提供的接口  autodesk
#
#         Parameters
#         ----------
#          username    刷新功能帐号或主账号
#          password    密码
#          task        刷新任务，JSON 格式
#
#         Returns
#         -------
#         　　Http code 　　信息    　　解释
# 　　          200   { " r_id " : " xxx " }      标识刷新请求提交成功，返回值为本次提交请求的id 号，用于查询刷新请求的结果，或接收刷新系统的反馈结果。
# 　　          201   { " r_id " : " xxx " ,
#                 " urlexceed " : " xx " }    如果url提交超量，返回的body中有一项urlexceed: xx，其中xx表示含义如下：如果为正数，表示超
#                 过一个小时的量；如果为负数，其绝对值标识超过一天的量。
# 　　                { " r_id " : " xxx " ,
#                 " direxceed" : " xx " } 如果url提交超量，返回的body中有一项direxceed: xx，其中xx表示含义如下：direxceed的值如果
#                 为正数，表示超过当前10分钟规定的量，如果为-1，表示没有目录刷新的权限（用于强制关闭用户的恶意的目录刷新）。
# 　　          202   { " direxceed" : " xx ", " urlexceed" : " xx ", " error_urls " : [" xx "]} 超量，可能部分频道错误
#               203   { " r_id " : " xxx " , " error_urls " : [" xx "] } 部分错误
#                     { " error_urls " : [" xx "] } 所有urls或dirs 全错误
#               401  INPUT_ERROR  　　参数不正确     　　
# 　　          402  WRONG_PASSWORD   　　用户名密码错误   　　
# 　　          403  NO_USER_EXISTS   　　用户被禁用     　　
# 　　          404   　　请求未找到 　　
# 　　          500   　　服务器错误 　　需要联系客服人员
#         '''
#         if len(request.form) > 0:
#             username = request.form.get('username', '')
#             password = request.form.get('password', '')
#             task = load_task(request.form.get("task", "{}"))
#
#         else:
#             data = load_task(request.data)
#             username = data.get('username', '')
#             password = data.get('password', '')
#             task = data.get('task')
#             if isinstance(task, str):
#                 task = load_task(task)
#
#         logger.debug(
#             'request %s with {user:%s,remote_addr:%s,task:%s}' % (request.path, username, request.remote_addr, task))
#         # ticket = authentication.verify(username, password, request.remote_addr)
#         ticket = authentication.internal_verify(username, request.remote_addr)
#         task["username"] = ticket["name"]
#         task["isSub"] = ticket.get("isSub", False)
#         task["parent"] = ticket.get("parent", ticket["name"])
#         task["remote_addr"] = request.remote_addr
#         task["URL_OVERLOAD_PER_HOUR"] = ticket["URL_OVERLOAD_PER_HOUR"]
#         task["DIR_OVERLOAD_PER_HOUR"] = ticket["DIR_OVERLOAD_PER_HOUR"]
#         task['type'] = 'API'
#         message = splitter_autodesk.process(db_session, task, True)
#         if message.get("urlExceed") or message.get("dirExceed"):
#             raise gethTTPException(202, message)
#         elif message.get("invalids"):
#             raise gethTTPException(201, message)
#         return jsonify(message)

    @app.route("/internal/refresh", methods=['POST'])
    def internal_receive():
        if request.form.get('isSub', None):
            result = internal_receive_new(request)
            logger.info('result:%s' % result)
        else:
            result = internal_receive_bak(request)
            logger.info('result_bak:%s' % result)

        if result.get("urlExceed") and result.get("dirExceed"):
            result["code"] = 3
        elif result.get("urlExceed"):
            result["code"] = 1
        elif result.get("dirExceed"):
            result["code"] = 2
        elif result.get("invalids"):
            result["code"] = 5
        else:
            result["code"] = 0
        return jsonify(result)

    @app.route("/internal/refresh_webluker", methods=['POST'])
    def internal_receive_webluker():
        if request.form.get('isSub', None):
            result = internal_receive_new_webluker(request)
            logger.info('result:%s' % result)
        else:
            result = internal_receive_bak_webluker(request)
            logger.info('result_bak:%s' % result)

        if result.get("urlExceed") and result.get("dirExceed"):
            result["code"] = 3
        elif result.get("urlExceed"):
            result["code"] = 1
        elif result.get("dirExceed"):
            result["code"] = 2
        elif result.get("invalids"):
            result["code"] = 5
        else:
            result["code"] = 0
        return jsonify(result)

    @app.route("/internal/refreshDevice", methods=['POST'])
    def internal_receive_refresh_device():
        result = internal_receive_refresh_device(request)
        logger.info('refreshDevice:%s' % result)
        if result.get("urlExceed") and result.get("dirExceed"):
            result["code"] = 3
        elif result.get("urlExceed"):
            result["code"] = 1
        elif result.get("dirExceed"):
            result["code"] = 2
        elif result.get("invalids"):
            result["code"] = 5
        else:
            result["code"] = 0
        return jsonify(result)

    def internal_receive_new(request):
        username = request.form.get('username', '')
        parent = request.form.get('parent', username)
        isSub = True if request.form.get('isSub', 'False') in ['True', 'true'] else False
        logger.debug('request %s with {user:%s,remote_addr:%s}' %
                     (request.path, username, request.remote_addr))
        task = load_task(request.form.get("task", "{}"))
        task["username"] = username
        ticket = authentication.internal_verify(username, request.remote_addr)
        task["remote_addr"] = request.remote_addr
        task["isSub"] = isSub
        task["parent"] = parent
        task["URL_OVERLOAD_PER_HOUR"] = ticket["URL_OVERLOAD_PER_HOUR"]
        task["DIR_OVERLOAD_PER_HOUR"] = ticket["DIR_OVERLOAD_PER_HOUR"]
        task['type'] = request.form.get('type', 'portal')
        logger.info('task:%s' % task)

        task_all = {}
        task_all['username'] = username
        task_all['urls'] = task.get('urls')
        task_all['dirs'] = task.get('dirs')
        task_all['update_urls'] = task.get('update_urls')
        task_all['purge_dirs'] = task.get('purge_dirs')
        message = {}

        urls_cc, urls_web = webluker_tools.get_urls(task['username'], task.get('urls'))
        dirs_cc, dirs_web = webluker_tools.get_urls(task['username'], task.get('dirs'))
        logger.debug("username:%s, urls_cc:%s, urls_web:%s, dirs_cc:%s,dirs_web:%s" %
                     (username, urls_cc, urls_web, dirs_cc, dirs_web))
        # add 2017-9-5
        update_urls_cc, update_urls_web = webluker_tools.get_urls(
            task['username'], task.get('update_urls'))
        purge_dirs_cc, purge_dirs_web = webluker_tools.get_urls(
            task['username'], task.get('purge_dirs'))
        logger.debug("internal_receive_new username:%s, update_url_cc:%s, update_urls_web:%s, purge_dirs_cc:%s, "
                     "purge_dirs_web:%s" % (username, update_urls_cc, update_urls_web, purge_dirs_cc, purge_dirs_web))

        web_flag = urls_web or dirs_web or update_urls_web or purge_dirs_web
        web_task = {}
        if web_flag:
            task_new = {}
            task_new['urls'] = urls_web
            if update_urls_web:
                task_new['urls'].extend(update_urls_web)
            task_new['dirs'] = dirs_web
            if purge_dirs_web:
                task_new['dirs'].extend(purge_dirs_web)
            logger.debug(
                "/content/refresh send to webluker task urls:%s, dirs:%s" % (task_new['urls'], task_new['dirs']))
            task_new['username'] = username
            web_task['task_new'] = task_new
            web_task['task_all'] = task_all

        # add 2017-9-5
        if urls_cc or dirs_cc or update_urls_cc or purge_dirs_cc:
            task['urls'] = urls_cc
            task['dirs'] = dirs_cc
            if update_urls_cc:
                task['update_urls'] = update_urls_cc
            if purge_dirs_cc:
                task['purge_dirs'] = purge_dirs_cc
            task['web_task'] = web_task
            message = splitter_new.process(db_session, task, True)
        if not message.get('r_id') and web_flag:
            r_id = None
            message = webluker_tools.post_data_to_webluker(task_new, task_all, r_id)

        return message

    def internal_receive_bak(request):
        username = request.form.get('username', '')
        logger.debug('request %s with {user:%s,remote_addr:%s}' %
                     (request.path, username, request.remote_addr))
        task = load_task(request.form.get("task", "{}"))
        task["username"] = username
        ticket = authentication.internal_verify(username, request.remote_addr)
        task["remote_addr"] = request.remote_addr
        task["URL_OVERLOAD_PER_HOUR"] = ticket["URL_OVERLOAD_PER_HOUR"]
        task["DIR_OVERLOAD_PER_HOUR"] = ticket["DIR_OVERLOAD_PER_HOUR"]
        task['type'] = request.form.get('type', 'portal')

        task_all = {}
        task_all['username'] = username
        task_all['urls'] = task.get('urls')
        task_all['dirs'] = task.get('dirs')
        task_all['update_urls'] = task.get('update_urls')
        task_all['purge_dirs'] = task.get('purge_dirs')
        message = {}

        urls_cc, urls_web = webluker_tools.get_urls(task['username'], task.get('urls'))
        dirs_cc, dirs_web = webluker_tools.get_urls(task['username'], task.get('dirs'))
        logger.debug("username:%s, urls_cc:%s, urls_web:%s, dirs_cc:%s,dirs_web:%s" %
                     (username, urls_cc, urls_web, dirs_cc, dirs_web))
        # add 2017-9-5
        update_urls_cc, update_urls_web = webluker_tools.get_urls(
            task['username'], task.get('update_urls'))
        purge_dirs_cc, purge_dirs_web = webluker_tools.get_urls(
            task['username'], task.get('purge_dirs'))
        logger.debug("internal_receive_bak username:%s, update_url_cc:%s, update_urls_web:%s, purge_dirs_cc:%s, "
                     "purge_dirs_web:%s" % (username, update_urls_cc, update_urls_web, purge_dirs_cc, purge_dirs_web))
        # add 2017-9-5

        # add 2017-9-12  by rubin
        web_flag = urls_web or dirs_web or update_urls_web or purge_dirs_web
        web_task = {}
        if web_flag:
            task_new = {}
            task_new['urls'] = urls_web
            if update_urls_web:
                task_new['urls'].extend(update_urls_web)
            task_new['dirs'] = dirs_web
            if purge_dirs_web:
                task_new['dirs'].extend(purge_dirs_web)
            logger.debug(
                "/content/refresh send to webluker task urls:%s, dirs:%s" % (task_new['urls'], task_new['dirs']))
            task_new['username'] = username
            web_task['task_new'] = task_new
            web_task['task_all'] = task_all

        if urls_cc or dirs_cc or update_urls_cc or purge_dirs_cc:
            task['urls'] = urls_cc
            task['dirs'] = dirs_cc
            if update_urls_cc and len(update_urls_cc) > 0:
                task['update_urls'] = update_urls_cc
            if purge_dirs_cc and len(purge_dirs_cc) > 0:
                task['purge_dirs'] = purge_dirs_cc
            task['web_task'] = web_task
            message = splitter.process(db_session, task, True)
        # add by rubin 2017-09-12  only send to webluker
        if not message.get('r_id') and web_flag:
            r_id = None
            message = webluker_tools.post_data_to_webluker(task_new, task_all, r_id)

        return message

    def internal_receive_new_webluker(request):
        username = request.form.get('username', '')
        parent = request.form.get('parent', username)
        isSub = True if request.form.get('isSub', 'False') in ['True', 'true'] else False
        logger.debug('internal_receive_new_webluker request %s with {user:%s,remote_addr:%s}'
                     % (request.path, username, request.remote_addr))
        task = load_task(request.form.get("task", "{}"))
        task["username"] = username
        ticket = authentication.internal_verify(username, request.remote_addr)
        task["remote_addr"] = request.remote_addr
        task["isSub"] = isSub
        task["parent"] = parent
        task["URL_OVERLOAD_PER_HOUR"] = ticket["URL_OVERLOAD_PER_HOUR"]
        task["DIR_OVERLOAD_PER_HOUR"] = ticket["DIR_OVERLOAD_PER_HOUR"]
        task['type'] = request.form.get('type', 'portal')
        logger.info('internal_receive_new_webluker task:%s' % task)
        return splitter_new.process(db_session, task, True)

    def internal_receive_bak_webluker(request):
        username = request.form.get('username', '')
        logger.debug('internal_receive_bak_webluker request %s with {user:%s,remote_addr:%s}'
                     % (request.path, username, request.remote_addr))
        task = load_task(request.form.get("task", "{}"))
        task["username"] = username
        ticket = authentication.internal_verify(username, request.remote_addr)
        task["remote_addr"] = request.remote_addr
        task["URL_OVERLOAD_PER_HOUR"] = ticket["URL_OVERLOAD_PER_HOUR"]
        task["DIR_OVERLOAD_PER_HOUR"] = ticket["DIR_OVERLOAD_PER_HOUR"]
        task['type'] = request.form.get('type', 'portal')
        return splitter.process(db_session, task, True)

    def internal_receive_refresh_device(request):
        username = request.form.get('username', '')
        logger.debug('request %s with {user:%s,remote_addr:%s}' %
                     (request.path, username, request.remote_addr))
        task = load_task(request.form.get("task", "{}"))
        task["username"] = username
        ticket = authentication.internal_verify(username, request.remote_addr)
        task["remote_addr"] = request.remote_addr
        task["URL_OVERLOAD_PER_HOUR"] = ticket["URL_OVERLOAD_PER_HOUR"]
        task["DIR_OVERLOAD_PER_HOUR"] = ticket["DIR_OVERLOAD_PER_HOUR"]
        task['type'] = request.form.get('type', 'portal')
        task['devices'] = load_task(request.form.get('devices', []))
        return splitter_refreshDevice.process(db_session, task, True)

    @app.route("/receiveService", methods=['POST'])
    def fc_report():
        logger.debug("ReceiveSnda :%s" % request.data)
        report_server.report(request.data, request.remote_addr)
        return 'ok'

    @app.route("/receiveStore", methods=['POST'])
    def parseStore():
        """
        parse json data  and store mongodb
        把接收到到的json数据解析，保存到mongo数据库中
        目录刷新结果格式：
         {"result":512,"id":"1438716009_d17b8cd63add11e5939090e2ba343720"}
          URL刷新结果格式：
          [{"result":"200","id":"1","result_gzip":"200"},
           {"result":"200","id":"2","result_gzip":"200"},
           {"result":"200","id":"10","result_gzip":"200"}]

           接收的目录刷新格式如下：
                           {"result":512,"id":"d17b8cd63add11e5939090e2"}
             URL刷新结果格式如下：
                   [{"result":"200","id":"1","result_gzip":"200"},
                     {"result":"200","id":"552f25c72b8a68da7a670667","result_gzip":"200"},
                     {"result":"200","id":"552f50e72b8a68ba42081172","result_gzip":"200"},
                     {"result":"200","id":"552f50e72b8a68ba42081173","result_gzip":"200"},
                     {"result":"200","id":"552f50e72b8a68ba42081174","result_gzip":"200"},
                     {"result":"200","id":"552f50e72b8a68ba42081175","result_gzip":"200"}]
           其中
             "result":"200"是非压缩URL的刷新结果
             "result_gzip":"200"代表的是压缩存储URL@@@accept-encoding_gzip的刷新结果

{"result":[{"result":"404","result_gzip":"404","id":"57849a752b8a68206e87ff83"}],"hostname":"cnc-js-c-3wr"}

        """
        # logger.debug("接收到的信息")
        # logger.debug('%s'%request)
        # 223.202.201.196
        # return json.dumps({"content": 'error'})

        # logger.debug("rubin_test receiveStore  request data:%s" % request.data)
        remote_ip = request.remote_addr
        logger.debug('receiveStore remote_ip:%s' % remote_ip)
        result = request.data
        logger.debug("report data:%s" % request.data)
        pResult = load_task(result)  # 解析接收到的json数据
        logger.debug('receiver parseStore pResult:%s' % pResult)
        if isinstance(pResult, list):
            return json.dumps({'msg': 'error', 'content': 'update error'})

        host = pResult.get('vip', None)
        if not host:
            logger.debug('receiver receiverStore host  in null')
            return json.dumps({'msg': 'error', 'content': 'hostname is null'})

        # if not host_remote_addr:
        #     return json.dumps({'msg': 'error', 'content': 'host ip is not register in mongo'})
        # 首先判断pResult 是否为一个列表 如果是一个列表  表明是url刷新的结果   否则是目录刷新的结果
        if isinstance(pResult.get('result'), list):
            flag_error = False
            for resu in pResult.get('result'):
                resulteT = {}
                # the ip of the edge host lvs
                resulteT['host'] = host
                resulteT["session_id"] = resu.get('id', 0)
                # resulteT["host"] = host_remote_addr
                resulteT["result_gzip"] = resu.get("result_gzip", 0)
                resulteT["result"] = resu["result"]
                resulteT["time"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S %f")
                #resulteT["time"] = datetime.datetime.now()
                logger.debug("resulteT:%s" % resulteT)
                #res_r = update_refresh_result.delay(resulteT)
                queue.put_json2('result_task', [resulteT])
            return json.dumps({'msg': 'ok', 'content': 'update success'})
        else:
            resulteT = {}
            resulteT['host'] = host
            resulteT["session_id"] = pResult["id"]
            # resulteT["result_gzip"] = pResult.get("result_gzip",None)
            resulteT["time"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S %f")
            resulteT["result"] = pResult["result"]
            #resulteT["time"] = datetime.datetime.now()
            #update_refresh_result.delay(resulteT, flag=2)
            queue.put_json2('result_task', [resulteT])
            return json.dumps({'msg': 'ok', 'content': 'update success'})

    @app.route("/receiveSubCenterGrasp", methods=['POST', 'GET'])
    def sub_center_grasp():
        """
        sub center send grab data request, return the corresponding data
        :return:
        """
        # result = request.data
        # parse_result = load_task(result)
        # id_host = parse_result.get("key", "")
        logger.debug(request.args)
        rid = request.args.get("key", "")
        host = request.args.get("host", "")
        logger.debug("receiver rid:%s,host:%s" % (rid, host))
        # array_id_host = id_host.split(",")
        # if len(array_id_host) != 2:
        #     return json.dumps({'content': "received key value is incorrect"})
        if not rid or not host:
            return json.dumps({'content': 'id is None or host is None'})
        else:
            return assemble_command_info(rid, host)

    @app.route("/receiveSubCenterResult", methods=['POST', 'GET'])
    def sub_center_result():
        """
        receive the result of sub center, the result is the result of a successful or not


        xml:
        <?xml version="1.0" encoding="UTF-8"?>
        <url_purge_response sessionid="bcd406fa3df711e6b84100e0ed25a740">
        <url_ret id="5773">404</url_ret>
        </url_purge_response>

        :return:
        """
        # get sub center ip
        sub_center_ip = request.remote_addr
        result = request.data
        try:
            parse_result = load_task(result)
            logger.debug("receiver branch center parse_result:%s" % parse_result)
        except Exception:
            logger.debug("parse data error:%s" % e)
            #  need to add some codes
            return json.dumps({'msg': 'error', 'content': 'parse json data error:%s' % e})
        rid = parse_result.get("rid", None)
        # receive data type, node_name
        node_name = parse_result.get("node_name", None)
        if not node_name:
            logger.debug("receiver sub_center_result node_name is null")
            return json.dumps({'msg': 'error', 'content': 'node_name is null'})

        # branch_code = parse_result.get("code", None)
        host = parse_result.get("host", None)
        if not host:
            return json.dumps({'msg': 'error', 'content': 'host is None'})
        # get the type of refresh
        # refresh_type = parse_result.get('refresh_type', None)
        refresh_type = parse_result.get('refresh_type', '')
        if not refresh_type:
            return json.dumps({'msg': 'error', 'content': 'refresh_type is None'})

        ack_content = parse_result.get('ack', None)
        # dictionary   {id: code, id1:code1, id2:code2}
        node_dic = {}

        if not ack_content:
            logger.debug("receiver receiveSubCenterResult  receive xml is null")
            branch_code = 503
            try:
                retry_device_branch_list = db.retry_device_branch.find({'rid': ObjectId(rid)})
            except Exception:
                logger.debug(
                    "receiver receiveSubCenterResult  query retry_device_branch_list error:%s" % e)
                return json.dumps({'msg': 'error', 'content': 'receiver receiveSubCenterResult  '
                                                              'query retry_device_branch_list error:%s' % e})
            if retry_device_branch_list:
                flag = True
                for retry_device_branch in retry_device_branch_list:
                    retry_branch_id = retry_device_branch.get("_id")
                    result = update_retry_branch(
                        retry_branch_id, branch_code, host, sub_center_ip, rid, refresh_type)
                    result_msg = load_task(result).get('msg')
                    if result_msg == 'error':
                        flag = False
                if flag:
                    return json.dumps({'msg': 'ok', 'content': 'branch can not reach edge device, '
                                                               'update retry_device_branch device success'})
                else:
                    return json.dumps({'msg': 'error', 'content': 'branch can not reach edge device, '
                                                                  'update retry_device_branch device failed'})
            else:
                return json.dumps({'msg': 'error', 'content': 'retry_device_branch list is null'})

        else:
            # xml is not null
            try:
                node_dic = getCodeFromXml(ack_content, node_name)
                if not node_dic:
                    return json.dumps({'msg': 'error', 'content': 'can not get data from xml'})
                else:
                    flag = True
                    for node_id in list(node_dic.keys()):
                        logger.debug("receiver sub_center_result node_id:%s, code:%s" %
                                     (node_id, node_dic[node_id]))
                        try:
                            if len(node_id) < 32:  # process the  device which the id is 4 bit
                                retry_obj = db.retry_device_branch.find({'rid': ObjectId(rid)})
                            else:
                                # original logical
                                if refresh_type == 'cert_task':
                                    retry_obj = db.retry_device_branch.find_one(
                                        {'rid': ObjectId(rid), "task_id": ObjectId(node_id)})
                                else:
                                    retry_obj = db.retry_device_branch.find_one(
                                        {'rid': ObjectId(rid), "uid": ObjectId(node_id)})
                        except Exception:
                            logger.debug(
                                "receiver receiveSubCenterResult retry_branch_content error:%s" % e)
                        if isinstance(retry_obj, dict):
                            retry_branch_id = retry_obj.get('_id', None)
                            url_id = "URLID_" + str(retry_obj.get('uid')) + "_FC"

                            if retry_branch_id:
                                if int(node_dic[node_id]) == 200:
                                    delete_fc_urlid_host(url_id, host)
                                result = update_retry_branch(retry_branch_id, node_dic[node_id], host, sub_center_ip, rid,
                                                             refresh_type)
                                logger.debug("update retry_device_branch result:%s" % result)
                                result_msg = load_task(result).get('msg')
                                if result_msg == 'error':
                                    flag = False
                        else:
                            for retry_obj_t in retry_obj:
                                retry_branch_id = retry_obj_t.get('_id', None)
                                url_id = "URLID_" + str(retry_obj_t.get('uid')) + "_FC"

                                if retry_branch_id:
                                    if int(node_dic[node_id]) == 200:
                                        delete_fc_urlid_host(url_id, host)
                                    result = update_retry_branch(retry_branch_id, node_dic[node_id], host,
                                                                 sub_center_ip, rid, refresh_type)
                                    logger.debug("update retry_device_branch result:%s" % result)
                                    result_msg = load_task(result).get('msg')
                                    if result_msg == 'error':
                                        flag = False
                            break
                    if flag:
                        return json.dumps({'msg': 'ok', 'content': 'branch  reach edge device success, '
                                                                   'update retry_device_branch device success'})
                    else:
                        return json.dumps({'msg': 'error', 'content': 'branch  reach edge device failed, '
                                                                      'update retry_device_branch device failed'})
            except Exception:
                logger.debug("receiver  receiveSubCenterResult parse xml error:%s" %
                             traceback.format_exc())
                return json.dumps({'msg': 'error', 'content': 'parse xml error:%s' % e})

    # def getNameAccordingId(id, host_id):
    #     """
    #     222.84.188.23
    #     61.240.135.49
    #     58.27.108.197
    #
    #     通过id,把这个id转换为Object类型，通过表url,查询到dev_id,然后根据dev_id查询device表
    #     查找表里面的响应的_id,找到device中包含的相同的host_id,返回对应的名称；如果没找到返回None
    #     :param id:查询用到的_id,查询url表时用
    #     :param host_id  对应的主机id
    #     :return 返回主机的名称  设备状态   是否是上层  设备类型 不存在返回None， None, None, None
    #     """
    #
    #     # 此地方修改了业务逻辑  数据需要从device_app中获得   获得数据以后 根据host  地址  是否和传过来的host_id 作比较  如果存在相应的host_id
    #     # 则为所需要的信息
    #     result = db_session.device_app.find_one({'host': host_id})
    #     # logger.debug("host_id: %s" % host_id)
    #     # logger.debug("result:结果%s" % result)
    #     if result:
    #         # logger.debug("result['name'] %s" %result['name'])
    #         # logger.debug("result['status']: %s" % result['status'])
    #         # logger.debug("result['firstlayer']: %s" %result['firstlayer'])
    #         return result['name'], result['status'], result['firstlayer'], result['type']
    #     else:
    #         return None, None, None, None

    # def getCodeFromXml(xmlBody, node_name):
    #     node = parseString(xmlBody).getElementsByTagName(node_name)[0]
    #     return int(node.firstChild.data)

    def load_task(task):
        '''
            解析接口的task

        Parameters
        ----------
        task : 刷新任务，JSON 格式

        Returns
        -------
        {"urls":["http://***1.jbp","http://***2.jbp"],
　　      "dirs":["http://***/","http://d***2/"],
　　      "callback":{"url":"http://***",
　　                  "email":["mail1","mail2"],
                    "acptNotice":true}}
        '''
        try:
            return json.loads(task)
        except Exception:
            logger.warn(task, exc_info=sys.exc_info())
            raise BadRequest("The schema of task is error.")

    @app.route("/index.jsp", methods=['POST', 'GET', 'HEAD'])
    def adapter_refresh3():
        """
        http://ccms.chinacache.com/index.jsp?&user=miaozhen&pswd=EudC@2gL&ok=ok&urls=http://s.tpg.stfile.com/b/c2/bc23aa4c11957ce67535220e91543ffe.flv'

        ccms.chinacache.com老接口
        :return:
        """
        username, password, task = get_refresh3_parameters(request)
        logger.debug('request %s with {user:%s,remote_addr:%s}' %
                     (request.path, username, request.remote_addr))
        ticket = authentication.verify(username, password, request.remote_addr)
        task["username"] = ticket.get("parent", ticket["name"])
        task["remote_addr"] = request.remote_addr
        task["URL_OVERLOAD_PER_HOUR"] = ticket["URL_OVERLOAD_PER_HOUR"]
        task["DIR_OVERLOAD_PER_HOUR"] = ticket["DIR_OVERLOAD_PER_HOUR"]
        task['type'] = 'index'
        message = splitter.process(db_session, task, True)
        responseMessage = parseString(
            '<result><url>%s</url><dir>%s</dir><urlExceed>%s</urlExceed><dirExceed>%s</dirExceed></result>' % (
                len(task.get("urls")), len(task.get("dirs")), message.get('urlExceed', 0), message.get('dirExceed', 0)))
        response = make_response(responseMessage.toxml('gb2312'))
        response.headers['whatsup'] = 'content="succeed"'
        response.headers['Content-Type'] = 'text/html;charset=gb2312'
        return response

    @app.route("/adapter/tencent", methods=['POST'])
    def adapter_tencent():
        params = json.loads(request.data)
        task, passed, message = adapters.get_tencent_task(request.data, request.remote_addr)
        logger.debug('new tencent request{user:qq,remote_addr:%s}' % request.remote_addr)
        if passed:
            task['remote_addr'] = request.remote_addr
            task['serial_num'] = params.get('serial_num', '')
            task['request_time'] = params.get('request_time')
            task["URL_OVERLOAD_PER_HOUR"] = URL_OVERLOAD_PER_HOUR
            task["DIR_OVERLOAD_PER_HOUR"] = DIR_OVERLOAD_PER_HOUR
            task['type'] = 'tencent'
            splitter.process(db_session, task, True)
        return message

    @app.route("/adapter/tencent", methods=['GET'])
    def adapter_tencent_search():
        authentication.verify(USERNAME_TENCENT, PASSWORD_KEY_TENCENT, request.remote_addr)
        if request.args.get('begin_time') and request.args.get('end_time'):
            begin_time = request.args.get('begin_time')
            end_time = request.args.get('end_time')
            response = make_response(
                result_tencent.get_result(query_db_session, begin_time, end_time, USERNAME_TENCENT))
            response.headers['Content-Type'] = 'text/plain;charset=UTF-8'
            return response
        raise BadRequest("请求必须包含begin_time和end_time参数。")

    # ntese adapter
    @app.route("/ntese", methods=['GET', 'POST'])
    def adapter_ntese():
        try:
            ntease_task, passed, message = adapters.get_ntease_task(
                request.form if request.method == "POST" else request.args, request.remote_addr)
            if passed:
                ntease_task["remote_addr"] = request.remote_addr
                ntease_task["URL_OVERLOAD_PER_HOUR"] = URL_OVERLOAD_PER_HOUR
                ntease_task["DIR_OVERLOAD_PER_HOUR"] = DIR_OVERLOAD_PER_HOUR
                ntease_task['type'] = 'ntese'
                splitter.process(db_session, ntease_task, True)
            return doResponse(message)
        except Exception:
            logger.warn("ntease warning.", exc_info=sys.exc_info())
            return doResponse(
                '<item_id>%s</item_id><result>FAILURE</result><detail>ERROR:PostFailed</detail>' % ntease_task.get(
                    "callback").get("ntease_itemid"))

    @app.route('/snda_callback_test', methods=['GET', 'POST'])
    def snda_callback_test():
        '''
        盛大回调测试接口
        '''
        username = request.form.get('username')
        password = request.form.get('password')
        time = request.form.get('time')
        data = request.form.get('data')
        logger.debug("#########snda_callback_test: username is %s, password is %s, time is %s, data is %s" % (
            username, password, time, data))
        return 'ok'

    @app.route('/adapter/snda_refresh', methods=['GET', 'POST'])
    def adapter_snda():
        '''
        盛大刷新
        '''
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        time = request.form.get("time", "")
        info = "snda request %s with {user:%s,remote_addr:%s}" % (
            request.path, username, request.remote_addr)
        logging.debug(info)
        # 验证成功 则返回portal校验密码
        p_password = adapters.verify_snda(username, password, time)
        if not p_password:
            return jsonify({"success": False, "message": "WRONG_PASSWORD"}), 403
        # TODO 测试
        # p_password = 'ptyy@snda.com'
        task = load_task(request.form.get("task", "{}"))
        task['callback'] = {"url": SNDA_CALLBACK, "email": [], "acptNotice": True}
        # task['callback'] = {"url": SNDA_CALLBACK_DBUG, "email":[],"acptNotice":True}
        logging.debug('snda task is %s' % (task))
        ticket = authentication.verify(username, p_password, request.remote_addr)
        task["username"] = ticket["name"]
        task["isSub"] = ticket.get("isSub", False)
        task["parent"] = ticket.get("parent", ticket["name"])
        task["remote_addr"] = request.remote_addr
        task["URL_OVERLOAD_PER_HOUR"] = ticket["URL_OVERLOAD_PER_HOUR"]
        task["DIR_OVERLOAD_PER_HOUR"] = ticket["DIR_OVERLOAD_PER_HOUR"]
        task['type'] = 'snda'
        message = splitter_new.process(db_session, task, True)
        if message.get("urlExceed") or message.get("dirExceed"):
            raise gethTTPException(202, message)
        elif message.get("invalids"):
            raise gethTTPException(201, message)
        return jsonify(message)

    @app.route("/adapter/encrypt", methods=['POST'])
    def adapter_encrypt():
        params = json.loads(request.data)
        logger.debug('new encrypt request{user:%s,remote_addr:%s}' %
                     (params.get("username"), request.remote_addr))
        if adapters.is_verify_encrypt_receiver_failed(params):
            raise Forbidden("verify failed.")
        else:
            refresh_task = {"username": params.get("username", ""), "urls": params.get('urls', []),
                            "dirs": params.get('dirs', []), "remote_addr": request.remote_addr,
                            "URL_OVERLOAD_PER_HOUR": URL_OVERLOAD_PER_HOUR,
                            "DIR_OVERLOAD_PER_HOUR": DIR_OVERLOAD_PER_HOUR}
            refresh_task['type'] = 'encrypt'
            return jsonify(splitter.process(db_session, refresh_task))

    @app.route("/agentdRestart", methods=['POST'])
    def restart_agentd():
        ret_pid = subprocess.getstatusoutput(
            "ps -eo pid,cmd|grep agentd|grep -v grep|awk '{print $1}'")
        if not ret_pid[0]:
            ret_kill = subprocess.getstatusoutput("kill -9 %s" % ret_pid[1])
            if not ret_kill[0]:
                ret_restart = os.system(
                    "nohup /Application/bermuda3/bin/python /Application/bermuda3/bin/agentd &")
        return subprocess.getstatusoutput("ps ux | grep agentd |grep -v grep | awk '{print $9}'")[1]

    def doResponse(nodeStr):
        '''


        Parameters
        ----------
        nodeStr :

        Returns
        -------
        '''
        responseMessage = parseString('<fwif>%s</fwif>' % nodeStr)
        response = make_response(responseMessage.toxml('utf-8'))
        logger.debug('ntese response :%s' % responseMessage.toxml('utf-8'))
        response.headers['Content-Type'] = 'text/xml;charset=UTF-8'
        return response

    @app.route("/content/refresh/noc.jsp", methods=['GET'])
    def search_for_noc():
        result = query_db_session.rewrite.find_one()
        if result:
            return make_response('service is fine!')

    @app.route("/internal/taskStatusByUIdForPortal", methods=['POST', 'GET'])
    def get_task_status_by_id():
        # time range is from the begin of the day to now
        request_args = {}
        if request.method == 'POST':
            request_args = request.form
        elif request.method == 'GET':
            request_args = request.args
        # get the args
        username = request_args.get('username', '')
        parent = request_args.get('parent', '')
        is_sub = request_args.get('is_sub', '')
        start_time = request_args.get('start_time', '')
        end_time = request_args.get('end_time', '')
        # username should not empty
        if not username.strip():
            return jsonify({'is_success': False, 'error': 'has no username'})
        is_sub = True if is_sub.upper() == 'TRUE' else False
        # if is_sub False, means it is a main user, so username equals parent
        if not is_sub:
            parent = username
        else:
            if not parent.strip():
                return jsonify({'is_success': False, 'error': 'is_sub is true, but parent is empty'})
        if not start_time.strip() or not end_time.strip():
            return jsonify({'is_success': False, 'error': 'has no start_time or end_time'})
        # change the string to datetime
        try:
            start_time = datetime.datetime.strptime(start_time, "%Y-%m-%d %H:%M")
            end_time = datetime.datetime.strptime(end_time, "%Y-%m-%d %H:%M")
        except ValueError as e:
            return jsonify({'is_success': False, 'error': 'time format does not match: %Y-%m-%d %H:%M'})
        logger.info(
            'get task status by username, username: %s, parent: %s, is_sub: %s, start_time: %s, end_time: %s' % (
                username, parent, is_sub, start_time, end_time))
        result = get_task_count(username, parent, start_time, end_time, is_sub)
        return jsonify({'is_success': True, 'result': result})

    @app.route('/rewrite_query', methods=['GET', 'POST'])
    def rewrite_n_to_n():
        """
        according channel_name or rewrite_name, return the list of url, the channel_name is necessary rewrite_name is no necessary
        :return: like[{"_id":XXXX, "channel_name":XXXX, "channel_name_list":["xxxx","http://qsdf.com"]}]
        """
        # args = {"totalpage":0,"curpage":int(request.form.get("curpage",0)),"CHANNEL_NAME":request.form.get('CHANNEL_NAME', ''),"REWRITE_NAME":request.form.get('REWRITE_NAME', '')}
        # rewrite_list = get_rewrite_list(args)

        # username = request.form.get('username', '')
        # channel_name = request.form.get('channel_name', '')
        # receive data from remote
        result = request.data
        # parse the data
        p_result = load_task(result)

        # username = result.form.get('username', '')
        # channel_name = result.form.get('channel_name', '')
        username = p_result.get('username', '')
        channel_name = p_result.get('channel_name', '')
        # return "username:%s, channel_name:%s, %s" % (username, channel_name, result)
        if username != '':
            result_list = rewrite_query_n_to_n(username.strip(), channel_name.strip())
            app.logger.debug("result_list:%s" % result_list)
            return JSONEncoder().encode({'msg': 'ok', 'result': result_list})
        else:
            return json.dumps({'msg': 'error', 'result': 'username cannot None'})

    @app.route('/update_rewrite_new', methods=['GET', 'POST'])
    def update_rewrite_new():
        """
        this interface is used to receive data which will be used to udate the database and redis
        the format of receive data
        [{"id":XXXX, "username":XXXX, "channel_list":[xxxx,xxxx,xxx,xxxx]},
        {"username":XXXXX, "channel_list":[xxxx,xxxx,xxxx,xxxxx}]
        :return:{'msg':xxxx, 'result':xxxxxx}  json
        """
        # receive data from remote
        result = request.data
        # parse the data
        p_result = load_task(result)
        app.logger.debug(p_result)

        # return "hello"

        if p_result:
            for res in p_result:
                id = res.get("id", '')
                if id:
                    # if id is not '' , update the collection of rewrite_new and alter the redis
                    # this place to make a judge
                    update_res = update_rewrite_id(res)
                    update_res_p = load_task(update_res)
                    if update_res_p.get('msg', '') == 'ok':
                        continue
                    else:
                        return update_res
                else:
                    # insert the info the collection of rewrite_new and alter the redis
                    # this place to make a judge
                    update_res = update_rewrite_no_id(res)
                    update_res_p = load_task(update_res)
                    if update_res_p.get('msg', '') == 'ok':
                        continue
                    else:
                        return update_res
            return json.dumps({'msg': 'ok', 'result': 'update data success'})
        return json.dumps({'msg': 'error', 'result': 'channel list is None!'})

    @app.route('/delete_rewrite_new', methods=['GET', 'POST'])
    def del_rewrite_new():
        """
        delete data from mongo, and update the redis
        the format of receive data
        [{"id":XXXX, "username":XXXX, "channel_list":[xxxx,xxxx,xxx,xxxx]},
        {"id":XXXX, "username":XXXX, "channel_list":[xxxx,xxxx,xxx,xxxx]}
        ]

        :return:{'msg':xxxx, 'result':xxxxxx}  json
        """
        # receive data from remote
        result = request.data
        # parse the data
        p_result = load_task(result)
        if p_result:
            for res in p_result:
                id = res.get("id", '')
                if id:
                    # delete data which in mongo
                    # this place to make a judge
                    del_res = delete_rewrite_id(res)
                    del_res_p = load_task(del_res)
                    if del_res_p.get("msg", '') == 'ok':
                        continue
                    else:
                        return del_res
            return json.dumps({'msg': 'ok', 'result': 'delete data success!'})

        return json.dumps({'msg': 'error', 'result': 'channel list is None!'})

    @app.route('/isValidUrlByPortal', methods=['GET', 'POST'])
    def isValidUrlByPortal():
        """
        key, username, channel_name
        :return:
        """

        key = request.args.get('key', '')
        username = request.args.get('username', '')
        channel_name = request.args.get('channel_name', '')
        logger.debug('isValidUrlByPortal  key:%s, username:%s, channel_name:%s' %
                     (key, username, channel_name))
        flag = isValidChannelByPortal(username, channel_name)
        if flag:
            return "yes"
        else:
            return "no"

    @app.route('/isValidUrl', methods=['GET', 'POST'])
    def isValidUrl():
        """

        :return:
        """
        username = request.args.get('username', '')
        url = request.args.get('url', '')
        isValid, is_multilayer, channel_code, ignore_case = rcmsapi.isValidUrl(username, url)
        return json.dumps({'isValid': isValid, 'is_multilayer': is_multilayer, 'channel_code': channel_code,
                           'ignore_case': ignore_case})

    @app.route('/render_channels_rcms', methods=['GET', 'POST'])
    def get_render_channels_rcms():
        """

        :return:
        """
        username = request.args.get('username', '')
        if username:
            return json.dumps(OutSysToRedis().render_channels_rcms(username))
        else:
            return json.dumps({})

    def get_task_count(username, parent, start_time, end_time, is_sub):
        processing_task_count = 0
        finished_task_count = 0
        failed_task_count = 0
        invalid_task_count = 0
        if is_sub:
            processing_task_count = query_db_session.url.find(
                {'username': username, 'parent': parent, 'status': 'PROCESS',
                 'created_time': {'$gte': start_time, '$lte': end_time}}).count()
            finished_task_count = query_db_session.url.find(
                {'username': username, 'parent': parent, 'status': 'FINISHED',
                 'created_time': {'$gte': start_time, '$lte': end_time}}).count()
            failed_task_count = query_db_session.url.find({'username': username, 'parent': parent, 'status': 'FAILED',
                                                           'created_time': {'$gte': start_time,
                                                                            '$lte': end_time}}).count()
            invalid_task_count = query_db_session.url.find({'username': username, 'parent': parent, 'status': 'INVALID',
                                                            'created_time': {'$gte': start_time,
                                                                             '$lte': end_time}}).count()
        else:
            processing_task_count = query_db_session.url.find(
                {'parent': parent, 'status': 'PROCESS', 'created_time': {'$gte': start_time, '$lte': end_time}}).count()
            finished_task_count = query_db_session.url.find({'parent': parent, 'status': 'FINISHED',
                                                             'created_time': {'$gte': start_time,
                                                                              '$lte': end_time}}).count()
            failed_task_count = query_db_session.url.find(
                {'parent': parent, 'status': 'FAILED', 'created_time': {'$gte': start_time, '$lte': end_time}}).count()
            invalid_task_count = query_db_session.url.find(
                {'parent': parent, 'status': 'INVALID', 'created_time': {'$gte': start_time, '$lte': end_time}}).count()

        return {'PROCESS': processing_task_count, 'FAILED': failed_task_count, 'FINISHED': finished_task_count,
                'INVALID': invalid_task_count}

    def gethTTPException(code, message):
        hTTPException = HTTPException(message)
        hTTPException.code = code
        return hTTPException

    @app.route("/internal/update", methods=['POST'])
    def internal_refresh_preload():
        """
        1.对数据进行处理
        2.进行刷新
        3.保存到数据库（封装成预加载接口数据）
        4.等待router打包,在处理入库时,根据url找到3存在数据库中的信息,获取objectid,供下一步使用（用于一段时间内url不重复问题,重复对刷新没有影响,预加载）
        5.进行预加载,完成删除3号库中对应的信息()
        """
        result = internal_preload(request)

        if result.get("urlExceed") and result.get("dirExceed"):
            result["code"] = 3
        elif result.get("urlExceed"):
            result["code"] = 1
        elif result.get("dirExceed"):
            result["code"] = 2
        elif result.get("invalids"):
            result["code"] = 5
        else:
            result["code"] = 0
        return jsonify(result)

    @app.route("/internal/physical/refresh", methods=['POST'])
    def url_physical():
        '''

        '''
        try:
            if len(request.form) > 0:
                urls = load_task(request.form.get("urls", "[]"))

            else:
                data = load_task(request.data)
                urls = data.get('urls')
                if isinstance(urls, str):
                    urls = load_task(urls)

            pyurls_list = get_url_details(urls)

            logger.debug("physical list is {}".format(pyurls_list))
            queue.put_json2("physical_refresh", pyurls_list)
            return jsonify({"code": 200, "message": "ok"})
        except Exception:
            logger.debug("{}".format(traceback.format_exc()))
            return jsonify({"code": 500, "message": "error"})

    def get_url_details(urls):
        urls_list = []
        for url in urls:
            try:
                domain = get_channelname(url)
                code = getcode_from_redis(domain)
                if not code:
                    code = get_channel_code(domain)
                if domain and code:
                    urls_list.append({"id": get_uuid(), "channel_code": code,
                                      "domain": domain, "url": url, "newphysical": "newphysical"})
                else:
                    logger.debug("physical error url is ".format(url))
            except Exception:
                logger.debug("get url details physical {}".format(traceback.format_exc()))
        return urls_list

    def internal_preload(request):

        if len(request.form) > 0:
            request_data = request.form
            insert_dict = copy.deepcopy(request_data)
        else:
            request_data = load_task(request.data)
            insert_dict = copy.deepcopy(request_data)

        #request_id = str(ObjectId())
        # task_list = insert_dict.pop('task')['urls']
        # for url in task_list:
        #
        #     task_index = copy.deepcopy(insert_dict)
        #     task_index.setdefault('task',[])
        #
        #
        #     #url_id = hashlib.md5('%s_%s' % (url, time.time()).hexdigest())
        #
        #     #task_index['id'] = url_id
        #     task_index['url'] = url
        #     task_index['request_id'] = request_id
        #     db.refresh_preload.insert(task_index)

        refresh_task = request_data.pop('tasks')
        task_list_ll = []
        for refresh_url in refresh_task:
            # logger.debug(type(refresh_url))
            #refresh_url = load_task(refresh_url)
            task_list_ll.append(refresh_url['url'])
        #refresh_task['tasks'] = {}

        request_data['task'] = {}
        request_data['task']['urls'] = task_list_ll
        logger.debug(request_data)
        username = request_data.get('username', '')
        issub = request_data.get('username', False)
        if issub:
            parent = request_data.get('parent', username)
            isSub = True if request_data.get('isSub', 'False') in ['True', 'true'] else False
        logger.debug('request %s with {user:%s,remote_addr:%s}' %
                     (request.path, username, request.remote_addr))
        #tasks = load_task(request_data.get("task", "{}"))
        tasks = request_data.get("task", "{}")
        task = {}
        # for ts in tasks:
        #     if not task['urls']:
        #         task['urls'] = []
        #     else:
        #         task['urls'].append(ts['url'])
        task['urls'] = task_list_ll
        task["username"] = username
        ticket = authentication.internal_verify(username, request.remote_addr)
        task["remote_addr"] = request.remote_addr
        if issub:
            task["isSub"] = isSub
            task["parent"] = parent
        task["URL_OVERLOAD_PER_HOUR"] = ticket["URL_OVERLOAD_PER_HOUR"]
        task["DIR_OVERLOAD_PER_HOUR"] = ticket["DIR_OVERLOAD_PER_HOUR"]

        task['type'] = 'REFRESH_PRELOAD'

        logger.info('task:%s' % task)

        task_all = {}
        task_all['username'] = username
        task_all['urls'] = task.get('urls')
        task_all['dirs'] = task.get('dirs')
        task_all['update_urls'] = task.get('update_urls')
        task_all['purge_dirs'] = task.get('purge_dirs')
        message = {}

        urls_cc, urls_web = webluker_tools.get_urls(task['username'], task.get('urls'))
        dirs_cc, dirs_web = webluker_tools.get_urls(task['username'], task.get('dirs'))
        logger.debug("username:%s, urls_cc:%s, urls_web:%s, dirs_cc:%s,dirs_web:%s" %
                     (username, urls_cc, urls_web, dirs_cc, dirs_web))
        update_urls_cc, update_urls_web = webluker_tools.get_urls(
            task['username'], task.get('update_urls'))
        purge_dirs_cc, purge_dirs_web = webluker_tools.get_urls(
            task['username'], task.get('purge_dirs'))
        logger.debug("internal_receive_new username:%s, update_url_cc:%s, update_urls_web:%s, purge_dirs_cc:%s, "
                     "purge_dirs_web:%s" % (username, update_urls_cc, update_urls_web, purge_dirs_cc, purge_dirs_web))

        web_flag = urls_web or dirs_web or update_urls_web or purge_dirs_web
        web_task = {}
        if web_flag:
            task_new = {}
            task_new['urls'] = urls_web
            if update_urls_web:
                task_new['urls'].extend(update_urls_web)
            task_new['dirs'] = dirs_web
            if purge_dirs_web:
                task_new['dirs'].extend(purge_dirs_web)
            logger.debug(
                "/content/refresh send to webluker task urls:%s, dirs:%s" % (task_new['urls'], task_new['dirs']))
            task_new['username'] = username
            web_task['task_new'] = task_new
            web_task['task_all'] = task_all

        if isSub:
            if urls_cc or dirs_cc or update_urls_cc or purge_dirs_cc:
                task['urls'] = urls_cc
                task['dirs'] = dirs_cc
                if update_urls_cc:
                    task['update_urls'] = update_urls_cc
                if purge_dirs_cc:
                    task['purge_dirs'] = purge_dirs_cc
                task['web_task'] = web_task
                message = splitter_new.process(db_session, task, True)
        else:
            if urls_cc or dirs_cc or update_urls_cc or purge_dirs_cc:
                task['urls'] = urls_cc
                task['dirs'] = dirs_cc
                if update_urls_cc and len(update_urls_cc) > 0:
                    task['update_urls'] = update_urls_cc
                if purge_dirs_cc and len(purge_dirs_cc) > 0:
                    task['purge_dirs'] = purge_dirs_cc
                task['web_task'] = web_task
                message = splitter.process(db_session, task, True)
        if not message.get('r_id') and web_flag:
            r_id = None
            message = webluker_tools.post_data_to_webluker(task_new, task_all, r_id)

        request_id = message.get('r_id', str(ObjectId()))
        task_list = insert_dict.pop('tasks')
        for url_dict in task_list:
            task_index = copy.deepcopy(insert_dict)
            url_id = hashlib.md5('%s_%s' % (url_dict['url'], time.time())).hexdigest()
            task_index['url'] = url_dict['url']
            task_index['id'] = url_dict.get('id', url_id)
            task_index['r_id'] = request_id
            db.refresh_preload.insert(task_index)

        return message

    @app.route("/rep/request/result", methods=['GET', 'POST'])
    def rep_request_result():
        request_id = request.args.get('request_id', '')
        # logger.debug("-----------------------------request_id--{0}-----------".format(request_id))
        if not request_id:
            return json.dumps({'message': 'please put the right id'})
        try:
            request_message = get_request_by_request(request_id)

            now = datetime.datetime.now()
            task_create_time = request_message.get('created_time')
            check_time = (now - task_create_time).seconds
            task_tt = task_create_time.strftime("%Y-%m-%d %H:%M:%S %f")

            urls_list = get_urls_by_request(request_id)
            dev_list = {}
            all_result = []
            for url in urls_list:
                dev_count = dev_list.get(url.get('dev_id'))
                if dev_count:
                    countAll = dev_count
                else:
                    db_devs = get_devs_by_id(url.get('dev_id'))
                    devs = list(db_devs.get("devices").values())
                    try:
                        countAll = len([i for i in devs if i['code'] != 204 and i['type'] != 'FC'])
                    except KeyError:
                        countAll = len(devs)
                    dev_list[url.get('dev_id')] = countAll
                logger.debug("---------------------url--{0}".format(url))
                refresh_results = get_refresh_result_by_sessinId(url.get('u_id'))
                logger.debug("---refresh_results{0}".format(refresh_results))

                rep_res_dev = sorted(
                    refresh_results, key=lambda re_r: re_r.get('time'), reverse=False)
                ss_count = len([x for x in rep_res_dev if x['result'] == "200"])
                logger.debug("--------------sscount:{0},countAll:{1}".format(ss_count, countAll))
                #status = 'success' if ss_count / countAll > 0.9 else 'false'
                status = 'success' if (float(ss_count) / countAll) >= 0.9 else 'false'
                if status != 'success':
                    if check_time < 5 * 60:
                        status = 'running'

                all_result.append({'status': status, "session_id": str(url.get('u_id')), 'url': url.get('url'),
                                   'create_time': task_tt,
                                   'last_time': rep_res_dev[0].get('time').strftime(
                                       "%Y-%m-%d %H:%M:%S %f") if rep_res_dev else 'running'})
                try:
                    if ss_count != countAll:
                        err_message = {'request_id': request_id, 'url': url.get('url'), 'success': ss_count,
                                       'all': countAll, 'channelName': url.get('channel_name'), "session_id": str(url.get('u_id'))}
                        send_result_error(err_message)
                        pass  # 告警
                except Exception:
                    logger.debug('send email error {0}'.format(traceback.format_exc()))
            return json.dumps(all_result)
        except Exception:
            logger.debug('rep request error {0}'.format(traceback.format_exc()))
            return json.dumps({'code': 500, 'message': 'error'})

    @app.route("/subcenter/preload", methods=['POST', 'GET'])
    def subcenter_preload():

        sub_center_host = request.remote_addr
        logger.debug('subcenter_preload sub_center_host: %s' % (sub_center_host))
        # sub_center_host = '223.202.203.31'
        result = request.data
        logger.debug("subcenter_preload result:%s, request.form:%s" % (result, request.form))
        try:
            parse_result = json.loads(result)
            logger.debug("subcenter_preload branch center parse_result:%s" % parse_result)
        except Exception:
            logger.debug("subcenter_preload data error:%s" % e)
            #  need to add some codes
            return json.dumps({'msg': 'error', 'content': 'parse json data error:%s' % e})
        # receive data type, node_name
        edge_host = parse_result.get("target_url", None)
        if not edge_host:
            return json.dumps({'msg': 'error', 'content': 'edge host is None'})
        edge_host = edge_host.split(":")[1].strip("//")

        callback_params = parse_result.get("callback_params", None)
        if not callback_params:
            return json.dumps({'msg': 'error', 'content': 'callback_params is None'})

        ack_content = parse_result.get('edgeReturnBody', None)
        if not ack_content:
            return json.dumps({'msg': 'error', 'content': 'edgeReturnBody is None'})
            # return handing_failed_sub_result(callback_params, sub_center_host,
            # edge_host, branch_code)

        node_dic = {}
        date_time_now = datetime.datetime.now()
        try:
            try:
                nodes_body = json.loads(ack_content)
                for t in nodes_body['task_id']:
                    node_dic[t] = nodes_body['status']
                # obj_cert.ack_content = ack_content
                logger.debug("subcenter_preload cert subcenter_preload node_dic:%s" % node_dic)

                if not node_dic:
                    return json.dumps({'msg': 'error', 'content': 'can not get data '})
                else:
                    for param in callback_params:
                        Subcenter_preload.subcenter_udate_redis('cert_subcenter_result', param, db_s1, sub_center_host,
                                                                edge_host, int(list(node_dic.values())[0]), date_time_now)
                        res = Subcenter_preload.update_subcenter_result('cert_subcenter_result', db_s1, param,
                                                                        sub_center_host, edge_host, ack_content,
                                                                        int(list(node_dic.values())[0]), date_time_now)
                        if res:
                            return json.dumps({'msg': 'ok', 'content': 'branch reach edge device,insert data into mongo success'})
                        else:
                            return json.dumps({'msg': 'error', 'content': 'branch reach edge device,insert data into mongo success'})
            except Exception:

                logger.debug('subcenter_preload error:%s' % traceback.format_exc())
                branch_code = 503
                for param in callback_params:
                    Subcenter_preload.subcenter_udate_redis('cert_subcenter_result', param, db_s1, sub_center_host,
                                                            edge_host, branch_code, date_time_now)
                    res = Subcenter_preload.update_subcenter_result('cert_subcenter_result', db_s1, param, sub_center_host,
                                                                    edge_host, ack_content, branch_code, date_time_now)
                    if res:
                        return json.dumps({'msg': 'ok', 'content': 'branch can not reach edge device,insert data into mongo success'})
                    else:
                        return json.dumps({'msg': 'error', 'content': 'branch can not reach edge device,insert data into mongo failed'})
        except Exception:

            logger.debug("subcenter_preload[error]: %s" % traceback.format_exc())
            return json.dumps({'msg': 'error', 'content': 'error: %s' % e})

    @app.route("/cert/receiveSubCenterResult", methods=['POST', 'GET'])
    def sub_center_result_new():

        sub_center_host = request.remote_addr
        logger.debug('------------cert sub_cent_host----------%s' % (sub_center_host))
        # sub_center_host = '223.202.203.31'
        result = request.data
        logger.debug(
            "receiveSubCenterResult result type:%s, result:%s, request.form:%s" % (type(result), result, request.form))
        try:
            parse_result = load_task(result)
            logger.debug("receiver branch center parse_result:%s" % parse_result)
        except Exception:
            logger.debug("parse data error:%s" % e)
            #  need to add some codes
            return json.dumps({'msg': 'error', 'content': 'parse json data error:%s' % e})
        # receive data type, node_name
        edge_host = parse_result.get("target_url", None)
        if not edge_host:
            return json.dumps({'msg': 'error', 'content': 'edge host is None'})
        edge_host = edge_host.split(":")[1].strip("//")

        callback_params = parse_result.get("callback_params", None)
        if not callback_params:
            return json.dumps({'msg': 'error', 'content': 'callback_params is None'})

        ack_content = parse_result.get('edgeReturnBody', None)
        if not ack_content:
            return json.dumps({'msg': 'error', 'content': 'edgeReturnBody is None'})
            # return handing_failed_sub_result(callback_params, sub_center_host,
            # edge_host, branch_code)

        node_dic = {}
        date_time_now = datetime.datetime.now()
        try:
            try:
                nodes_body = load_task(ack_content)
                for t in nodes_body['task_id']:
                    node_dic[t] = nodes_body['status']
                # obj_cert.ack_content = ack_content
                logger.debug("receiver cert receiveSubCenterResult node_dic:%s" % node_dic)

                if not node_dic:
                    return json.dumps({'msg': 'error', 'content': 'can not get data '})
                else:
                    for param in callback_params:
                        Subcenter_cert.subcenter_udate_redis('cert_subcenter_result', param, db_s1, sub_center_host,
                                                             edge_host, int(list(node_dic.values())[0]), date_time_now)
                        res = Subcenter_cert.update_subcenter_result('cert_subcenter_result', db_s1, param,
                                                                     sub_center_host, edge_host, ack_content,
                                                                     int(list(node_dic.values())[0]), date_time_now)
                        if res:
                            return json.dumps(
                                {'msg': 'ok', 'content': 'branch reach edge device,insert data into mongo success'})
                        else:
                            return json.dumps(
                                {'msg': 'error', 'content': 'branch reach edge device,insert data into mongo success'})
            except Exception:

                logger.debug('getCodeFromData error:%s' % traceback.format_exc())
                branch_code = 503
                for param in callback_params:
                    Subcenter_cert.subcenter_udate_redis('cert_subcenter_result', param, db_s1, sub_center_host,
                                                         edge_host, branch_code, date_time_now)
                    res = Subcenter_cert.update_subcenter_result('cert_subcenter_result', db_s1, param, sub_center_host,
                                                                 edge_host, ack_content, branch_code, date_time_now)
                    if res:
                        return json.dumps(
                            {'msg': 'ok', 'content': 'branch can not reach edge device,insert data into mongo success'})
                    else:
                        return json.dumps({'msg': 'error',
                                           'content': 'branch can not reach edge device,insert data into mongo failed'})
        except Exception:

            logger.debug("receive SubCenterResult  error:%s" % traceback.format_exc())
            return json.dumps({'msg': 'error', 'content': ' error:%s' % e})

    @app.route("/subcenter/bestroad", methods=['POST', 'GET'])
    def get_best_road():
        if len(request.form) > 0:
            request_data = request.form
        else:
            request_data = load_task(request.data)
        branch_center_list = []
        branch_centers = get_subcenters()
        if branch_centers:
            branch_center_list = list(branch_centers.values())
        failed_dev_list = request_data.get('devices')
        map_t = {}
        try:
            for host in failed_dev_list:
                branch_list = []
                #host = failed_dev.get('host')
                branch_center = subcenter_factory.get('central_best_road' + host)
                # branch_center is exits
                if branch_center:
                    branch_redi_list = eval(branch_center)
                    if branch_redi_list and len(branch_redi_list):
                        for branch in branch_redi_list:
                            branch_list.extend(branch + ":" + str(21109))
                    else:
                        subcenter_factory.delete("central_best_road_" + host)
                        # subcenter_factory.delete("central_link_" + host + "_" + branch_center)
                        branch_list.extend(branch_center_list)
                else:
                    keys = subcenter_factory.keys("central_link_" + host + "*")
                    # have keys
                    logger.debug('get best road keys  %s' % (keys))
                    k_v = {}
                    if keys and len(keys) > 0:
                        for key in keys:
                            k_v[key] = subcenter_factory.get(key)  # int(subcenter_factory.get(key))
                        # 取时间最小的key

                        sub_min_list = sorted(k_v, key=lambda x: k_v[x])
                        flag = False
                        # if len(sub_min_list) >= FIRST_HOST:
                        #     send_dev = sub_min_list[:FIRST_HOST]
                        # else:
                        #     send_dev = sub_min_list
                        # logger.debug('get best road send_dev %s'%(send_dev))
                        best_road_sor_list = []
                        for key in sub_min_list:
                            if len(best_road_sor_list) >= FIRST_HOST:
                                break
                            else:
                                logger.debug('get best road key is %s' % (
                                    key.rsplit('_', 1)[1] + ":" + str(21109)))
                                logger.debug('get best road branch_center_list %s' %
                                             (branch_center_list))
                                if key.rsplit('_', 1)[1] + ":" + str(21109) in branch_center_list:
                                    branch_list.append(key.rsplit('_', 1)[1] + ":" + str(21109))
                                    best_road_sor_list.append(key.rsplit('_', 1)[1])
                                    flag = True
                        if not flag:
                            branch_list.extend(branch_center_list)
                        else:
                            logger.debug(' set host: %s best road is %s' %
                                         (host, best_road_sor_list))
                            subcenter_factory.set('central_best_road_' + host, best_road_sor_list)
                            logger.debug('best road is %s' %
                                         subcenter_factory.get('central_best_road_' + host))
                            subcenter_factory.expire('central_best_road_' + host, EXPIRETIME_BEST)
                            # branch_list.extend(best_road_sor_list)
                    else:
                        branch_list.extend(branch_center_list)

                map_t[host] = branch_list
            logger.info('-------best_road------map_t-------------------%s' % (map_t))
        except Exception:
            logger.debug('get_best_road_v error:%s, host:%s' % (traceback.format_exc(), host))
        return json.dumps(map_t)

    @app.route("/subcenter/refresh", methods=['POST', 'GET'])
    def sub_center_refresh_result():
        sub_data = request.data
        try:
            parse_result = load_task(sub_data)
            logger.debug("receiver branch center parse_result:%s" % parse_result)
        except Exception:
            logger.debug("parse data error:%s" % e)
            #  need to add some codes
            return json.dumps({'msg': 'error', 'content': 'parse json data error:%s' % e})
        # receive data type, node_name
        edge_host = parse_result.get("target_url", None)
        if not edge_host:
            logger.debug("dont have edge_host error")
            return json.dumps({'msg': 'error', 'content': 'edge host is None'})

        callback_params = parse_result.get("callback_params", None)
        if not callback_params:
            logger.debug("dont have callback_params error")
            return json.dumps({'msg': 'error', 'content': 'callback_params is None'})

        content = parse_result.get('edgeReturnBody', None)
        if not content:
            logger.debug("dont have edgeReturnBody error")
            return json.dumps({'msg': 'error', 'content': 'edgeReturnBody is None'})
            # return handing_failed_sub_result(callback_params, sub_center_host,
            # edge_host, branch_code)

        callback_params_list = parse_result.get('callback_params', [])
        sub_center_host = request.remote_addr
        logger.debug('------------sub_cent_host----------%s' % (sub_center_host))
        # sub_center_host = '127.0.0.1'
        edge_host = edge_host.split(":")[1].strip("//")

        results = get_refresh_result(content)
        date_time_now = datetime.datetime.now()
        # request_id = callback_params_list[0]
        # create_time = db_s1['subcenter_refresh_task'].find_one({"r_id": request_id}).get("created_time")

        task_id = callback_params_list[0]
        request_id = callback_params_list[1]
        # create_time = db_s1['subcenter_refresh_task'].find_one({"r_id": request_id}).get("created_time")
        create_time = db_s1['subcenter_refresh_task'].find_one(
            {"_id": ObjectId(task_id)}).get("created_time")

        # create_time_timestamp = time.mktime(create_time.timetuple()*1000)
        # edge_return_time_timestamp = time.mktime(date_time_now.timetuple()*1000)
        # consume_time = edge_return_time_timestamp - create_time_timestamp
        # create_time_second = create_time.second
        # create_time_microsecond = create_time.microsecond
        # date_time_now_second = date_time_now.second
        # date_time_now_microsecond = date_time_now.microsecond
        # consume_time = round((date_time_now_second-create_time_second)*1000 + (date_time_now_microsecond-create_time_microsecond))
        # subcenter_factory.set("central_link_" + edge_host + "_" + sub_center_host, consume_time)
        # subcenter_factory.expire("central_link_" + edge_host + "_" + sub_center_host, EXPIRETIME)
        # request_id = callback_params_list[0]
        consume_time = (date_time_now - create_time).total_seconds()
        url_id_list = callback_params_list[2:]
        uniqui_id_list = []
        for uid in url_id_list:
            uniqui_id_list.append(uid + "_" + sub_center_host + "_" + edge_host)
        logger.debug("get uniqui_is %s" % (uniqui_id_list))
        # for x in url_id_list:
        #     result_x = db_s1.subcenter_refresh_result.find_one(
        #         {'edge_host': edge_host, 'subcenter_host': sub_center_host, 'uid': x})
        #     if not result_x:
        #         logger.debug({'fail':'fail','edge_host': edge_host, 'subcenter_host': sub_center_host, 'uid': x})
        #         logger.debug("sub_center_refresh_result NONONONONON edge_host: %s|| sub_center_host: %s|| x: %s" % (
        #         edge_host, sub_center_host, x))
        #     else:
        #         logger.debug({'sucesss':'sucesss','edge_host': edge_host, 'subcenter_host': sub_center_host, 'uid': x})

        # logger.debug('uniqui_id_list %s'%(uniqui_id_list))
        # resutl = db_s1['subcenter_refresh_result'].update(
        #     {"unique_id": {"$in": uniqui_id_list}},
        #     {"$set": {"edge_result": 200}},multi=True)
        # logger.debug('db update restult %s||edge_host:%s,subcenter_host:%s,uid:%s'%(resutl,edge_host,sub_center_host,url_id_list))

        if results.get('status') == 'failed':
            # if sub_center_host == subcenter_factory.get('central_best_road' + edge_host):
                # subcenter_factory.delete("central_best_road_" + edge_host)#不自动删除最优路径,设置为10s自动删除
            subcenter_factory.delete("central_link_" + edge_host + "_" + sub_center_host)

            # db_s1['subcenter_refresh_result'].update_many(
            #    {"unique_id": {"$in": uniqui_id_list}},{"$set": {"edge_result": 503, "finish_time": date_time_now, 'consume_time': consume_time}})
            # db_s1['subcenter_refresh_result'].update_many(
            #    {"unique_id": {"$in": uniqui_id_list}},{"$set": {"edge_result": 503, "finish_time": date_time_now, 'consume_time': consume_time,'xml_body':results.get('xml_body')}})
            fail_mq_result = db_s1['subcenter_refresh_result'].update_many(
                {"unique_id": {"$in": uniqui_id_list}}, {
                    "$set": {"edge_result": 503, "finish_time": date_time_now, 'consume_time': consume_time,
                             'xml_body': results.get('xml_body')}})
            logger.debug('fail_mq_result %s' % (fail_mq_result))
            return json.dumps({'msg': 'sucess', 'content': 'server success'})

            # db_s1['subcenter_refresh_result'].update_many(
            #     {'r_id': request_id, "edge_host": edge_host, 'subcenter_host': sub_center_host,
            #      "uid": {"$in": url_id_list}}, {"$set": {"edge_result": 503, 'finish_time': date_time_now,'consume_time':consume_time}})
        else:
            # rid = results.get('request_id')
            # create_time = db_s1['subcenter_refresh_task'].find_one({"r_id": rid}).get("created_time")
            # create_time_timestamp = time.mktime(create_time.timetuple())
            # edge_return_time_timestamp = time.mktime(date_time_now.timetuple())
            # consume_time = edge_return_time_timestamp - create_time_timestamp
            #
            # subcenter_factory.set("central_link_" + edge_host + "_" + sub_center_host, consume_time)
            # subcenter_factory.expire("central_link_" + edge_host + "_" + sub_center_host, EXPIRETIME)
            #
            # url_id_list = callback_params_list[1:]
            # db_s1['subcenter_refresh_result'].update_many(
            #     {"edge_host": edge_host, 'subcenter_host': sub_center_host,
            #      "uid": {"$in": url_id_list}},
            #     {"$set": {"edge_result": 200, "finish_time": date_time_now, 'consume_time': consume_time}})
            #
            # return  json.dumps({'msg': 'sucess', 'content': 'server success'})
            # rid = results.get('request_id')
            success_list = results.get('code_200')
            fail_list = results.get('code_514')
            # logger.debug("------------------------------")
            #
            # create_time = db_s1['subcenter_refresh_task'].find_one({"r_id": request_id}).get("created_time")
            #
            # create_time_timestamp = time.mktime(create_time.timetuple())
            # edge_return_time_timestamp = time.mktime(date_time_now.timetuple())
            # consume_time = edge_return_time_timestamp - create_time_timestamp

            subcenter_factory.set("central_link_" + edge_host + "_" + sub_center_host, consume_time)
            subcenter_factory.expire("central_link_" + edge_host +
                                     "_" + sub_center_host, EXPIRETIME)
            # x_num = db_s1['subcenter_refresh_result'].find(
            #             {"edge_host": edge_host, 'subcenter_host': sub_center_host, "uid": {"$in": success_list}}).count()
            # logger.debug("------x_num: %s---len(success_list): %s-----len(fail_list): %s------" % (x_num, len(success_list), len(fail_list)))

            if success_list:
                success_uid_list = []
                for uid in success_list:
                    success_uid_list.append(uid + "_" + sub_center_host + "_" + edge_host)
                logger.debug("get success_uid_list %s" % (success_uid_list))
                # db_s1['subcenter_refresh_result'].update_many(
                #    {"unique_id": {"$in": success_uid_list}}, {"$set": {"edge_result": 200, "finish_time": date_time_now,'consume_time':consume_time}})
                sucess_list_result_m = db_s1['subcenter_refresh_result'].update_many(
                    {"unique_id": {"$in": success_uid_list}},
                    {"$set": {"edge_result": 200, "finish_time": date_time_now, 'consume_time': consume_time}})
                logger.debug('sucess_list_mq %s' % (sucess_list_result_m))
            if fail_list:
                fail_uid_list = []
                for uid in fail_list:
                    fail_uid_list.append(uid + "_" + sub_center_host + "_" + edge_host)
                logger.debug("get fail_uid_list %s" % (fail_uid_list))
                # db_s1['subcenter_refresh_result'].update_many(
                #    {"unique_id": {"$in": fail_uid_list}},
                #    {"$set": {"edge_result": 514, "finish_time": date_time_now, 'consume_time': consume_time}})
                fail_list_mq = db_s1['subcenter_refresh_result'].update_many(
                    {"unique_id": {"$in": fail_uid_list}},
                    {"$set": {"edge_result": 514, "finish_time": date_time_now, 'consume_time': consume_time}})
                logger.debug('fail_list_mq %s' % (fail_list_mq))
            for uid in success_list:
                # # if db_s1['subcenter_refresh_result'].find_one({'r_id': rid, "uid": uid}, {"status": 1, "_id": 0}).get(
                # #         "status") == "success":
                # #     continue
                # # edge_host_list = db_s1['subcenter_refresh_result'].update({'r_id': rid, "uid": uid, "edge_result": 200},
                # #                                                         {"edge_host": 1})
                # # task_fail_list = set([edge_host['edge_host'] for edge_host in edge_host_list])
                # # if task_fail_list == set(fail_edge_list['fail_edge_list']):
                # #     db_s1['subcenter_refresh_result'].update({'r_id': rid, "uid": uid}, {"$set": {"status": "success"}})
                # #     db.url.update({"uid": uid}, {"$set": {"status": "FINISHED"}})
                # # SUBCENTER_REFRSH_UID = redisfactory.getDB(3)
                # # subcenter_expire_time = 60 * 15
                # #edge_host
                # dev_list = SUBCENTER_REFRSH_UID.get('sub_'+uid)
                # dev_list = eval(dev_list)
                # #logger.debug(type(dev_list))
                # #logger.debug(dev_list)
                #
                # if not  dev_list:
                #     continue
                # else:
                #     dev_set = set(dev_list)
                #     #dev_set.remove(edge_host)
                #     dev_set = dev_set - set([edge_host])
                #     logger.debug("---------------%s------------%s"%('sub_'+uid,list(dev_set)))
                #     #logger.debug(dev_set)
                #     SUBCENTER_REFRSH_UID.set('sub_'+uid,list(dev_set))
                #     if  len(dev_set) < 1:
                #         logger.debug('subcent refresh success id is %s'%(uid))
                #         db.url.update({"uid": ObjectId(uid)}, {"$set": {"status": "FINISHED"}})
                set_edge_device(SUBCENTER_REFRSH_UID, uid, edge_host)
        return json.dumps({'msg': 'sucess', 'content': 'server success'})

    return app


# class JSONEncoder(json.JSONEncoder):
#     """
#     solve ObjectId('57515b0a2b8a681de5b0612b') is not JSON serializable
#     """
#
#     def default(self, o):
#         if isinstance(o, ObjectId):
#             return str(o)
#         return json.JSONEncoder.default(self, o)


r_app = create_app(db_session(), query_db_session())

if __name__ == "__main__":
    create_app(db_session(), query_db_session()).run(host='0.0.0.0', port=8000)
