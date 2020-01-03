#! /usr/bin/env python
# -*- coding: utf-8 -*-
from redis.exceptions import WatchError
import sys

__author__ = 'vance'
__date__ = '15-9-18'

import simplejson as json
import pika
import pickle
from contextlib import contextmanager
import datetime
import redis
from pika.adapters.select_connection import SelectConnection
import logging
from celeryconfig import BROKER_USER, BROKER_PASSWORD, BROKER_HOST, BROKER_PORT


LOG_FILENAME = '/Application/bermuda3/logs/process_mq.log'
formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s")
fh = logging.FileHandler(LOG_FILENAME)
fh.setFormatter(formatter)

logger = logging.getLogger('process_mq')
logger.addHandler(fh)
logger.setLevel(logging.DEBUG)
# BROKER_URL = 'amqp://{0}:{1}@{2}:{3}/%2F'.format(BROKER_USER, BROKER_PASSWORD, BROKER_HOST, BROKER_PORT)
BROKER_URL = 'amqp://bermuda:bermuda@{0}:5672/%2F'


@contextmanager
def queue_channel(b_url,queue):
    # print BROKER_USER
    # print BROKER_PASSWORD
    #
    # hst1=config.get('rabbitmq', 'host')
    #
    # print hst1
    # credentials = pika.PlainCredentials(BROKER_USER, BROKER_PASSWORD)
    # # credentials = pika.PlainCredentials('guest', 'guest')
    # conn=pika.ConnectionParameters(host=hst1, credentials=credentials)
    # # conn=pika.ConnectionParameters(host=config.get('rabbitmq', 'host'), credentials=None)
    # connection = pika.BlockingConnection(conn)

    # logger.debug('BROKER_URL:%s'%(BROKER_URL))
    parameters = pika.URLParameters(b_url)
    connection = pika.BlockingConnection(parameters)

    channel = connection.channel()
    channel.queue_declare(queue=queue, durable=True)
    # logger.debug('channel:%s'%(str(channel)))
    try:
        yield channel
    except Exception:
        raise
    finally:
        connection.close()

PRELOAD_CACHE = redis.StrictRedis(host='%s' % '172.16.21.28', port=6379, db=1)

def unlock(key):
    cache_body = {}
    has_lock = False
    try:
        pipe = PRELOAD_CACHE.pipeline()
        while 1:
            try:
                # 对序列号的键进行 WATCH
                pipe.watch(key)  # 监控字段变化，如果在未处理之前有变化，直接报错
                # WATCH 执行后，pipeline 被设置成立即执行模式直到我们通知它
                # 重新开始缓冲命令。
                # 这就允许我们获取序列号的值
                print(key)
                pip_cache_body = pipe.get(key)
                # print pip_cache_body
                if not pip_cache_body:
                    return has_lock, cache_body
                cache_body = json.loads(pip_cache_body)

                if cache_body.get("lock"):
                    cache_body["lock"] = False
                    pipe.multi()  # 对数据进行缓存
                    pipe.set(key, json.dumps(cache_body))
                    # PRELOAD_CACHE.set(key,json.dumps(cache_body))
                    pipe.execute()
                    has_lock=True
                break
            except WatchError:
                logger.debug("watch error:%s" % key)
                continue
            finally:
                pipe.reset()

    except Exception:
        logger.debug("has_lock error:%s." % e)
    return has_lock

def get(b_url,queue, batch_size):
    now = datetime.datetime.now()
    last_time = now - datetime.timedelta(hours=1)

    log_file = '/Application/bermuda3/logs/redis.txt'
    f = file("%s" % log_file, "a")

    with queue_channel(b_url,queue) as channel:
        bodys = []
        while batch_size > 0:
            method_frame, header_frame, body = channel.basic_get(queue=queue)
            batch_size = batch_size - 1
            if method_frame:
                try:
                    body_context = pickle.loads(body)
                    for arg in body_context["args"]:
                        if "finish_time" in arg:
                            # print arg["finish_time"],body_context
                            cur_time = datetime.datetime.strptime(arg["finish_time"],"%Y-%m-%d %H:%M:%S")
                            print(cur_time, last_time)
                            if cur_time < last_time:
                                # channel.basic_ack(delivery_tag=method_frame.delivery_tag)
                            #     bodys.append(body_context)
                            #     print "process:",arg["url_id"]
                                unlock(arg["url_id"])
                                f.write(arg["url_id"] + "\r\n")
                                logger.debug(PRELOAD_CACHE.get(arg["url_id"]))
                                # logger.debug(body_context)
                            # else:
                            #     channel.basic_publish(exchange ='preload',
                            #    routing_key = 'preload',
                            #    body = body)
                        else:
                            # print body_context
                            # print body_context["args"][0]["finish_time"]
                            logger.debug(body_context)
                            channel.basic_publish(exchange ='preload',
                               routing_key = 'preload',
                               body = body)
                except Exception:
                    print(traceback.format_exc())
                    logger.error(traceback.format_exc())
                    logger.error(body)

            else:
                print('no message return')
                break
            # if method_frame.NAME == 'Basic.GetEmpty':
            #     break
            # else:
            #     channel.basic_ack(delivery_tag=method_frame.delivery_tag)
            #     bodys.append(body)

        f.flush()
        f.close()
        return bodys

if __name__ == '__main__':
    # [refresh@BGP-BJ-C-5H9 bermuda]$ bin/python lib/python2.6/site-packages/bermuda-5.3.dev_r12792-py2.6.egg/util/check_preload_mq.py 223.202.52.139
    queuename='preload'
    # put_json2(queuename,'abcdefg')
    receiver_list=[]
    print(len(sys.argv))
    if len(sys.argv) > 1:
        receiver_list.append(sys.argv[1])
    else:
        receiver_list = ["223.202.52.43","223.202.52.44","223.202.52.45","223.202.52.139"]
    print(receiver_list)
    for rr in receiver_list:
        print(rr)
        b_url=BROKER_URL.format(rr)
        print(b_url)
        get(b_url,queuename,10000)
    # unlock("56036e3d40780740cbda35b3")