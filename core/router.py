#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Created on 2011-5-26

@author: wenwen
"""

import simplejson as json
from math import ceil
import sys
#log
import traceback, logging
from datetime import datetime
from core import queue, preload_worker_new, database, cert_trans_worker, cert_query_worker, transfer_cert_worker
from . import dir_refresh ,url_refresh
from util import log_utils
from .config import config
from core.generate_id import ObjectId

from . import physical_refresh
# logger = logging.getLogger('router')
# logger.setLevel(logging.DEBUG)

logger = log_utils.get_router_Logger()

PRELOAD_RATIO = {'preload_task': 1, 'preload_task_h': 2}

class Router(object):
    def __init__(self, batch_size = 3000, package_size = 30):

        self.preload_api_size = 100
        self.batch_size = batch_size
        self.package_size = package_size
        logger.debug('router start. batch_size:%s package_size:%s' % (self.batch_size, self.package_size))
        self.dt = datetime.now()
        self.merged_urls = {}
        self.merged_cert = {}
        self.merged_cert_query = {}
        self.merged_transfer_cert = {}
        self.physical_urls = {}


    def run(self):

        #先执行高优先级队列任务
        logger.debug("refresh_high_router.start")
        self.refresh_router('url_high_priority_queue')
        logger.debug("refresh_high_router.end")
        #重置merged_urls
        self.merged_urls = {}
        logger.debug("refresh_router.start")
        self.refresh_router()
        logger.debug("refresh_router.end")

        logger.debug("preload_router.start")
        self.preload_router()
        logger.debug("preload_router.end")

        #logger.debug("preload_report_router.start")
        #self.preload_report_router()
        #logger.debug("preload_report_router.end")

        logger.debug("cert_router.start")
        self.cert_router()
        logger.debug("cert_router.end")

        logger.debug("cert_query_router.start")
        self.cert_query_router()
        logger.debug("cert_query_router.end")

        logger.debug("transfer_cert_router.start")
        self.transfer_cert_router()
        logger.debug("transfer_cert_router.end")

        logger.debug("physical_refresh.start")
        self.physicalrefresh_router()
        logger.debug("physical_refresh.end")



    def cert_router(self, queue_name='cert_task'):
        '''
        证书任务打包
        '''
        try:
            messages = queue.get(queue_name, self.batch_size)
            logger.debug("cert_router %s .work process messages begin, count: %d " %(queue_name, len(messages)))
            for body in messages:
                task = json.loads(body)
                logger.debug('router for cert: %s' % task.get('_id'))
                self.merge_cert(task)
            for tasks in list(self.merged_cert.values()):
                cert_trans_worker.dispatch.delay(tasks)
            logger.info("cert_router %s .work process messages end, count: %d " %(queue_name, len(messages)))
        except Exception:
            logger.warning('cert_router %s work error:%s' %(queue_name, traceback.format_exc()))

    def merge_cert(self, task):

        task['created_time'] = datetime.strptime(task.get("created_time"),"%Y-%m-%d %H:%M:%S")
        send_devs = task['send_devs']
        if send_devs == 'all_hpcc':
            self.merged_cert.setdefault(send_devs,[]).append(task)
            if len(self.merged_cert.get(send_devs)) > self.package_size:
                cert_trans_worker.dispatch.delay(self.merged_cert.pop(send_devs))
        else:
            cert_trans_worker.dispatch.delay([task])

    def cert_query_router(self,queue_name='cert_query_task'):
        '''
        证书查询任务
        '''

        try:
            messages = queue.get(queue_name, self.batch_size)
            logger.debug("cert_query_router %s .work process messages begin, count: %d " %(queue_name, len(messages)))
            task_set = {}
            for body in messages:
                task = json.loads(body)
                logger.debug('router for cert_query: %s' % task.get('_id'))
                self.merge_cert_query(task)
            #for k,v in self.merged_cert_query.items():
            for tasks in list(self.merged_cert_query.values()):
                #if len(v) > self.package_size:
                #cert_query_worker.dispatch.delay(self.merged_cert_query.pop(k))
                cert_query_worker.dispatch.delay(tasks)
        except Exception:
            logger.warning('cert_query_router %s work error:%s' %(queue_name, traceback.format_exc()))

    def merge_cert_query(self,task):

        task['created_time'] = datetime.strptime(task.get("created_time"),"%Y-%m-%d %H:%M:%S")
        m = task['dev_ip_md5']
        if m in self.merged_cert_query:
            self.merged_cert_query[m].append(task)
            if len(self.merged_cert.get(m)) > self.package_size:
                cert_query_worker.dispatch.delay(self.merged_cert.pop(m))
        else:
            self.merged_cert_query[m]=[task]

    def transfer_cert_router(self,queue_name='transfer_cert_task'):
        '''
        证书转移任务
        '''
        try:
            messages = queue.get(queue_name, self.batch_size)
            logger.debug("transfer_cert_router %s .work process messages begin, count: %d " %(queue_name, len(messages)))
            task_set = {}
            for body in messages:
                task = json.loads(body)
                logger.debug('router for transfer_cert: %s' % task.get('_id'))
                self.merge_transfer_cert(task)
            #for k,v in self.merged_cert_query.items():
            for tasks in list(self.merged_transfer_cert.values()):
                #if len(v) > self.package_size:
                #cert_query_worker.dispatch.delay(self.merged_cert_query.pop(k))
                transfer_cert_worker.dispatch.delay(tasks)
        except Exception:
            logger.warning('transfer_cert_router %s work error:%s' %(queue_name, traceback.format_exc()))

    def merge_transfer_cert(self,task):

        task['created_time'] = datetime.strptime(task.get("created_time"),"%Y-%m-%d %H:%M:%S")
        m = task['send_dev_md5']
        if m in self.merged_transfer_cert:
            self.merged_transfer_cert[m].append(task)
            if len(self.merged_transfer_cert.get(m)) > self.package_size:
                transfer_cert_worker.dispatch.delay(self.merged_transfer_cert.pop(m))
        else:
            self.merged_transfer_cert[m]=[task]

    def refresh_router(self, queue_name='url_queue'):
        """
        从url_queue中提取url,进行处理

        """
        try:
            messages = queue.get(queue_name, self.batch_size)
            logger.debug("refresh_router %s .work process messages begin, count: %d " %(queue_name, len(messages)))
            for body in messages:
                url = json.loads(body)
                logger.debug('router for url: %s' % url.get('id'))
                if url.get('isdir'):
                    dir_refresh.work.delay(url)
                    #todo change delay to queue.put
                elif url.get('url_encoding'):
                    url_refresh.work.delay([url])
                else:
                    self.merge_urlMsg(url)
            for urls in list(self.merged_urls.values()):
                url_refresh.work.delay(urls)
            logger.info("refresh_router %s .work process messages end, count: %d " %(queue_name, len(messages)))
        except Exception:
            logger.warning('refresh_router %s work error:%s' %(queue_name, traceback.format_exc()))

    def preload_router(self):
        """
        处理rabbitmq中preload_task的内容

        """
        try:
            # messages = queue.get('preload_task', self.batch_size)
            messages = self.get_preload_messages()
            if not messages:
                messages = queue.get('preload_task', self.batch_size)

            s1_db = database.s1_db_session()
            logger.debug("preload_router.work process messages begin, count: %d " %len(messages))
            url_dict = {}
            url_other = []
            for message in messages:
                self.merge_preload_task(message, url_dict, url_other)
            for urls in list(url_dict.values()):
                preload_worker_new.dispatch.delay(urls)
            if url_other:#定时任务先只插入库中
                for url_t in url_other:
                    url_t['_id'] = ObjectId()
                s1_db.preload_url.insert(url_other)
            logger.info("preload_router.work process messages end, count: %d " %len(messages))
        except Exception:
            logger.warning('preload_router work error:%s' % traceback.format_exc())


    def physicalrefresh_router(self, queue_name='physical_refresh'):
        """
        从url_queue中提取url,进行处理

        """
        try:
            messages = queue.get(queue_name, self.batch_size)
            logger.debug("refresh_router %s .work process messages begin, count: %d " %(queue_name, len(messages)))
            for body in messages:
                url = json.loads(body)
                logger.debug('router for url: %s' % url.get('id'))
                self.physical_urlMsg(url)
            for urls in list(self.physical_urls.values()):
                physical_refresh.work.delay(urls)
            logger.info("physical refresh_router %s .work process messages end, count: %d " %(queue_name, len(messages)))
        except Exception:
            logger.warning('physical refresh_router %s work error:%s' %(queue_name, traceback.format_exc()))

    def get_preload_messages(self):
        try:
            s1_db = database.s1_db_session()
            queue_list = [{i['queue_name']: int(i['queue_ratio'])} for i in s1_db.preload_queue_ratio.find({'status': 'ready'})]
            for q in queue_list:
                PRELOAD_RATIO.update(q)
            logger.info('get_preload_messages PRELOAD_RATIO: %s' % (PRELOAD_RATIO, ))
            all_p = sum(PRELOAD_RATIO.values())
            all_m_dict = {}
            for pi, pv in list(PRELOAD_RATIO.items()):
                g_num = int(ceil((pv/float(all_p))*self.batch_size))
                g_messages = queue.get(pi, g_num)
                logger.info('get_preload_messages g_messages key %s  value len %s'%(pi, len(g_messages)))
                all_m_dict[pi] = g_messages

            sorted_s = sorted(list(PRELOAD_RATIO.items()),key=lambda x: x[1], reverse=True)
            messages = []
            for k in sorted_s:
                append_key = k[0]
                messages.extend(all_m_dict[k[0]])

            for x in range(len(PRELOAD_RATIO)):
                if len(messages) < self.batch_size:
                    left_n = self.batch_size - len(messages)
                    left_m = queue.get(sorted_s[x][0], left_n)
                    messages.extend(left_m)

            logger.info('get_preload_messages messages count %s'%(len(messages)))

            return messages
        except Exception:
            logger.info('get_preload_messages error %s'%(traceback.format_exc()))
            return []

    def merge_urlMsg(self, url):
        """
        合并 频道相同的 url
        package_size 默认30条
        :param url:
        """
        if url.get("url",'').endswith('/'):
            url_refresh.work.delay([url])
        else:
            key = url.get('channel_code')
            self.merged_urls.setdefault(key,[]).append(url)
            if len(self.merged_urls.get(key)) > self.package_size :
                url_refresh.work.delay(self.merged_urls.pop(key))

    def physical_urlMsg(self, url):
        """
        合并 频道相同的 url
        package_size 默认30条
        :param url:
        """

        key = url.get('channel_code')
        self.physical_urls.setdefault(key, []).append(url)
        if len(self.physical_urls.get(key)) > self.package_size:
            physical_refresh.work.delay(self.physical_urls.pop(key))


    # original package_size  20
    def merge_preload_task(self,message,url_dict,url_other,package_size=50):
        """
        合并preload任务
        :param message:
        :param url_dict: 实时任务
        :param url_other: 定时任务
        :param package_size:
        """
        try:
            task = json.loads(message)
            task['created_time'] = datetime.strptime(task.get("created_time"),"%Y-%m-%d %H:%M:%S")
            if task.get('status') == 'PROGRESS':#实时任务
                url_dict.setdefault(
                    task.get("channel_code"), []).append(task)
            else:
                if task.get("start_time"):#定时任务
                    task['start_time'] = datetime.strptime(task.get("start_time"),"%Y-%m-%d %H:%M:%S")
                url_other.append(task)
            # logger.debug("merge_preload_task url_dict: %s" % url_dict)
            if len(url_dict.get(task.get("channel_code"),{})) > package_size:
                preload_worker_new.dispatch.delay(url_dict.pop(task.get("channel_code")))
        except Exception:
            logger.debug("merge_preload_task error: %s" % e)

   # def preload_report_router(self):

   #     try:
   #         messages = queue.get('preload_report', self.preload_api_size)
   #         for msg in messages:
   #             preload_worker_new.save_fc_report.delay(msg)
   #     except Exception,e:
   #         logger.warning('preload_report_router work error:%s' % traceback.format_exc())


if __name__ == "__main__":
    logger.debug("router begining...")
    router = Router()
    router.run()
    logger.debug("router end.")
