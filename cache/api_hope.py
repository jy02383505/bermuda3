# -*- coding:utf-8 -*-
__author__ = 'root'
import urllib.request, urllib.parse, urllib.error,traceback

from core.config import  config
from .api_outersys import ApiOuter
from util import log_utils
import simplejson as sjson

logger = log_utils.get_redis_Logger()
RCMS_ROOT = config.get('hopeapi', 'HOPE_ROOT')

#查询所有频道信息,including user name
ALL_HPCC_CACHE = RCMS_ROOT + '/servicetree/api/all/devicelist?app=SHPCC,HPCC'
#ALL_SMS_CACHE  = RCMS_ROOT + '/servicetree/api/all/devicelist?app=SMS&product=BRE_MSO_SMS&device_group=SMS002'
ALL_SMS_CACHE  = RCMS_ROOT + '/servicetree/api/all/devicelist?app=SMS&product=BRE_MSO_SMS&device_group=SMS001'

RETRY_TIMES=2
class ApiHOPE(ApiOuter):

    def read_allHpcc_cache_hope(self):
        return self.read_from_outer(ALL_HPCC_CACHE, time_out=60)
    def read_all_sms_cache_hope(self):
        return self.read_from_outer(ALL_SMS_CACHE, time_out=60)

