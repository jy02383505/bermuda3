# -*- coding:utf-8 -*-
__author__ = 'root'
from .api_rcms import ApiRCMS
from .api_portal import ApiPortal
import simplejson as sjson
from . import rediscache
'''
this class is utility
to implement the data transition from RCMS ,portal to redis
caused by redis structure is different from RCMS,portal.
redis to save using key-hash,RCMSToRedis,portal is saved key-value
'''
class OutSysToRedis(object):
    def __init__(self):
        self.rcms_cache=ApiRCMS()
        self.portal_cache=ApiPortal()
    def render_userInfo_outer(self,username,isRcms=True):
        if isRcms:
            return self.rcms_cache.read_userInfo_rcms(username)
        else:
            customer_portal=self.portal_cache.read_userInfo_portal(username)
            return rediscache.refresh_user_channel_portal(username,customer_portal)
    def render_channels_rcms(self,username):
        channels_map={}
        channels_rcms=self.rcms_cache.read_channels_rcms(username,need_retry=False)
        if channels_rcms:
            # channels_cache = sjson.JSONDecoder(encoding='utf-8').decode(channels_cache_str)
            channels_map= rediscache.refresh_user_channel(username,channels_rcms)
        return channels_map


    def render_devices_rcms(self,channel_code,isNotFirst=True):
        devices_map={}
        devices_cache={}
        if isNotFirst:
            devices_cache_str=self.rcms_cache.read_devices_rcms(channel_code,need_retry=False)
            if devices_cache_str:
                devices_cache = sjson.JSONDecoder(encoding='utf-8').decode(devices_cache_str)
        else:
            devices_cache_str=self.rcms_cache.read_firstDevices_rcms(channel_code,need_retry=False)
            if devices_cache_str:
                devices_cache = sjson.JSONDecoder(encoding='utf-8').decode(devices_cache_str)

        device_list=devices_cache.get('devices')
        if device_list:
            devices_map= rediscache.refresh_channel_devices(channel_code,isNotFirst,device_list)
        return devices_map