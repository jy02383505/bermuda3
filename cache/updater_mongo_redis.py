# -*- coding:utf-8 -*-
__author__ = 'root'
from .api_mongo import  ApiMongo
# from trans_mongo_to_redis import MongoToRedis
from util import log_utils

import rediscache,traceback,time

logger = log_utils.get_redis_Logger()

class UpdaterRedis(object):
    def __init__(self):
        self.apimongo = ApiMongo()
        # pass
        # self.trans_mongo_to_redis=MongoToRedis()

    ''' channel:[],device:[],firstdevice:[]'''
    # def notify_redis_update(self):
    #     try:
    #         user_updates=[]
    #         '''channels been changed'''
    #         for userchannel in self.apimongo.cache_user_channels.find({'needUpdateRedis':True},{'username':1}):
    #             # .sort('username',1):
    #             user_updates.append(userchannel.get('username'))
    #         print('notify_redis_update channels been changed nums:%d'% len(user_updates))
    #         # logger.debug('notify_redis_update channels been changed nums:%d'% len(user_updates))
    #         '''devices been changed'''
    #         channel_devices_updates=[]
    #         for channel_device in self.apimongo.cache_channel_devices.find({'needUpdateRedis':True},{'channel_code':1}):
    #             # .sort('channel_code',1):
    #             channel_devices_updates.append(channel_device.get('channel_code'))
    #         channel_firstdevices_updates=[]
    #         print('notify_redis_update devices been changed nums:%d'% len(channel_devices_updates))
    #         # logger.debug('notify_redis_update devices been changed nums:%d'% len(channel_devices_updates))
    #
    #         ''' for channel first device'''
    #         for channel_firstdevice in self.apimongo.cache_channel_firstlayer_devices.find({'needUpdateRedis':True},{'channel_code':1}):
    #             # .sort('channel_code',1):
    #             channel_firstdevices_updates.append(channel_firstdevice.get('channel_code'))
    #         print('notify_redis_update first device been changed nums:%d'% len(channel_firstdevices_updates))
    #         # logger.debug('notify_redis_update first device been changed nums:%d'% len(channel_firstdevices_updates))
    #
    #         '''for portal:'''
    #         portal_user_channel_updates=[]
    #         for channel_device in self.apimongo.cache_user_channels_portal.find({'needUpdateRedis':True},{'channel_code':1}):
    #             portal_user_channel_updates.append(channel_device.get('channel_code'))
    #
    #         print('notify_redis_update portal been changed nums:%d'% len(portal_user_channel_updates))
    #         # logger.debug('notify_redis_update first device been changed nums:%d'% len(portal_user_channel_updates))
    #         '''call the interface to refresh redis'''
    #         self.trans_mongo_to_redis.refresh_redisCache({rediscache.USERCHANNELS_UPDATE:user_updates,rediscache.CHANNEL_DEVICES_UPDATE:channel_devices_updates,rediscache.CHANNEL_FIRSTDEVICES_UPDATE:channel_firstdevices_updates,rediscache.PORTAL_UPDATE:portal_user_channel_updates})
    #
    #     except Exception,e:
    #         logger.error('notify_redis_update exception:%s' % traceback.format_exc())
    #         raise e

    def updateMongoRedis_rcms(self,all=False):
        self.apimongo.sync_allObjects_rcms(all)

    def updateMongoRedis_portal(self):
        self.apimongo.sync_allObjects_portal()

    def updateMongoRedis_portal_by_queue(self):
        self.apimongo.sync_user_channel_portals_by_queue()

    def clear_mongo(self):
        self.apimongo.clear_mongo_cache()

    def clear_redis(self):
        rediscache.clear_redis()

def sync_rcms():
    updaterRedis = UpdaterRedis()
    updaterRedis.updateMongoRedis_rcms()
def sync_all_rcms():
    updaterRedis = UpdaterRedis()
    updaterRedis.updateMongoRedis_rcms(all=True)

def sync_portal():
    updaterRedis = UpdaterRedis()
    updaterRedis.updateMongoRedis_portal()

def sync_portal_by_queue():
    updaterRedis = UpdaterRedis()
    updaterRedis.updateMongoRedis_portal_by_queue()

# def clear_cache():
#     updaterRedis = UpdaterRedis()
#     updaterRedis.clear_mongo()
#     updaterRedis.clear_redis()

#
# if __name__ == '__main__':
#     import sys
#     updaterRedis=UpdaterRedis()
#     if (sys.argv.__len__()==2):
#         outer = sys.argv[1]
#         if outer=='rcms':
#             updaterRedis.updateMongoRedis_rcms()
#         else:
#             print 'begining updateMongoRedis_portal from main'
#             updaterRedis.updateMongoRedis_portal()
