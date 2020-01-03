# -*- coding: utf-8 -*-
from core.config import config
from celery import Celery
#from core.database import db_session
from core import redisfactory
import datetime
import sys, os, socket

CACHE = redisfactory.getMDB(7)

def my_monitor(app):
    state = app.events.State()

    def record_tasks(event):

       # print '--------------event-----------'
       # print event

        state.event(event)
        # task name is sent only with -received event, and state
        # will keep track of this for us.
        task = state.tasks.get(event['uuid'])

       # print '-------------task-------------'
       # print task

        hostname = event['hostname']
        #print 111111111111111111111
        #print task.name
        #print 222222222222222222222
        if task.name in ['core.splitter_new.submit', 'core.splitter.submit']:
          add_count('receiver',hostname)
        elif task.name in ['core.url_refresh.work','core.dir_refresh.work']:
          add_count('refresh',hostname)

       # print('TASK FAILED: %s[%s] %s' % (
       #     task.name, task.uuid, task.info(), ))

    with app.connection() as connection:
        recv = app.events.Receiver(connection, handlers={
               # 'task-sent': record_tasks,
                'task-received': record_tasks,
               # 'task-succeeded': record_tasks,
               # 'task-failed': record_tasks,
        })
        recv.capture(limit=None, timeout=None, wakeup=True)


def add_count(_type, host_info):
    '''
    type: receiver/refresh
    '''

    _, hostname = host_info.split('@')

    #print _type, host_info, hostname

    now = datetime.datetime.now()
    now_key = now.strftime('%Y-%m-%d')
    h = now.hour
    _s = int(now.minute) * 60 + int(now.second)
    _key = '%s_%s_%s' %(hostname, h, _type)
    CACHE.hincrby(_key, _s, 1)

    #TODO 过期时间
    if not CACHE.ttl(_key):
        CACHE.expire(_key, 2*3600)

    if _type == 'receiver':
        receiver_group = eval(config.get('monitor', 'receiver_group'))
        receiver_all_key = '%s_%s_receiver'%(receiver_group[0][0], h)
        #记录总值
        CACHE.hincrby(receiver_all_key, _s, 1)
        #记录最高值
        sort_all_key = '%s_%s_receiver_sort' %(receiver_group[0][0], now_key)
        sort_sub_key = now.strftime('%H:%M:%S')
        CACHE.zincrby(sort_all_key, sort_sub_key, 1)
        if not CACHE.ttl(receiver_all_key):
            CACHE.expire(receiver_all_key, 2*3600)
        if not CACHE.ttl(sort_all_key):
            CACHE.expire(sort_all_key, 7*24*3600)


  #  print '##################'
  #  print now
  #  print '##################'
  #  print CACHE.hgetall(_key)
  #  print '##################'

def run():

    BROKER_USER = BROKER_PASSWORD = 'bermuda'
    BROKER_HOST = config.get('rabbitmq', 'host')
    BROKER_PORT = 5672
    BROKER_URL = 'amqp://{0}:{1}@{2}:{3}//'.format(BROKER_USER, BROKER_PASSWORD, BROKER_HOST, BROKER_PORT)
    app = Celery(broker=BROKER_URL)
    my_monitor(app)


if __name__ == '__main__':

    run()


