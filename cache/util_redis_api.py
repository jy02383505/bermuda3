__author__ = 'root'
#!/usr/bin/env python
# -*- coding: utf-8 -*-
from . import rediscache

from util import log_utils
from .trans_outer_to_redis import OutSysToRedis
from .api_mongo import ApiMongo

api_mongo = ApiMongo()
import simplejson as sjson,traceback

logger = log_utils.get_redis_Logger()

portal_cache  =rediscache.portal_cache
firstlayer_cache = rediscache.firstlayer_cache
device_cache = rediscache.device_cache
channels_cache = rediscache.channels_cache

#this module invoked by rcmsapi.py,provide interfaces:read channel,device,firstlayer_device
#get an object in the following order:redis-->mongo-->rcms/portal

# def read_customer_rcms(username):
#     customer={}
#     logger.debug('user: request in read_customer: %s' % username)
#     try:
#         user_redis = channels_cache.get(rediscache.USERINFO_RCMS_PREFIX % username)
#         if not user_redis:
#             logger.debug('read customer not from redis instead from mongo')
#             userinfo_str = MongoToRedis().render_userInfo_mongo(username)
#             if not userinfo_str:
#                 logger.debug('read customer not from redis instead from rcms')
#                 userinfo_str = OutSysToRedis().render_userInfo_outer(username)
#             channels_cache.set(rediscache.USERINFO_RCMS_PREFIX % username,userinfo_str)
#             user_redis = channels_cache.hvals(rediscache.CHANNELS_PREFIX % username)
#         customer=sjson.JSONDecoder().decode(user_redis)
#         # self.channels_cache.expire(rediscache.CHANNELS_PREFIX % username,CACHE_TIMEOUT)
#         # channels = json.loads(channels)
#     except Exception,e:
#         logger.error(traceback.format_exc())
#         logger.error('redis api read_customer failed.username: %s,%s' % (username,traceback.format_exc()))
#
#     return customer

# def read_customer_portal(username):
#     logger.debug('user: request in read_customer_portal: %s' % username)
#     customer={}
#     try:
#         user_redis = portal_cache.get(rediscache.USERINFO_PORTAL_PREFIX % username)
#         if not user_redis:
#             logger.debug('read customer not from redis instead from mongo')
#             userinfo_str = MongoToRedis().render_portalUserInfo_mongo(username)
#             if not userinfo_str:
#                 logger.debug('read customer not from redis instead from portal')
#                 userinfo_str = OutSysToRedis().render_userInfo_outer(username,isRcms=False)
#             user_redis = portal_cache.get(rediscache.USERINFO_PORTAL_PREFIX % username)
#         customer=sjson.JSONDecoder().decode(user_redis)
#     except Exception,e:
#         logger.error(traceback.format_exc())
#         logger.error('redis api read_customer_portal failed.username: %s,%s' % (username,traceback.format_exc()))
#
#     return customer


'''
channel_redis structure:
    channels_by_user_name:{
      '15043':{'billingCode': '7438',
           'channelState': 'TRANSFER',
           'code': '15043',
           'customerCode': '2922',
           'customerName': 'sina_t',
           'multilayer': true,
           'name': 'http://ss10.sinaimg.cn',
           'productCode': '9010100000002',
           'transferTime': ''},
       channel_code2:{},
       channel_code3:{}
    }
'''
def read_channels(username):
    logger.debug('user: request in read_channels: %s' % username)
    channels=[]
    try:
        if username not in rediscache.read_from_redis(rediscache.USERNAME_LIST_KEY):
            channels_cache.sadd(rediscache.USERNAME_LIST_KEY,username)
            OutSysToRedis().render_channels_rcms(username)
        channel_redis = rediscache.read_from_redis(rediscache.CHANNELS_PREFIX,username)
        if not channel_redis:
            # channel_maps={}
            logger.debug('readChannels not from redis instead from rcms')
            if OutSysToRedis().render_channels_rcms(username):
                channels_cache.sadd(rediscache.USERNAME_LIST_KEY,username)
            channel_redis = rediscache.read_from_redis(rediscache.CHANNELS_PREFIX, username)
        else:
            logger.debug('read_channels get from redis')
        if channel_redis:
            for val in channel_redis:
                channels.append(sjson.JSONDecoder().decode(val))
            channels.sort(reverse=True, key=lambda x:x['name'].split('//')[1])
    except Exception:
        logger.error('redis api read_channels failed.username== %s ;exception==%s' % (username,traceback.format_exc()))
        logger.error(traceback.format_exc())
    return channels

def read_channels_by_portal(username):
    logger.debug('user: request in read_channels: %s' % username)
    channels=[]
    try:
        channel_redis = rediscache.read_from_redis(rediscache.CHANNELS_PORTAL_PREFIX,username)
        if not channel_redis:
            # channel_maps={}
            logger.debug('readChannels not from redis instead from portal')
            api_mongo.sync_user_channel_portals_by_username(username)
            channel_redis = rediscache.read_from_redis(rediscache.CHANNELS_PORTAL_PREFIX, username)
        else:
            logger.debug('read_channels get from redis')
        if channel_redis:
            for val in channel_redis:
                channels.append(sjson.JSONDecoder().decode(val))
            channels.sort(reverse=True, key=lambda x:x['name'].split('//')[1])
    except Exception:
        logger.error('redis api read_channels failed.username== %s ;exception==%s' % (username,traceback.format_exc()))
        logger.error(traceback.format_exc())
    return channels

'''
devices hash structure in redis:
devices_by_channel_code:{  'CNC-HQ-a-3S1':
    {
         'firstLayer': false,
         'host': '119.188.140.142',
         'name': 'CNC-HQ-a-3S1',
         'port': 21108,
         'serialNumber': '060105a3S1',
         'status': 'OPEN'
    },
    '':{}
   }

'''
def read_devices(channel_code):
    logger.debug('user: request in read_devices from channel code = %s' % str(channel_code))
    devices=[]
    devices_redis = rediscache.read_from_redis(rediscache.DEVICES_PREFIX ,channel_code)
    try:
        if not devices_redis:
            logger.debug('device miss in redis. for %s' % channel_code)
            # device_maps={}
            logger.debug('readDevices not from redis instead from rcms')
            OutSysToRedis().render_devices_rcms(channel_code)
            devices_redis = rediscache.read_from_redis(rediscache.DEVICES_PREFIX ,channel_code)
        else:
            logger.debug('read_devices of channel : %s get device is  from redis ' % str(channel_code))
        if devices_redis:
            for val in devices_redis:
                    devices.append(sjson.JSONDecoder().decode(val))
    except Exception:
        logger.error('get devices from redisapi failed. read_devices of channel: %s' % str(channel_code))
        logger.error(traceback.format_exc())

    return devices

def read_firstLayerDevices(channel_code):
    logger.debug('user: request in read_firstLayerDevices from channel code = %s' % channel_code)
    devices=[]
    devices_redis = rediscache.read_from_redis(rediscache.FIRSTLAYER_DEVICES_PREFIX , channel_code)
    try:
        if not devices_redis:
            logger.debug('device missed in redis. for %s' % channel_code)
            # device_maps={}
            logger.debug('readDevices not from redis instead from rcms')
            device_maps = OutSysToRedis().render_devices_rcms(channel_code,False)
            devices_redis = rediscache.read_from_redis(rediscache.FIRSTLAYER_DEVICES_PREFIX , channel_code)
        else:
            logger.debug('success:api of read_firstLayerDevices get from redis')
        if devices_redis:
            for val in devices_redis :
                    devices.append(sjson.JSONDecoder().decode(val))
    except Exception:
        logger.error('fail: get firstdevice from redisapi failed. read_firstLayerDevices of channel: %r' % channel_code)
        logger.error(traceback.format_exc())
    return devices

def is_matched(expected, actual):
    try:
        if expected.split('//')[1].startswith('*'):
            return expected[expected.index('*')+1:] in actual
        else:
            return expected == actual
    except:
        logger.warn("channel match error. expected:%s actual:%s" % (expected, actual))
        return False

def isValidChannel(channel_name,username):
    logger.info('call valid channel, user:%s, channel:%s'%(username, channel_name))
    rediscache.append_to_channel_cache(rediscache.USERNAME_LIST_KEY,username)
    channel = rediscache.read_from_redis(rediscache.CHANNELS_PREFIX, username, channel_name)
    if not channel:
        channel = rediscache.read_from_redis(rediscache.CHANNELS_PREFIX, username, getExtensiveDomainName(channel_name))
        logger.warn('username:%s, DomainName:%s' % (username, getExtensiveDomainName(channel_name)))
    channel_obj={}
    if not channel:
        if not isInvalids(username, channel_name):
            channels_user=OutSysToRedis().render_channels_rcms(username)
            for c in channels_user:
                if is_matched(c, channel_name):
                    channel_obj = sjson.loads(channels_user.get(c))
                    break
            if not channel_obj.get('is_valid',False):
                setInvalids(username, channel_name)
    else:
        channel_obj = sjson.loads(channel)
    return channel_obj.get('is_valid',False), channel_obj.get('multilayer',False), channel_obj.get('code',0), channel_obj.get('ignore_case', False)

def isInvalids(user,channel):
    try:
        isInvalid = channels_cache.hexists(rediscache.CHANNELS_BLACK % user, channel)
        logger.warn('isInvalids user:%s, channel:%s isInvalid:%s' %(user, channel, isInvalid))
        return isInvalid
    except Exception:
        logger.error('isInvalids error,can not connect redis')
        logger.error(traceback.format_exc())
        return False

def setInvalids(user,channel):
    try:
        channels_cache.hset(rediscache.CHANNELS_BLACK % user, channel, True)
        channels_cache.expire(rediscache.CHANNELS_BLACK % user, 300)
        logger.warn('setInvalids is user:%s, channel:%s'%(user, channel))
    except Exception:
        logger.error('setInvalids error,can not connect redis')
        logger.error(traceback.format_exc())

def getExtensiveDomainName(channel_name):
    startInt = channel_name.find('://')
    if startInt >0:
        startInt +=3
    else:
        startInt = 0
    endInt = channel_name.find('.')
    if endInt< 0:
        return channel_name
    domainName = channel_name[startInt:endInt]
    return channel_name.replace(domainName, '*', 1)
