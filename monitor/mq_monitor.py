# -*- coding:utf-8 -*-
'''
Created on 2012-7-3

@author: wenwen
'''
import threading, time, traceback, urllib.request, urllib.error, urllib.parse, urllib.request, urllib.parse, urllib.error
#from pymongo import ReplicaSetConnection
# from pymongo import MongoClient
from datetime import datetime
from core import sendEmail
from core.config import initConfig
from core import database

# Try and reduce the stack size.
try:
    threading.stack_size(409600)
except:
    pass

import logging

logging.basicConfig(format='%(asctime)s %(levelname)s - %(message)s',
                    filename='/Application/bermuda3/logs/mq_monitor.log')



SMSURL = "http://sms.chinacache.com/ReceiverSms"

class Monitor(threading.Thread):
    logging.info('mq_monitor start.')
    def __init__(self, db):
        self.db = db
        self.threshold = {'url_queue': 10000, 'celery': 3000, 'refresh': 3000, 'email': 3000, 'error_task': 10000,
                           'preload':50000,'preload_task': 11000}
        self.threshold_noc = {'url_queue': 10000, 'celery': 3000, 'refresh': 3000, 'email': 5000, 'error_task': 10000,
                              'preload':50000,'preload_task': 11000}
        self.agent_last_send_time = ''
        threading.Thread.__init__(self)

    def run(self):
        logging.info('mq_monitor start.')
        while True:
            try:
                time.sleep(300)
                logging.info('do job.')
                self.do_job()
            except Exception:
                logging.error(traceback.format_exc())

    def do_job(self):
        alert_messages = []
        alert_messages_noc = []
        logging.info('mq_monitor start.')
        for mq in self.db.mq_status.find():
            server_name = mq.get('_id')
            print(server_name,mq.get('update_time'))
            if time.mktime(datetime.now().timetuple()) - time.mktime(mq.get('update_time').timetuple()) > 300 and (
                    self.agent_last_send_time == '' or time.mktime(
                    datetime.now().timetuple()) - self.agent_last_send_time > 1800):
                alert_messages.append("%s ageng is down!" % server_name)
                self.agent_last_send_time = time.mktime(datetime.now().timetuple())
            for queue_status in mq.get('status'):
                if self.threshold.get(queue_status['name'], 0) < int(queue_status['m_ready']):
                    alert_messages.append("%s %s %s" % (server_name, queue_status['name'], queue_status['m_ready']))

            for queue_status in mq.get('status'):
                if self.threshold_noc.get(queue_status['name'], 0) < int(queue_status['m_ready']):
                    alert_messages_noc.append("%s %s %s" % (server_name, queue_status['name'], queue_status['m_ready']))
        config = initConfig()
        refresh_email = config.get('refresh_noc_monitor', 'refresh_email').split(',')
        subject = "**队列堆积报警**"
        mailContent = ""
        for message in alert_messages:
            mailContent += message + "\n"
            logging.warn(message)
            #args = {"content": message, "phonenum": "15910506097;13717961668;15801269880;15910506922"}
            #urllib.request.urlopen("http://logmonitor.chinacache.net:8888/mobile/", urllib.urlencode(args), timeout=10)
            #根总借的帐号
            config = {"username":"1295410062943JJQ","password":"nocbrother","mobile":"15910506097;13717961668;15801269880;15910506922","content":message}
            query = urllib.parse.urlencode(config)
            print(urllib.request.urlopen(SMSURL, query, timeout=10).read())
        mailContent_noc = "刷新队列堆积报警，请通知刷新组维护人员（张宏安、于善良、马欢）\n"
        subject_noc = "**队列堆积报警**"
        noc_email = config.get('refresh_noc_monitor', 'noc_email').split(',')
        for message in alert_messages_noc:
            mailContent_noc += message + "\n"
            logging.warn("refresh queue detail: %s: " % (message))
        try:
            if len(alert_messages) > 0:
                sendEmail.send(refresh_email, subject, mailContent.encode('utf8'))
            if len(alert_messages_noc) > 0:
                sendEmail.send(noc_email, subject_noc, mailContent_noc.encode('utf8'))
        except Exception:
            logging.debug(e)


if __name__ == '__main__':
    # agent = Monitor(
    #     MongoClient('%s:27017,%s:27017,%s:27017' % ('172.16.12.134', '172.16.12.135', '172.16.12.136'),
    #                          replicaSet='bermuda_db')['bermuda'])
    agent = Monitor(database.query_db_session())
    #agent.setName('mq_monitor')
    #agent.setDaemon(True)
    #agent.run()
    agent.do_job()
    exit()
