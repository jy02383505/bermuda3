#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Created on 2017-11-13

"""

import simplejson as json
import sys
#log
import traceback, logging, time
from datetime import datetime
from . import queue, database
from util import log_utils
from .config import config
from util.tools import JSONEncoder, load_task, delete_urlid_host, get_mongo_str
from werkzeug.exceptions import Forbidden, BadRequest, Unauthorized, HTTPException

# logger = logging.getLogger('router')
# logger.setLevel(logging.DEBUG)

logger = log_utils.get_logger_refresh_result()
db_s1 = database.s1_db_session()

class Refresh_router(object):
    def __init__(self, batch_size = 10000, package_size = 100):

        self.preload_api_size = 100
        self.batch_size = batch_size
        self.package_size = package_size
        logger.debug('router start. batch_size:%s package_size:%s' % (self.batch_size, self.package_size))
        self.dt = datetime.now()
        self.merged_refresh = {}
        #self.merged_refresh_dir={}


    def run(self):
        logger.debug("refresh_router.start")
        self.refresh_router()
        logger.debug("refresh_router.end")


    def refresh_router(self, queue_name='result_task'):
        '''
        回调数据打包
        '''
        try:
            messages = queue.get(queue_name, self.batch_size)
            logger.debug("refresh_router %s .work process messages begin, count: %d " %(queue_name, len(messages)))
            for body in messages:
                #logger.debug('---------'+ body +'-------------------')
                task = json.loads(body)
                #if isinstance(task, str):
                    #task = json.loads(task)
                #logger.debug(task)
                logger.debug('router for refresh: %s' % task.get('session_id'))
                self.merge_refresh(task)
            for key in self.merged_refresh.keys():
                self.update_refresh_result(self.merged_refresh.get(key))
            logger.info("refresh_router %s .work process messages end, count: %d " %(queue_name, len(messages)))
        except Exception:
            logger.warning('refresh_router %s work error:%s' %(queue_name, traceback.format_exc()))

    def merge_refresh(self, task):
        session_id=task['session_id']
        self.merged_refresh.setdefault(session_id,[]).append(task)
        if len(self.merged_refresh.get(session_id)) > self.package_size:
            self.update_refresh_result(self.merged_refresh.pop(session_id))


    def update_refresh_result(self,results):
        if not results:
            return
        logger.debug('update_refresh_result number:%s' % (len(results)))
        for result in results:
            timestr=result['time']
            result['time']=datetime.strptime(timestr, '%Y-%m-%d %H:%M:%S %f')#time.mktime(time.strptime(timestr, "%Y-%m-%d %H:%M:%S")
            url_id = result.get('session_id')
            host = result.get('host')
            result_code = result.get('result')
            try:
                if 'result_gzip' in result:

                    result_gzip_code = result.get('result_gzip', '0')
                    if str(result_code) == '200' and str(result_gzip_code) == '200':
                        delete_urlid_host(url_id, host)
                else:
                    if str(result_code) == '200':
                        delete_urlid_host(url_id, host)
            except Exception:
                logger.debug('refresh result error :%s' % traceback.format_exc())
        str_num = ''
        try:
            num_str =config.get('refresh_result', 'num')
            str_num = get_mongo_str(str(results[0].get('session_id')), num_str)
        except Exception:
            logger.debug('get number of refresh_result error:%s' % traceback.format_exc())

        try:

            db_s1['refresh_result' + str_num].insert_many(results,ordered=False)

            time.sleep(0.05)

            logger.debug('update_refresh_result success, session_id:%s' % (result.get('session_id')))
        except Exception:
            logger.info('update_refresh_result error:%s, session_id:%s' % (traceback.format_exc(),
                                                            result.get('session_id')))
    def load_task(self,task):
        '''
            解析接口的task

        Parameters
        ----------
        task : 刷新任务，JSON 格式

        Returns
        -------
        {"urls":["http://***1.jbp","http://***2.jbp"],
　　      "dirs":["http://***/","http://d***2/"],
　　      "callback":{"url":"http://***",
　　                  "email":["mail1","mail2"],
                    "acptNotice":true}}
        '''
        try:
            return json.loads(task)
        except Exception:
            logger.warn(task, exc_info=sys.exc_info())
            raise BadRequest("The schema of task is error.")


if __name__ == "__main__":
    logger.debug("router begining...")
    router = Refresh_router()
    router.run()
    logger.debug("router end.")