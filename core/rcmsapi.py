#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Created on 2011-5-26

@author: wenwen
"""
import simplejson as json

import traceback
import urllib

import logging, cache.util_redis_api as redisutil
from .database import query_db_session
from core.config import config
from urllib.parse import quote
from util import log_utils
from cache import api_portal


db = query_db_session()

# LOG_FILENAME = '/Application/bermuda3/logs/rcmsapi.log'
# logging.basicConfig(filename=LOG_FILENAME, format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s', level=logging.INFO)
#
# logger = logging.getLogger('rcmsapi')
# logger.setLevel(logging.DEBUG)

logger = log_utils.get_rcms_Logger()


RCMS_ROOT = config.get('rcmsapi', 'RCMS_ROOT')
PORTAL_ROOT = config.get('portalapi', 'CHANNEL_ROOT')
# RCMS_ROOT = 'http://rcmsapi.chinacache.com:36000'
CHANNELS_URL = RCMS_ROOT + '/customer/%s/channels'
DEVICES_URL = RCMS_ROOT + '/channel/%s/flexicache'
DEVICES_FIRSTLAYER_URL = RCMS_ROOT + '/channel/%s/flexicache/firstlayer'
CUSTOMER_URL = RCMS_ROOT + '/customer/%s'
DEVICE_STATUS_URL = RCMS_ROOT + "/device/name/%s/status"
DEVICE_BU_DEPARTMENT = RCMS_ROOT + "/device/%s"
CHANNELNAME = RCMS_ROOT + "/channelsByName?channelName=%s"

PORTAL_CHANNEL = api_portal.CHANNELS_URL

DEVICE_COUNT_0005 = 58
DEVICE_COUNT_7777 = 6

USER_CACHE = {}
CACHE_TIMEOUT = 600

def isValidUrl(username, url):
    if url.find('\n') >= 0 or len(url) > 1000:
        return False, False, 0 , False
    channel_name = get_channelname_from_url(url)
    if channel_name:
        return redisutil.isValidChannel(channel_name, username)
    else:
        return False, False, 0 , False


def getDevices(channel_code):
    if not channel_code:
        return []
    return redisutil.read_devices(channel_code)


def getFirstLayerDevices(channel_code):
    if not channel_code:
        return []
    return redisutil.read_firstLayerDevices(channel_code)


def get_channels(username):
    if not username:
        return []
    return redisutil.read_channels(username)

def get_channels_by_portal(username):
    logger.debug("get_channels %s "%(username))
    if not username:
        return []
    return redisutil.read_channels_by_portal(username)
# def getUser(username):
#     if not username:
#         return {}
#     return redisutil.read_customer(username)


# def getUser_portal(username):
#     if not username:
#         return {}
#     return redisutil.read_customer_portal(username)


def getDevStatus(devName):
    return json.loads(urllib.request.urlopen(DEVICE_STATUS_URL % devName).read())

def getBUDepartment(devName):
    return json.loads(urllib.request.urlopen(DEVICE_BU_DEPARTMENT % devName).read())

def getChannelCode(channelName):
    return json.loads(urllib.request.urlopen(CHANNELNAME % channelName).read())

def get_channelname_from_url(url):
    s = url.split('/', 3)
    if len(s) > 2:
        if s[2].find(':') > 0:
            s[2] = s[2].split(':')[0]
        return s[0] + '//' + s[2]
    else:
        return None

def isValidUrlByPortal(username, parent, url):
    '''
    username : 功能用户
    parent : 主账号
    url : 提交的URL

    Returns
    '''
    if url.find('\n') >= 0 or len(url) > 1000:
        return False, False, 0 , False
    channel_name = get_channelname_from_url(url)
    if isValidChannelByPortal(username, channel_name):
        return isValidUrl(parent, url)
    else:
        return False, False, 0 , False

def isValidChannelByPortal(username, channel_name):
    '''
    从PORTAL验证功能用户的频道权限
    https://portal-api.chinacache.com:444/api/internal/getBusinessInfo.do?username=
    shenma：用户
    Parameters
    ----------
    username : 功能用户
    channel_name : 频道名称

    Returns
    -------
    -------
    portal_cache   redis存储的临时数据，在 6 库

    '''
    key = redisutil.rediscache.CHANNELS_PORTAL_PREFIX % username
    try:
        if redisutil.portal_cache.hexists(key, channel_name):
            return True
        else:
            logger.debug('connect PORTAL CHANNELS_URL %s' % str(username))
            user = json.loads(urllib.request.urlopen(PORTAL_CHANNEL % str(username), timeout=10).read())
            businesses = user.get('businesses', [])
            for business in businesses:
                if not business.get('productCode', ''):
                    continue
                for channel in business.get('channels', []):
                    if redisutil.is_matched(channel.get('channelName'), channel_name):
                        channel_utf8 = json.JSONEncoder().encode(channel)
                        redisutil.portal_cache.hset(key, channel_name, channel_utf8)
                        return True
    except Exception:
        logger.error(traceback.format_exc())
    return False


def isValidChannelByPortal_new(key, username, channel_name):
    """

    :param key:
    :param username:
    :param channel_name:
    :return:
    """
    try:
        logger.debug('connect PORTAL CHANNELS_URL %s' % str(username))
        user = json.loads(urllib.request.urlopen(PORTAL_CHANNEL % str(username), timeout=10).read())
        businesses = user.get('businesses', [])
        for business in businesses:
            if not business.get('productCode', ''):
                continue
            for channel in business.get('channels', []):
                if redisutil.is_matched(channel.get('channelName'), channel_name):
                    channel_utf8 = json.JSONEncoder().encode(channel)
                    redisutil.portal_cache.hset(key, channel_name, channel_utf8)
                    return True
    except Exception:
        logger.debug("signal rcms error:%s" % e)
    return False


