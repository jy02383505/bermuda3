#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
Created on 2012-3-1

@author: wenwen
'''
from core import redisfactory
import urllib.request, urllib.parse, urllib.error
import simplejson as json
from werkzeug.exceptions import Forbidden, Unauthorized, HTTPException
from core.models import URL_OVERLOAD_PER_HOUR, DIR_OVERLOAD_PER_HOUR, PRELOAD_URL_OVERLOAD_PER_HOUR
from util import log_utils
from .database import query_db_session
import traceback

db = query_db_session()

user_cache = redisfactory.getDB(2)  # redis存储的临时数据

CHECKIN_URL = "https://portal.chinacache.com/public-api/checkin.action?%s"  # 通过portal验证
CACHE_TIMEOUT = 1800

logger = log_utils.get_receiver_Logger()

def addCache(user_key, ticket):
    user_cache.set(user_key, ticket)
    user_cache.expire(user_key, CACHE_TIMEOUT)


def verify(username, password, remote_addr):
    '''
        用户验证

    Parameters
    ----------
    username : 用户名
    password : 密码
    remote_addr : 远程地址

    Returns
    -------

    CHECKIN_URL  通过portal验证的URL
    portal返回:
    '{"rcmsid":"2922","result":"SUCCESS","info":"","whitelist":[],"isSub":false,"parent":""}'
    user_cache   redis存储的临时数据，在 2 库
    db           mongodb overloads_config
    URL_OVERLOAD_PER_HOUR = 10000
    DIR_OVERLOAD_PER_HOUR = 100
    '''

    # if username:
    #     username = username.lower()

    user_key = username + password + remote_addr
    ticket = user_cache.get(user_key)
    if not ticket:
        try:
            user = json.loads(
                urllib.request.urlopen(CHECKIN_URL % urllib.parse.urlencode({"username": username, "pwd": password, "ignoreCase": False})).read())
        except Exception:
            logger.error('verify [error]: %s' % (traceback.format_exc()))
            logger.debug(CHECKIN_URL % urllib.parse.urlencode({"username": username, "pwd": password}))
            logger.debug(urllib.request.urlopen(CHECKIN_URL % urllib.parse.urlencode({"username": username, "pwd": password})).read())
        if user.get('result') == 'SUCCESS':
            user_config = db.overloads_config.find_one({"USERNAME": username})
            if user_config == None:
                user_config = {}
            ticket = {"name" : username, "parent": user.get('parent') if user.get('isSub') else username, "isSub": user.get('isSub'), "pass": True,
                      "URL_OVERLOAD_PER_HOUR": user_config.get("URL", URL_OVERLOAD_PER_HOUR),
                      "DIR_OVERLOAD_PER_HOUR": user_config.get("DIR", DIR_OVERLOAD_PER_HOUR),
                      "PRELOAD_URL_OVERLOAD_PER_HOUR": user_config.get("PRELOAD_URL", PRELOAD_URL_OVERLOAD_PER_HOUR)}
            if user.get('whitelist'):
                if remote_addr not in user.get('whitelist'):
                    ticket = {"name": username, "pass": False, "info": "%s not in whitelist" % remote_addr}
        else:
            ticket = {"name": username, "pass": False, "info": user.get("info")}
        addCache(user_key, json.dumps(ticket))
    else:
        ticket = json.loads(ticket)
    if not ticket.get("pass"):
        if ticket.get("info") == "NO_USER_EXISTS":
            raise Forbidden(ticket.get("info"))
        elif ticket.get("info") == "INPUT_ERROR":
            raise Unauthorized(ticket.get("info"))
        else:
            hTTPException =  HTTPException(ticket.get("info"))
            hTTPException.code = 402
            raise hTTPException
    return ticket


def internal_verify(username, remote_addr):
    user_key = username + remote_addr
    try:
        ticket = user_cache.get(user_key)
        if not ticket:
            user_config = db.overloads_config.find_one({"USERNAME": username})
            if user_config == None:
                user_config = {}
            ticket = {"name": username, "pass": True,
                      "URL_OVERLOAD_PER_HOUR": user_config.get("URL", URL_OVERLOAD_PER_HOUR),
                      "DIR_OVERLOAD_PER_HOUR": user_config.get("DIR", DIR_OVERLOAD_PER_HOUR),
                      "PRELOAD_URL_OVERLOAD_PER_HOUR": user_config.get("PRELOAD_URL", PRELOAD_URL_OVERLOAD_PER_HOUR)}
            addCache(user_key, json.dumps(ticket))
        else:
            ticket = json.loads(ticket)
        return ticket
    except:
        return {"name": username, "pass": True, "URL_OVERLOAD_PER_HOUR": URL_OVERLOAD_PER_HOUR,
                "DIR_OVERLOAD_PER_HOUR": DIR_OVERLOAD_PER_HOUR}
