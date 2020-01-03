#encoding=utf8
'''
Created on 2011-11-7

@author: IBM
'''

import datetime,logging
import simplejson as json
from . import postal ,database

logger = logging.getLogger('retry')
logger.setLevel(logging.DEBUG)

ydt = datetime.datetime.now() - datetime.timedelta(hours=24)
dt = datetime.datetime.now()
device_status_cache = {}

db = database.db_session()

def retry(device):
    try:
        host = device.get('ip')
        device["created_time"] = dt
        device["status"] = "Doing"
        for task in db.error_task.find({"created_time": {"$gte": ydt}, "host": host}):
            logger.debug('retry doSend_HTTP error_task id:%s host:%s.' % (str(task['_id']), host))            
            if task.get('urls')[0].get('isdir'):
                ssid,command = postal.getDirCommand(task['urls'])
            else:
                command = postal.getUrlCommand(task.get('urls'))

            dev = {"host": task.get('host')}
            results, wrongRet = postal.doSend_HTTP([dev], command)
            if results:
                db.error_task.remove({'_id': task['_id']})
                logger.debug('delete error_task id:%s host:%s.' % (str(task['_id']), host))
    except Exception:
        logger.error('device:%s retry error!' % host, e)


def readconf(conf_file):
    filehandler = open(conf_file, 'r')
    conf = filehandler.read()
    logger.debug('read retry config:%s.' % conf)
    devices = json.loads(conf)
    for device in devices:
        retry(device)


