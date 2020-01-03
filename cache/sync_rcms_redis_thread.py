#! -*- encoding=utf-8 -*-
__author__ = 'root'

import threading
import traceback
import datetime,time
import simplejson as sjson
from util import log_utils

logger = log_utils.get_redis_Logger()

class SyncObjThread(threading.Thread):
    def __init__(self,thread_name,userlist,apimongo,countbatch, map_user_channels={}):
        super(SyncObjThread, self).__init__(name = thread_name)
        self.thread_name=thread_name
        self.handler=apimongo
        self.userlist=userlist
        self.countbatch=countbatch
        self.map_user_channels=map_user_channels

    def run(self):

        try:
            for username in self.userlist:
                if not self.map_user_channels:
                    channels = self.handler.sync_channels(username)
                else:
                    # the content is new
                    channels = self.handler.sync_channels_new(username, self.map_user_channels)
                    logger.warn("SyncObjThread   get data from channels!")
                for channel_obj in channels:
                    if channel_obj.get('channelState') !='TRANSFER':
                        channel_code=channel_obj.get('code')
                        self.handler.sync_devices(channel_code)
                        self.handler.sync_firstLayer_devices(channel_code)


            self.countbatch.count_down()
        except Exception:
            logger.error('SyncObjThread thread run exception:---%r,%r' % (self.thread_name,traceback.format_exc()))
            raise e

'''cite from internet, this class is similar to countdownlatch in java to ensure the thread finish at the some point'''
class CountDownLatch(object):
    def __init__(self, usercount=0,threadcount=1,thread_name='',begin_time=time.time()):
        self.count = threadcount
        self.total_user_num=usercount
        self.total_thread_num=threadcount
        self.lock = threading.Condition()
        self.begintime=begin_time
        self.threadname=thread_name

    def count_down(self):
        self.lock.acquire()
        self.count -= 1
        if self.count <= 0:
            self.lock.notifyAll()
            logger.warn('sync_allObjects_rcms End...threadname=%s ---.threadnum=%s...usernum=%s...takes time= %s  seconds' %(self.threadname, str(self.total_thread_num),str(self.total_user_num), str(time.time()-self.begintime)))
            print(('sync_allObjects_rcms End...threadname=%s ....threadnum=%s...usernum=%s...takes time= %s  seconds' %(self.threadname,str(self.total_thread_num),str(self.total_user_num), str(time.time()-self.begintime))))

        self.lock.release()

    def await(self):
        self.lock.acquire()
        while self.count > 0:
            self.lock.wait()
        self.lock.release()
