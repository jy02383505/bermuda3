# encoding=utf-8
'''
Created on 2012-9-28

@author: cooler
'''
import sys
import imp
imp.reload(sys)
sys.setdefaultencoding('utf8')
sys.path.append('/Application/bermuda3/')
import threading
import traceback
import logging
import time
from datetime import datetime, timedelta
from core import postal, verify, database ,queue
from core.models import STATUS_RETRY_SUCCESS
from core.update import db_update

# Try and reduce the stack size.
try:
    threading.stack_size(409600)
except:
    pass

logging.basicConfig(
    format='%(asctime)s %(levelname)s - %(message)s', filename='/Application/bermuda3/logs/retry_beated.log')
logger = logging.getLogger('monitor')
logger.setLevel(logging.DEBUG)


class Beat(threading.Thread):

    def __init__(self, db,query_db):
        self.db = db
        self.query_db = query_db
        threading.Thread.__init__(self)

    def run(self):
        while True:
            try:
                logger.debug("retry_beat...")
                self.retry_error_task(10)
                logger.debug("retry_beat end....")
            except Exception:
                logger.error(traceback.format_exc())
            time.sleep(60)

    def retry_error_task(self, num):
        global error_tasks, count, mutex
        error_tasks = [task for task in self.query_db.error_task.find(
            {'status': 'OPEN', 'created_time': {'$gte': datetime.now() - timedelta(minutes=35)},'retryCount': None })]
        count = 0
        if len(error_tasks) > 0:
            logger.debug("error_tasks Count : %s" % (len(error_tasks)))
            threads = []
            mutex = threading.Lock()
            for x in range(0, num):
                threads.append(
                    threading.Thread(target=retry_task, args=(self.db,self.query_db)))
            for t in threads:
                t.start()
            # 主线程中等待所有子线程退出
            for t in threads:
                t.join()
            logger.debug("all task retry over!")
        else:
            logger.debug("there is no error_tasks")


def retry_task(db,query_db):
    global error_tasks, count, mutex
    while count < len(error_tasks):
        mutex.acquire()
        task = error_tasks[count]
        count = count + 1
        # 释放锁
        mutex.release()
        threadname = threading.currentThread().getName()
        logger.debug("threadname:[ %s ] -- error_tasks retry [%s/%s]" %
                     (threadname, count, len(error_tasks)))
        if task.get('urls')[0].get('isdir'):
            session_id, command = postal.getDirCommand(task.get('urls'))
        else:
            command = postal.getUrlCommand(task.get('urls'))
        logger.debug("HOST %s , task retryCount:%s" %
                     (task.get('host'), task.get('retryCount', 0)))
        results, wrongRet = postal.doSend_HTTP(
            [{"host": task.get('host')}], command)
        update_error_task(task, results, db,query_db)


def update_error_task(task, results, db ,query_db):
    task['retryCount'] = task.get('retryCount', 0) + 1
    if results:
        task['retryCount'] = -2
        db.error_task.save(task)
        db_update(db.device,{"_id": task.get("dev_id")},{"$set":{"devices.%s.code" % task.get('name') :STATUS_RETRY_SUCCESS}})
        logger.debug('successed, task_id = %s dev_id = %s host=%s...' % (task.get("_id"),task.get("dev_id"),task.get("host")))
        if not query_db.error_tasks.find({"dev_id":task.get("dev_id"),"retryCount":{'$ne': -2},"status":'OPEN'}).count():
            verify.verify(task.get("urls"), db, 'FINISHED')
    else:
        db.error_task.save(task)
    if task.get('retryCount') == 1:
        logger.debug(
            "retryCount:3, status:FAILED,task_id : %s dev_id : %s..." %
            (task.get("_id"), task.get("dev_id")))
        verify.verify(task.get("urls"), db, 'FAILED')
        queue.put_json2("error_task",[get_queue(task)])

def get_queue(task):
    queue = {"_id":str(task.get("_id")),"channel_code":task.get("urls")[0].get("channel_code"),'host':task.get("host")}
    queue['urls'] = [{"url":u.get("url"),"username":u.get("username")} for u in task.get("urls")]
    return queue

if __name__ == "__main__":
    beat = Beat(database.db_session(),database.query_db_session())
    beat.setName('retry_beat')
    beat.setDaemon(True)
    beat.run()
