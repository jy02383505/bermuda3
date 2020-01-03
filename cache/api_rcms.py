# -*- coding:utf-8 -*-
__author__ = 'root'
import urllib.request, urllib.parse, urllib.error,traceback

from core.config import  config
from .api_outersys import ApiOuter
from util import log_utils
import simplejson as sjson

logger = log_utils.get_redis_Logger()
RCMS_ROOT = config.get('rcmsapi', 'RCMS_ROOT')

#查询所有频道信息,including user name
ALL_CHANNELS = RCMS_ROOT + '/channels'
# #获取RCMS所有的客户信息
All_CUSTOMERS = RCMS_ROOT + '/customers'
#查询所有设备信息
All_DEVICES = RCMS_ROOT + '/devices'
#查询所有上层设备信息
ALL_FIRSTLAYER_DEVICES= RCMS_ROOT + '/upperlayer/devices'

CHANNELS_URL = RCMS_ROOT + '/customer/%s/channels'
DEVICES_URL = RCMS_ROOT + '/channel/%s/flexicache'
DEVICES_FIRSTLAYER_URL = RCMS_ROOT + '/channel/%s/flexicache/firstlayer'
CUSTOMER_URL = RCMS_ROOT + '/customer/%s'
DEVICE_STATUS_URL = RCMS_ROOT + "/device/name/%s/status"
DEVICE_BU_DEPARTMENT = RCMS_ROOT + "/device/%s"
CHANNELNAME = RCMS_ROOT + "/channelsByName?channelName=%s"
HPCC_OPEN_DEVICES = RCMS_ROOT + '/app/name/GHPC/OPEN/devices'

RETRY_TIMES=2
class ApiRCMS(ApiOuter):
    def read_allCustomers_rcms(self):
        return self.read_from_outer(All_CUSTOMERS)

    def read_allChannels_rcms(self):
        return self.read_from_outer(ALL_CHANNELS, time_out=600)

    def read_allDevices_rcms(self):
        return self.read_from_outer(All_DEVICES)

    def read_allFirstLayer_Devices_rcms(self):
        return self.read_from_outer(ALL_FIRSTLAYER_DEVICES)

    def read_userInfo_rcms(self,username,times=1):
        return self.read_from_outer(CUSTOMER_URL % urllib.parse.quote(username))

    def read_channels_rcms(self,username,times=1,need_retry=True):
        user_chnl_str = self.read_from_outer(CHANNELS_URL % urllib.parse.quote(username),need_retry=need_retry)
        if user_chnl_str is None:
            logger.warn('read_channels_rcms get data from rcms error, username:%s' % username)
            return None
        if self.get_valid_jsonstr(user_chnl_str):
            channel_rcms=sjson.JSONDecoder(encoding='utf-8').decode(user_chnl_str)
            return [user_channel for user_channel in channel_rcms if user_channel['channelState'] not in ["TRANSFER"]]
        return []
    def read_devices_rcms(self,channel_code,times=1,need_retry=True):
        return self.read_from_outer(DEVICES_URL % urllib.parse.quote(channel_code),need_retry=need_retry)

    def read_firstDevices_rcms(self,channel_code,times=1,need_retry=True):
        return self.read_from_outer(DEVICES_FIRSTLAYER_URL % urllib.parse.quote(channel_code),need_retry=need_retry)

    def read_allHpcc_rcms(self):
        return self.read_from_outer(HPCC_OPEN_DEVICES, time_out=5)

    # def read_from_rcms(self,channel_code,times=1):
    #     return self.read_from_outer(DEVICES_FIRSTLAYER_URL % urllib.quote(channel_code))
