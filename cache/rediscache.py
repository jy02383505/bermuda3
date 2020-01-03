__author__ = 'root'
#!/usr/bin/env python
# -*- coding: utf-8 -*-

import core.redisfactory as redisfactory,simplejson as sjson
#import core.query_result as query_result
from core import query_result
from util import log_utils
import traceback
import datetime
import imp
imp.reload(redisfactory)

'''
1=post BlackList , preload_cache
2=user_cache
3=search result_cache
4=splitter COUNTER_CACHE
8=RegexConfig_cache
10 = device_BU
11=firstlayer_cache
12=device_cache
13=channels_cache
15=REWRITE_CACHE
5=PRELOAD_DEVS
6=PORTAL_CACHE
'''
portal_cache  =redisfactory.getDB(6)# add new cache db
firstlayer_cache = redisfactory.getDB(11)
device_cache = redisfactory.getDB(12)
channels_cache = redisfactory.getDB(13)

COUNTER_CACHE = redisfactory.getDB(4)
BLACKLIST = redisfactory.getDB(1)
REWRITE_CACHE = redisfactory.getDB(15)
REGEXCONFIG = redisfactory.getDB(8)


USERNAME_LIST_KEY='usernames'

CACHE_TIME_OUT=24*60*60

logger = log_utils.get_redis_Logger()

DEVICES_PREFIX='d_by_%s'
CHANNELS_PREFIX='c_by_%s'
FIRSTLAYER_DEVICES_PREFIX='fd_by_%s'
USERINFO_PORTAL_PREFIX='up_by_%s'
CHANNELS_PORTAL_PREFIX='cp_by_%s'
CHANNELS_BLACK='black_%s'

USERCHANNELS_UPDATE='userchannels'
CHANNEL_DEVICES_UPDATE='channel_devices'
CHANNEL_FIRSTDEVICES_UPDATE='channel_firstlayer'
PORTAL_UPDATE='portals'

PORTAL_USER_BATCH_SIZE=100

def isFunctionUser(username):
    try:
        return portal_cache.exists(CHANNELS_PORTAL_PREFIX % username)
    except Exception:
        logger.error(traceback.format_exc())
        return False

def counted(fn):
    def wrapper(*args, **kwargs):
        try:
            wrapper.called+=1
            return fn(*args, **kwargs)
        finally:
            if (len(args)>2):
                print('%s %s was called %i times, channel code is %s, is not firstlayer:%s' % (datetime.datetime.now(),fn.__name__, wrapper.called,args[0],args[1]))
            else:
                print('%s %s was called %i times, username is :%s' % (datetime.datetime.now(),fn.__name__, wrapper.called,args[0]))
    wrapper.called= 0
    wrapper.__name__= fn.__name__
    return wrapper
def derct_channel(channel_obj):
    channel_obj['is_valid'] = True
    channel_obj['ignore_case'] = False
    # old logic: if db.channel_ignore.find_one({"CHANNEL_NAME":channel_name}) else False
    channel_str_utf8 = sjson.JSONEncoder().encode(channel_obj)
    return channel_str_utf8
@counted
def refresh_user_channel(username,channels_arr):
    channels_map={}
    for channel in channels_arr:
        channel_utf8 = derct_channel(channel)
        channels_map.setdefault(channel.get('name'),channel_utf8)
    channels_cache.watch()

    pipe=channels_cache.pipeline()
    pipe.delete(CHANNELS_PREFIX % username)
    if channels_map:
        pipe.hmset(CHANNELS_PREFIX % username,channels_map)
    pipe.execute()

        # channels_cache.expire(CHANNELS_PREFIX % username,CACHE_TIME_OUT)
    return channels_map
    # print("refresh redis,current channels_cache connection num of redis==%s, %s" % (str(channels_cache.info().get("connected_clients")),username))

@counted
def refresh_channel_devices(channel_code,isNotfirst,devices_arr):
    devices_map={}
    for device in devices_arr:
        device_name = device.get('name')
        try:
            # device_type = query_result.get_device_type_by_mongo(device_name)
            device_type = device_cache.hmget("DEVICE_TYPE", device.get('name'))
            device['type'] = device_type[0]
        except Exception:
            logger.error('refresh_channel_devices [error]: %s' % (traceback.format_exc()))
        device_utf8 =sjson.JSONEncoder().encode(device)
        devices_map.setdefault(device_name,device_utf8)

    if devices_map:
        if isNotfirst:
            pipe = device_cache.pipeline()
            pipe.delete(DEVICES_PREFIX % channel_code)
            pipe.hmset(DEVICES_PREFIX % channel_code,devices_map)
            pipe.execute()
        else:
            pipe = firstlayer_cache.pipeline()
            pipe.delete(FIRSTLAYER_DEVICES_PREFIX % channel_code)
            pipe.hmset(FIRSTLAYER_DEVICES_PREFIX % channel_code,devices_map)
            pipe.execute()
    else:
        if isNotfirst:
            pipe = device_cache.pipeline()
            pipe.delete(DEVICES_PREFIX % channel_code)
            pipe.execute()
        else:
            pipe = firstlayer_cache.pipeline()
            pipe.delete(FIRSTLAYER_DEVICES_PREFIX % channel_code)
            pipe.execute()

    return devices_map

def refresh_channels_portal(username,channels_arr):
    channels_map={}
    for channel in channels_arr:
        channel_utf8 =sjson.JSONEncoder().encode(channel)
        channels_map.setdefault(channel.get('channelName'),channel_utf8)
    if channels_map:
        pipe = portal_cache.pipeline()
        pipe.delete(CHANNELS_PORTAL_PREFIX % username)
        pipe.hmset(CHANNELS_PORTAL_PREFIX % username,channels_map)
        pipe.execute()
    return channels_map
    # print("refresh redis,current refresh_channels_portal connection num of redis==%s,%s" % (str(portal_cache.info().get("connected_clients")),username))
def refresh_customer_portal(mapping):
    if mapping:
        portal_cache.mset(mapping)
    # else:
    #     customer_utf8 =sjson.JSONEncoder().encode(customer_obj)
    #     portal_cache.set(USERINFO_PORTAL_PREFIX % username,customer_utf8)
    # return mapping
    # print("refresh redis,current refresh_customer_portal connection num of redis==%s,%s" % (str(portal_cache.info().get("connected_clients"))),username)
def refresh_user_channel_portal(username,userinfo_str):
    portal_cache.set(USERINFO_PORTAL_PREFIX % username,userinfo_str)
    return userinfo_str

def clear_redis():
    # channels_cache.delete(USERNAME_LIST_KEY)
    firstlayer_cache.flushdb()
    device_cache.flushdb()
    channels_cache.flushdb()
def append_to_channel_cache(key,value):
    try:
        channels_cache.sadd(USERNAME_LIST_KEY,value)
    except Exception:
        logger.error('append_to_cache error,can not connect redis')
        logger.error(traceback.format_exc())
        return ''

def read_from_redis(redis_prefix,redis_suffix='',key_name=''):
    '''
    Arguments:
        redis_prefix: 'c_by_%s'
    
    Keyword Arguments:
        redis_suffix: username # cybeye
        key_name: channel_name # http://*.garri.net
    call_example: channel = rediscache.read_from_redis(rediscache.CHANNELS_PREFIX, username, getExtensiveDomainName(channel_name))
    '''
    try:
        if redis_prefix==CHANNELS_PREFIX:
            if key_name:
                return channels_cache.hget(CHANNELS_PREFIX % redis_suffix, key_name)
            return channels_cache.hvals(redis_prefix%redis_suffix)
        elif redis_prefix==CHANNELS_PORTAL_PREFIX:
            if key_name:
                return portal_cache.hget(CHANNELS_PORTAL_PREFIX % redis_suffix, key_name)
            return portal_cache.hvals(redis_prefix%redis_suffix)
        elif redis_prefix==DEVICES_PREFIX:
            return device_cache.hvals(redis_prefix%redis_suffix)
        elif redis_prefix==FIRSTLAYER_DEVICES_PREFIX:
            return firstlayer_cache.hvals(redis_prefix%redis_suffix)
        elif redis_prefix==USERNAME_LIST_KEY:
            return channels_cache.smembers(USERNAME_LIST_KEY)
    except Exception:
        logger.error('read_channels_redis error,can not connect redis')
        logger.error(traceback.format_exc())
        return ''



