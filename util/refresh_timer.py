# -*- coding:utf-8 -*-
__author__ = 'cl'
import time,logging

import simplejson as json
from datetime import datetime
from core import splitter,database
from core.models import URL_OVERLOAD_PER_HOUR, DIR_OVERLOAD_PER_HOUR

LOG_FILENAME = '/Application/bermuda3/logs/timer.log'
logging.basicConfig(filename = LOG_FILENAME, format = '%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s', level = logging.INFO)

logger = logging.getLogger('refresh_timer')
logger.setLevel(logging.DEBUG)

db = database.db_session()

class Timer():
    def __init__(self,sleep_time, worker,task={}):
        self.worker = worker
        self.task = task
        self.sleep_time = sleep_time

    def run(self):
        time.sleep(self.sleep_time)
        self.worker(self.task)

def worker(tasks={}):
    try:
        logger.debug('work is Start !')
        for refresh_task in list(tasks.values()):
            refresh_task["URL_OVERLOAD_PER_HOUR"] = URL_OVERLOAD_PER_HOUR
            refresh_task["DIR_OVERLOAD_PER_HOUR"] = DIR_OVERLOAD_PER_HOUR
            splitter.process(db,refresh_task)
            logger.debug('splitter.process task : %s!' % refresh_task)
        logger.debug('work is Stop !')
    except Exception:
        logger.warn("worker error. expected:%s " % e)

def create_task(timer_task):
    try:
        run_time = datetime(datetime.now().year,datetime.now().month,datetime.now().day+1,int(timer_task.get("run_time")[0]),int(timer_task.get("run_time")[1]))
        t = Timer( (run_time - datetime.now()).seconds,worker,timer_task.get('tasks'))
        logger.debug('%s timer is run ' % run_time)
        t.run()
    except Exception:
        logger.warn("create_task error. expected:%s " % e)

def init_task_list():
    try:
        timer_tasks =[t for t in db.timer_task.find()]
        timer_tasks.sort(key=lambda x:x.get("run_time"))
        for timer_task in timer_tasks:
            logger.debug('create_task task:%s'% timer_task )
            create_task(timer_task)
    except Exception:
        logger.warn("init_task_list error. expected:%s " % e)

if __name__ == "__main__":
    logger.debug("timer is Start!")
    init_task_list()
    logger.debug("timer is Stop!")
