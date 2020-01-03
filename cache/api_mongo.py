# -*- coding:utf-8 -*-
__author__ = 'root'
import datetime,time
import traceback,threading
import simplejson as sjson
from . import  rediscache
from .api_rcms import ApiRCMS
from .api_portal import ApiPortal
from util import log_utils


logger = log_utils.get_redis_Logger()
FUNCTION_USER='3'
DAY_FREQ='DAY'
HOUR_FREQ='HOUR'

from core.database import db_session
from .sync_rcms_redis_thread import CountDownLatch,SyncObjThread


class ApiMongo(ApiRCMS,ApiPortal):
    '''
    this class to read or write mongo by reading portal or rcms content
    no need to deploy on the same host lwith the database of bermuda
    '''
    def __init__(self):
        dbcache=db_session()
        self.statistical=dbcache.statistical
        self.cache_user_channels = dbcache.cache_user_channels
        self.cache_user_channels.create_index('username')
        self.cache_channel_devices=dbcache.cache_channel_devices
        self.cache_channel_devices.create_index('channel_code')
        self.cache_channel_firstlayer_devices=dbcache.cache_channel_firstlayer_devices
        self.cache_channel_firstlayer_devices.create_index('channel_code')
        self.cache_user_channels_portal=dbcache.cache_user_channels_portal
        self.cache_user_channels_portal.create_index('username')

    def is_first_times(self,now_str,freq):
        if freq==DAY_FREQ:
            return int(now_str[11:13])==1 and int(now_str[14:16])<5
        elif freq==HOUR_FREQ:
            #after 1 hour, when statis in mongodb at 2
            return int(now_str[11:13])==3 and int(now_str[14:16])<5
        return False

    def get_predays_users(self,days=5,now_str=''):
        username_set=[]
        usernames_redis = rediscache.channels_cache.smembers(rediscache.USERNAME_LIST_KEY)
        if self.is_first_times(now_str,DAY_FREQ):#sync all at this time
             return 0,[]
        if self.is_first_times(now_str,HOUR_FREQ):#refresh the key from mongodb.statistical.2:00 begin
            sts = self.statistical.find({},{'username_list':1}).sort("date", -1).limit(days)
            for usr_names in sts:
                username_set = username_set + usr_names.get('username_list')
            pipe=rediscache.channels_cache.pipeline()
            pipe.delete(rediscache.USERNAME_LIST_KEY)
            for username in username_set:
                pipe.sadd(rediscache.USERNAME_LIST_KEY, username)
            pipe.execute()
        return len(usernames_redis),usernames_redis

    def get_all_rcms_users(self):
        users_str=self.read_allCustomers_rcms()
        # users_str='[{ 'code': '2275', 'companyName': 'test', 'name': 'xingyun', 'password': 'test', 'userState': 'TEST' }]'
        print(users_str, 'ztdebug..users')
        logger.debug('get_all_rcms_users:%s' % users_str)
        username_arr=[]
        if self.get_valid_jsonstr(users_str):
            all_users= sjson.JSONDecoder(encoding='utf-8').decode(users_str)
            username_arr= [customer_obj.get('name') for customer_obj in all_users if customer_obj.get('userState') !='TRANSFER']
        return len(username_arr),username_arr

    def get_all_rcms_users_new(self):
        """
        获取所有的频道信息，包含用户名称,然后组装users
        Returns:

        """
        try:
            logger.warn("get_all_rcms_users_new get channels starting...")
            channels_str = self.read_allChannels_rcms()
            logger.warn("get_all_rcms_users_new get channels end...")
            logger.warn('get_all_rcms_channels get channels success!')
            logger.warn('type of channels_str:%s' % type(channels_str))
            # logger.warn('valid jsonstr:%s' % self.get_valid_jsonstr(channels_str))
            time_start = time.time()
            if self.get_valid_jsonstr(channels_str):
                logger.warn("different:%s" % (time.time() - time_start))
                channels = sjson.JSONDecoder(encoding='utf-8').decode(channels_str)
                # 增加一个处理channels 信息的接口
                logger.warn("type of channels:%s" % type(channels))
                length_channel, user_names, map_user_channels = self.arrangement_all_channels(channels)
                return length_channel, user_names, map_user_channels
            return 0, [], {}
        except Exception:
            logger.warn("get_all_rcms_channels error:%s" % traceback.format_exc())
            return 0, [], {}

    def arrangement_all_channels(self, channels):
        """
        处理channels信息，返回　["username": [{'state': "commercial", "channelName": "xxxxx", "channelCode": "94038"}]]
        Args:
            self:
            channels: 处理　channel state 不是　TRANSFER的频道

        Returns:

        """
        map_temp = {}
        if not channels:
            return 0, [], {}
        else:
            try:
                for channel in channels:
                    state = channel.get('state')
                    logger.debug('arrangement_all_channels channel:%s' % channel)
                    if state not in ["TRANSFER"]:
                        temp = {}
                        temp['code'] = channel.get('channelCode')
                        temp['channelName'] = channel.get('channelName')
                        temp['customerName'] = channel.get('customerName')
                        temp['channelState'] = channel.get('state')
                        temp['billingCode'] = channel.get('billingCode')
                        temp['customerCode'] = channel.get('customerCode')
                        temp['customerDirector'] = channel.get('customerDirector')
                        temp['isLayered'] = channel.get('isLayered')
                        temp['name'] = channel.get('channelName')
                        temp['productCode'] = channel.get('productCode')
                        temp['transferTime'] = channel.get('channelTransferTime')
                        temp['multilayer'] = channel.get('isLayered')
                        if temp['customerName'] in map_temp:
                            map_temp[temp['customerName']].append(temp)
                        else:
                            map_temp[temp['customerName']] = []
                            map_temp[temp['customerName']].append(temp)
                if map_temp:
                    map_keys = list(map_temp.keys())
                    return len(map_keys), map_keys, map_temp
                else:
                    return 0, [], {}
            except Exception:
                logger.debug("arrangement_all_channels error:%s" % traceback.format_exc())
                return 0, [], {}

    def sync_allObjects_rcms(self,all):
        # BATCH_SIZE=30
        # origin thread_num
        thread_num = 20
        # test thread num
        # thread_num = 15
        now_str = str(datetime.datetime.now())
        thread_name = threading.currentThread().getName()+now_str
        logger.warn('sync_allObjects_rcms of thread:%s.....Begin' % thread_name)
        print(('sync_allObjects_rcms..thread.name = %s ...Begin at %s' % (thread_name,now_str)))
        try:
            thread_users=[]
            map_user_channels = {}
            if all:
                # usernum_countlatch, username_arr=self.get_all_rcms_users()
                usernum_countlatch, username_arr, map_user_channels = self.get_all_rcms_users_new()
                logger.warn("sync_allObjects_rcms get data from channels success")
            else:
                usernum_countlatch,username_arr=self.get_predays_users(1,now_str)
            print(usernum_countlatch, 'ztdebug-----')

            logger.warn('sync_allObjects_rcms of usernum_countlatch:%s' % usernum_countlatch)
            if usernum_countlatch>0:
                # thread_num = usernum_countlatch/BATCH_SIZE +1
                BATCH_SIZE = usernum_countlatch/thread_num + 1
                logger.warn('sync_allObjects_rcms of thread_num:%s' % thread_num)
                countbatch=CountDownLatch(usernum_countlatch,thread_num,thread_name,time.time())
                for user_name in username_arr:
                    user_name_utf8 = self.utfize_username(user_name)
                    thread_users.append(user_name_utf8)
                    if (len(thread_users)>=BATCH_SIZE):
                        self.sync_obj_by_multhread(thread_name,thread_users,countbatch, map_user_channels=map_user_channels)
                        thread_users=[]
                self.sync_obj_by_multhread(thread_name,thread_users,countbatch, map_user_channels=map_user_channels)
            else:
                print(('sync_allObjects_rcms of thread:%s.....End at %s' % (thread_name,str(datetime.datetime.now()))))

            logger.warn('The_Nums_sync_users_from_rcms of thread: %s totally are== :%s' % (thread_name,str(usernum_countlatch)))
            return True
        except Exception:
            logger.error('From rcms sync allObjects_from rcms  exception:')
            logger.error('exp detail is :%s' % traceback.format_exc())
            return False

    def sync_obj_by_multhread(self,user_name_utf8,thread_users,countbatch, map_user_channels={}):
        try:
            SyncObjThread(user_name_utf8,thread_users,self,countbatch, map_user_channels=map_user_channels).start()
        except Exception:
            logger.error('sync_allObjects.sync_obj_by_multhread exception: sleep 10s')
            time.sleep(10)
            #original
            # self.sync_obj_by_multhread(user_name_utf8,thread_users,self,countbatch)
            # new
            self.sync_obj_by_multhread(user_name_utf8,thread_users,countbatch, map_user_channels=map_user_channels)



    '''[{'accountType':'0','apipwd':'workercn@123',
        'customerCode':'2754','name':'workercn','password':'',
        'status':'commercial'},
        '''
    def sync_allObjects_portal(self):
        logger.warn('sync allObjects_portal From  portal begin to mongodb and redis')
        try:
            all_customers_portal=self.read_allCustomers_portal()
            all_users = self.get_valid_jsonstr(all_customers_portal)
            if all_users:
                mapping={}
                for user_obj in all_users:
                    if user_obj.get('status') !='out':
                        self.sync_user_channel_portals(user_obj,mapping)
                        if (len(list(mapping.keys()))==rediscache.PORTAL_USER_BATCH_SIZE):
                            rediscache.refresh_customer_portal(mapping)
                            mapping={}
                rediscache.refresh_customer_portal(mapping)
            logger.warn('sync allObjects_portal From  portal finished to mongodb and redis')
            return True
        except Exception:
            logger.error('From  portal to mongo sync allObjects_portal exception:%s' % traceback.format_exc())
            return False


    def sync_user_channel_portals_by_username(self, username):
        '''
        对指定username同步缓存channle
        '''
        try:
            if not username or username=='HTTPSQS_GET_END':
                return
            business = self.read_channels_portal(username)
            if self.get_valid_jsonstr(business):
                logger.warn(' from portal sync user channel by username %s in redis begin'%(username))
                business_obj = sjson.JSONDecoder().decode(business)
                if business_obj:
                    business_arr = business_obj.get('businesses')
                    if  business_arr and len(business_arr)>0:
                        channel_portal_list = []
                        for business_arr_i in business_arr:
                            product_code = business_arr_i.get('productCode','')
                            if not product_code:
                                continue
                            # logger.warn(business_arr_i.get('channels'))
                            channel_portal_list.extend(business_arr_i.get('channels'))
                        channel_portal = channel_portal_list
                        logger.warn("set username:%s,%s"%(username,channel_portal))
                        rediscache.refresh_channels_portal(username, channel_portal)
        except Exception:
            logger.error('sync user  channels for portal by username : [%s] to redis : %s' % (username,traceback.format_exc()))

    def sync_user_channel_portals_by_queue(self):
        '''
        定期对portal提供的队列拉取频道关系更改的用户
        对其提供的用户进行缓存更新
        '''
        logger.warn('sync user channel portals by queue From portal begin to mongodb and redis')
        try:
            queue_info = self.read_channels_portal_changed_by_queue()
            if not queue_info:
                return False
            info_obj = self.get_valid_jsonstr(queue_info)
            if not info_obj:
                return False
            unread_num = info_obj.get('unread', 0)
            if unread_num <= 0:
                logger.warn('sync user channel portals by queue unread num not enough, num is %s' %(unread_num))
                return False

            logger.warn('sync user channel portals by queue unread num is %s' %(unread_num))
            for n in range(unread_num):
                username = self.read_channels_portal_changed_by_queue(getOne=True)
                self.sync_user_channel_portals_by_username(username)
                time.sleep(0.1)

        except Exception:
            logger.error('From portal to redis sync user channel portals by queue exception:%s' % traceback.format_exc())
            return False


    def sync_channels(self,username):
        try:
            if not username:
                return []
            '''note:the precondition is that:
             user in rcms should never be dropped instead updated or appended'''
            channel_rcms=self.read_channels_rcms(username)
            if channel_rcms is None:
                logger.warn('get data from rcms error None, username:%s' % username)
                return []
            rediscache.refresh_user_channel(username,channel_rcms)
            logger.debug('From rcms sync_channels method,in: %s' % (username,))
            return channel_rcms
        except Exception:
            logger.error('From rcms sync_channels method,in: %s have exceptions: %s' % (username,traceback.format_exc()))
            return []

    def sync_channels_new(self, username, map_username_channels):
        """
        according map_username_channels, get the channels of user
        Args:
            username:
            map_username_channels:

        Returns:

        """
        try:
            if not username:
                return []
            '''note:the precondition is that:
             user in rcms should never be dropped instead updated or appended'''
            channel_rcms = map_username_channels[username]
            rediscache.refresh_user_channel(username, channel_rcms)
            logger.debug('From rcms sync_channels_new method,in: %s' % (username,))
            return channel_rcms
        except Exception:
            logger.error('From rcms sync_channels method,in: %s have exceptions: %s' % (username,traceback.format_exc()))
            return []



    def sync_devices(self,channel_code=''):
        try:
            if not channel_code:
                return
            devices_rcms_str=self.read_devices_rcms(channel_code)
            # alter by rubin 2017 1 11 start
            if devices_rcms_str is None:
                return
            # alter by rubin 2017 1 11 end
            devices_rcms=[]
            if self.get_valid_jsonstr(devices_rcms_str):
                devices_rcms = sjson.JSONDecoder().decode(devices_rcms_str).get('devices')

            rediscache.refresh_channel_devices(channel_code,True,devices_rcms)
            logger.debug('From rcms sync Devices of channel: %s' % (str(channel_code),))
        except Exception:
            logger.error('From rcms sync_devices method in: %s have errors:%s' % (str(channel_code),traceback.format_exc()))
            # raise e
    # logger.debug('db_update error, message=%s' % (ex))

    def sync_firstLayer_devices(self,channel_code=''):
        try:
            if not channel_code:
                return
            devices_rcms=[]
            firlayer_devices=self.read_firstDevices_rcms(channel_code)
            # alter by rubin 2017 1 11  start
            if firlayer_devices is None:
                logger.debug("sync_firstLayer_devices firlayer_devices is None")
                return
            # alter by rubin end
            if self.get_valid_jsonstr(firlayer_devices):
                devices_obj = sjson.JSONDecoder().decode(firlayer_devices)
                devices_rcms=devices_obj.get('devices')
            rediscache.refresh_channel_devices(channel_code,False,devices_rcms)
            logger.debug('From rcms sync_firstLayer_devices of channel: %s' % (str(channel_code),))
        except Exception:
            logger.error('From rcms sync_firstLayer_devices of channel: %s method have errors: %s' % (str(channel_code),traceback.format_exc()))
            # raise e

    '''name: 用户名称
    customerCode: 用户代码，如果不是主帐户，则该值为空字符串
    status: 用户状态，如果不是主帐户，则该值为空字符串。可能的值有：
        0: 商用
        5: 测试
        -1: 转出
    accountType: 帐户类型，可能的值有：
        0: 主帐户
        2: 集团帐户
        3: 功能帐户
    '''

    def sync_user_channel_portals(self,user_obj,mapping):
        try:
            if not user_obj:
                return
            user_name =user_obj.get('name')
            account_type=user_obj.get('accountType')
            mapping[rediscache.USERINFO_PORTAL_PREFIX % user_name]=user_obj
            if account_type==FUNCTION_USER:
                business = self.read_channels_portal(user_name)
                if self.get_valid_jsonstr(business):
                    business_obj = sjson.JSONDecoder().decode(business)
                    if business_obj:
                        business_arr = business_obj.get('businesses')
                        if  business_arr and len(business_arr)>0:
                            channel_portal_list = []
                            for business_arr_i in business_arr:
                                product_code = business_arr_i.get('productCode','')
                                if not product_code:
                                    continue
                                channel_portal_list.extend(business_arr_i.get('channels'))
                            channel_portal = channel_portal_list
                            rediscache.refresh_channels_portal(user_name, channel_portal)
                            logger.warn('from portal  sync user channel in redis:%s,%s'%(user_name,channel_portal))
        except Exception:
            logger.error('sync users and channels for portal by user : [%s] to mongo : %s' % (user_name,traceback.format_exc()))


    def read_customer_mongo(self,username):
        try:
            channel_obj =self.cache_user_channels.find_one({'username':username},{'userinfo':1})
            if channel_obj:
                return channel_obj.get('userinfo')
        except Exception:
            logger.error(traceback.format_exc())

        return {}


    def read_channels_mongo(self,username):
        try:
            channel_obj =self.cache_user_channels.find_one({'username':username},{'channels':1})
            if  channel_obj:
                return channel_obj.get('channels')
        except Exception:
            logger.error('read_channels_mongo from handle exception: %s ' % traceback.format_exc() )
        return []

    def read_portalChannels_mongo(self,username,isuser=False):
        try:
            if isuser:
                channel_obj =self.cache_user_channels_portal.find_one({'username':username},{'userinfo':1})
                if channel_obj:
                    return channel_obj.get('userinfo')
            else:
                channel_obj =self.cache_user_channels_portal.find_one({'username':username},{'channels':1})
                if channel_obj:
                    return channel_obj.get('channels')
        except Exception:
            logger.error('read_portalChannels_mongo exceptions: %s:' % traceback.format_exc())
        return {}

    def read_devices_mongo(self,channel_code):
        device_obj =self.cache_channel_devices.find_one({'channel_code':channel_code},{'devices':1})
        if  device_obj:
            return device_obj.get('devices')
        return []


    def read_firstLayerDevices_mongo(self,channel_code):
        device_obj =self.cache_channel_firstlayer_devices.find_one({'channel_code':channel_code},{'devices':1})
        if  device_obj:
            return device_obj.get('devices')
        return []
    def clear_mongo_cache(self):
        self.cache_user_channels.remove({})
        self.cache_channel_devices.remove({})
        self.cache_channel_devices.remove({})
