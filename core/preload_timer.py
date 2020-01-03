# -*- coding:utf-8 -*-
"""
Created on 2011-5-26

@author: likun
"""

import simplejson as json
import sys
# log
import traceback, logging
from datetime import datetime, timedelta

from core import database, preload_worker, redisfactory
from util import log_utils

# logger = logging.getLogger('proload_timer')
# logger.setLevel(logging.DEBUG)
preload_cache = redisfactory.getDB(1)

logger = log_utils.get_rtime_Logger()

class Timers(object):
    def __init__(self, batch_size=100):
        self.batch_size = batch_size
        logger.debug('timer start. batch_size:%s !' % self.batch_size)
        self.dt = datetime.now()
        self.query_db = database.query_db_session()
        self.db = database.db_session()

    def timer_run(self):
        """
        preload定时任务运行

        """
        try:
            logger.debug("timer work begining...")
            task_list = [self.reset(task) for task in
                         self.query_db.preload_url.find({"status": "TIMER", "start_time": {"$lte": self.dt}})]
            url_dict = {}
            self.merge_preload_task(task_list, url_dict)
            for urls in list(url_dict.values()):
                preload_worker.dispatch.delay(urls)
            logger.debug("timer.work process messages end, count: %d " % len(task_list))
        except Exception:
            logger.warning('timer work error:%s' % traceback.format_exc())

    def reset(self, task):
        task['status'] = 'PROGRESS'
        task['created_time'] = task.get("start_time")
        self.db.preload_url.remove({"_id": task.get("_id")})
        return task

    def merge_preload_task(self, tasks, url_dict):
        """
        preload 定时任务分组函数
    
        :param tasks url_dict:
        """
        for task in tasks:
            url_dict.setdefault(task.get("channel_code"), []).append(task)


    def calllback(self):
        """
        未完成任务定期汇报进度
        {
        “task_id”:"123",
        “percent”:80
        },
        5分钟发送一次，状态为PROGRESS，created_time为1小时之内的任务
        """
        false = False  #为了将字符串转为字典
        true = True
        try:
            logger.debug("calllback begining...")
            for channel in self.query_db.preload_channel.find({"has_callback": 1}):
                callback_body = []
                for task in self.query_db.preload_url.find(
                        {"status": "PROGRESS", "channel_code": channel.get("channel_code"),
                         "created_time": {"$lte": self.dt, "$gte": self.dt - timedelta(seconds=3600)}}):
                    info = preload_worker.get_information(eval(preload_cache.get(task.get('_id'))))
                    callback_body.append({"task_id": task.get('task_id'), "percent": info.get('percent')})
                if callback_body:  #邮件内容为空不发
                    preload_worker.preload_callback(channel, callback_body)
            logger.debug("calllback end.")
        except Exception:
            print(e)
            logger.warning('callback work error:%s' % traceback.format_exc())


if __name__ == "__main__":
    logger.debug("timer begining...")
    timer = Timers()
    timer.timer_run()
    timer.calllback()
    logger.debug("timer end.")
    exit()