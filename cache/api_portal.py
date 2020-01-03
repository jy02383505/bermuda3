# -*- coding:utf-8 -*-
__author__ = 'root'
import  urllib.request,  urllib.parse,  urllib.error
import traceback
from .api_outersys import ApiOuter
from core.config import  config
from util import log_utils

logger = log_utils.get_redis_Logger()

USERS_ROOT = config.get('portalapi', 'USERS_ROOT')
PORTAL_ROOT=config.get('portalapi', 'CHANNEL_ROOT')
USER_ROOT =config.get('portalapi', 'USER_ROOT')
CHANNEL_QUEUE_ROOT = config.get('portalapi', 'CHANNEL_QUEUE_ROOT')

CHANNELS_URL = PORTAL_ROOT + '?allCustomerBusinesses=true&username=%s'
USERINFO_URL=USER_ROOT+'?username=%s'
CHANNEL_QUEUE_INFO_URL = CHANNEL_QUEUE_ROOT + '/?auth=ChtTPs0s1842fdc&name=account_channel_relation_change&opt=status_json'
CHANNEL_QUEUE_GET_URL = CHANNEL_QUEUE_ROOT + '/?auth=ChtTPs0s1842fdc&name=account_channel_relation_change&opt=get'


class ApiPortal(ApiOuter):
    '''
    this class is api for module to call portal by urllib
    '''
    def read_userInfo_portal(self,username):
        return self.read_from_outer(USERINFO_URL% username)

    def read_allCustomers_portal(self):
        return self.read_from_outer(USERS_ROOT)

    def read_channels_portal(self,username):
        return self.read_from_outer(CHANNELS_URL % username)

    def read_channels_portal_changed_by_queue(self, getOne=False):
        if getOne:
            return self.read_from_outer(CHANNEL_QUEUE_GET_URL)
        else:
            return self.read_from_outer(CHANNEL_QUEUE_INFO_URL)

