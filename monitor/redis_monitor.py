# -*- coding:utf-8 -*-
'''
Created on 2012-7-3

@author: wenwen
'''
import threading , time, traceback, urllib.request, urllib.error, urllib.parse, urllib.request, urllib.parse, urllib.error
from datetime import datetime
from core import sendEmail
from core.config import initConfig

import logging, redis

# Try and reduce the stack size.
try:
    threading.stack_size(409600)
except:
    pass

logging.basicConfig(format = '%(asctime)s %(levelname)s - %(message)s', filename = '/Application/bermuda3/logs/redis_monitor.log')
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

class Monitor(threading.Thread):
    def __init__(self ):
        threading.Thread.__init__(self)

    def run(self):
        logger.debug('redis_monitor start.')
        while True:
            try:
                logger.debug('do job.')
                self.do_job()
                logger.debug('do job end.')
                time.sleep(1800)
            except Exception:
                logger.error(traceback.format_exc())


    def do_job(self):
        refresh_email = initConfig().get('refresh_noc_monitor', 'refresh_email').split(',')
        subject = "**redis监控**"
        mailContent = ""
        alert_messages = []
        if self.check_redis(initConfig().get('redis', 'host'),6379) != "ok":
            alert_messages.append(self.check_redis(initConfig().get('redis', 'host'),6379))
        if self.check_redis(initConfig().get('redis', 'host_bak'),6379) != "ok":
            alert_messages.append(self.check_redis(initConfig().get('redis', 'host_bak'),6379))
        for message in alert_messages:
            mailContent += str(message)+"\n"
            logger.debug(message)
            args = {"content": str(message), "phonenum": "13683011499;13910311138;18600219291"}
            urllib.request.urlopen("http://logmonitor.chinacache.net:8888/mobile/", urllib.parse.urlencode(args), timeout = 10)
        try :
            if len(alert_messages)>0 :
                sendEmail.send(refresh_email,subject, mailContent.encode('utf8'))
        except Exception:
            logger.debug(e)

    def check_redis(self,host,port):
        try:
            r_db = redis.Redis(host=host, port=port, db=0)
            list(r_db.keys())
            return "ok"
        except Exception:
            return e


if __name__ == '__main__':
    agent = Monitor()
    agent.setName('mq_monitor')
    agent.setDaemon(True)
    agent.run()
 