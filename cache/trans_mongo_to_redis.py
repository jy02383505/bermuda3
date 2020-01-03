# -*- coding:utf-8 -*-
__author__ = 'root'
import simplejson as sjson
import rediscache,traceback
from util import log_utils
from .api_mongo import ApiMongo

logger = log_utils.get_redis_Logger()
'''
this class is an utility
to implement the data transition from mongodb to redis
caused by redis structure is different from mongodb
redis to save using key-hash,mongodb is saved key-value
'''

class MongoToRedis(object):
    def __init__(self):
        self.mongo_cache = ApiMongo()

    def render_userInfo_mongo(self,username):
        customer_mongo=self.mongo_cache.read_customer_mongo(username)
        return rediscache.refresh_user_rcms(username,customer_mongo)

    def render_channels_mongo(self,username):
        try:
            channels_mongo = self.mongo_cache.read_channels_mongo(username)
            return rediscache.refresh_user_channel(username,channels_mongo)
        except Exception:
            logger.error('render channel of user= %s from mongo to redis exception: %s' % (username,traceback.format_exc()))

    def render_devices_mongo(self,channel_code,isNotfirst=True):
        try:
            devices_map={}
            if isNotfirst:
                devices_mongo = self.mongo_cache.read_devices_mongo(channel_code)
            else:
                devices_mongo = self.mongo_cache.read_firstLayerDevices_mongo(channel_code)
            return rediscache.refresh_channel_devices(channel_code,isNotfirst,devices_mongo)

        except Exception:
            logger.error('render isnotfirst= (%s) device from mongo to redis exception: %s' % (str(isNotfirst),traceback.format_exc()))


    def render_portalUserInfo_mongo(self,username):
        try:
            customer_mongo=self.mongo_cache.read_portalChannels_mongo(username,isuser=True)
            return rediscache.refresh_user_channel_portal(username,sjson.JSONEncoder().encode(customer_mongo))
        except Exception:
            logger.error('render portalUser Info_mongo of user= %s from mongo to redis exception: %s' % (username,traceback.format_exc()))


    '''rfrsh_content:
        {
            rediscache.USERCHANNELS_UPDATE:[username1,username2],
            rediscache.CHANNEL_DEVICES_UPDATE:[channelcode1,channelcode2],
            rediscache.CHANNEL_FIRSTDEVICES_UPDATE:[channelcode1,channelcode2]
            'portals':[username1,username2]
        }
    '''
    # def refresh_redisCache(self,rfrsh_content):
    #     if not rfrsh_content:
    #         return
    #     logger.debug('begin   to refresh_redisCache from  notify_redis_update')
    #     try:
    #         userchannels=rfrsh_content.get(rediscache.USERCHANNELS_UPDATE)
    #         for username in userchannels:
    #             for key_channel in rediscache.channels_cache.hkeys(rediscache.CHANNELS_PREFIX % username):
    #                 rediscache.channels_cache.hdel(rediscache.CHANNELS_PREFIX % username,key_channel)
    #             self.render_channels_mongo(username)
    #
    #         channel_devices=rfrsh_content.get(rediscache.CHANNEL_DEVICES_UPDATE)
    #         for channelcode in channel_devices:
    #             for key_channel_code in rediscache.device_cache.hkeys(rediscache.DEVICES_PREFIX % channelcode):
    #                 rediscache.device_cache.hdel(rediscache.DEVICES_PREFIX % channelcode,key_channel_code)
    #             self.render_devices_mongo(channelcode)
    #
    #         channel_firstlayer=rfrsh_content.get(rediscache.CHANNEL_FIRSTDEVICES_UPDATE)
    #         for channelcode in channel_firstlayer:
    #             for key in rediscache.device_cache.hkeys(rediscache.FIRSTLAYER_DEVICES_PREFIX % channelcode):
    #                 rediscache.firstlayer_cache.hdel(rediscache.FIRSTLAYER_DEVICES_PREFIX % channelcode,key)
    #             self.render_devices_mongo(channelcode,isNotfirst=False)
    #     except Exception,e:
    #         logger.error('refresh_redisCache exception:%s ' % traceback.format_exc())
    #         raise e
        # portal_userchannels=rfrsh_content.get('portals')
        # for username in portal_userchannels:
        #     for key in rediscache.portal_cache.hkeys(rediscache.CHANNELS_PREFIX % username):
        #         rediscache.channels_cache.hdel(rediscache.CHANNELS_PREFIX % username,key)
        #     self.renderChannels_mongo(username)
