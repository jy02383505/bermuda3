# -*- coding:utf-8 -*-
'''
Created on 2011-5-26

@author: wenwen
'''

# from util import log_utils
# import time
import pika
from contextlib import contextmanager
from .config import config
import simplejson as json
from pika.adapters.select_connection import SelectConnection
# import logging
#
# LOG_FILENAME = '/Application/bermuda3/logs/debug.log'
# logging.basicConfig(filename=LOG_FILENAME, format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s', level=logging.INFO)
#
#
# logger = logging.getLogger('debug')
# logger.setLevel(logging.DEBUG)

from celeryconfig import BROKER_USER, BROKER_PASSWORD, BROKER_HOST, BROKER_PORT

BROKER_URL = 'amqp://{0}:{1}@{2}:{3}/%2F'.format(BROKER_USER, BROKER_PASSWORD, BROKER_HOST, BROKER_PORT)
# BROKER_URL = 'amqp://bermuda:bermuda@223.202.52.83:5672/%2F'
# BROKER_URL = 'amqp://bermuda:bermuda@101.251.97.251:5672/%2F'
#有的服务器不允许直接使用/, 但是允许用它的ASCII码形式.
#%2F表示ASCII码0x2F(47)对应的字符, 即/.

# logger = log_utils.get_preload_Logger()

class MQ_Client():
    def __init__(self, host, queue, messages):
        self.host = host
        self.messages = messages
        self.queue = queue
        self.connection = None
        self.channel = None

    def on_connected(self, connection):
        connection.channel(self.on_channel_open)


    def on_channel_open(self, channel_):
        self.channel = channel_
        self.channel.queue_declare(queue=self.queue, durable=True,
                              exclusive=False, auto_delete=False,
                              callback=self.on_queue_declared)


    def on_queue_declared(self, frame):
        for message in self.messages:
            self.channel.basic_publish(exchange='',
                                  routing_key=self.queue,
                                  body=json.dumps(message),
                                  properties=pika.BasicProperties(
                                      content_type="text/plain",
                                      delivery_mode=1))

        # Close our connection
        self.connection.close()

    # def do_send(self, st=0, iname=''):
    #     parameters = pika.URLParameters(BROKER_URL)
    #     # credentials = pika.credentials.PlainCredentials(BROKER_USER, BROKER_PASSWORD)
    #     # parameters = pika.ConnectionParameters(self.host, credentials=credentials)

    #     logger.debug("do_send[%s -- takes(before connection)]: %s seconds." % (iname, (time.time()-st), ))
    #     self.connection = SelectConnection(parameters, self.on_connected)
    #     logger.debug("do_send[%s -- takes(after connection)]: %s seconds." % (iname, (time.time()-st), ))
    #     try:
    #         logger.debug("do_send[%s -- takes(before ioloop.start)]: %s seconds." % (iname, (time.time()-st), ))
    #         self.connection.ioloop.start()
    #         logger.debug("do_send[%s -- takes(after ioloop.start)]: %s seconds." % (iname, (time.time()-st), ))
    #     except KeyboardInterrupt:
    #         self.connection.close()
    #         self.connection.ioloop.start()

    def do_send(self):
        parameters = pika.URLParameters(BROKER_URL)
        # credentials = pika.credentials.PlainCredentials(BROKER_USER, BROKER_PASSWORD)
        # parameters = pika.ConnectionParameters(self.host, credentials=credentials)

        self.connection = SelectConnection(parameters, self.on_connected)
        try:
            self.connection.ioloop.start()
        except KeyboardInterrupt:
            self.connection.close()
            self.connection.ioloop.start()

def put(queue, messages):
    with queue_channel(queue) as channel:
        for message in messages:
            channel.basic_publish(exchange='',
                                  routing_key=queue,
                                  body=message.encode("utf-8"),
                                  properties=pika.BasicProperties(
                                     delivery_mode=2, # make message persistent
                                  ))
def put_json(queue, messages):
    with queue_channel(queue) as channel:
        for message in messages:
            channel.basic_publish(exchange='',
                                  routing_key=queue,
                                  body=json.dumps(message).encode("utf-8"),
                                  properties=pika.BasicProperties(
                                     delivery_mode=2, # make message persistent
                                  ))

# def put_json2(queue, messages, st=0, iname='/internal/preloadDevice'):
#     try:
#         logger.debug("put_json2[%s -- takes(enter)]: %s seconds." % (iname, (time.time()-st), ))
#         client = MQ_Client(config.get('rabbitmq', 'host'), queue, messages)
#         logger.debug("put_json2[%s -- takes(MQ_Client)]: %s seconds." % (iname, (time.time()-st), ))
#         client.do_send(st=st, iname=iname)
#         logger.debug("put_json2[%s -- takes(after do_send)]: %s seconds." % (iname, (time.time()-st), ))
#     except:
#         client = MQ_Client(config.get('rabbitmq', 'bak_host'), queue, messages)
#         client.do_send()

def put_json2(queue, messages):
    try:
        client = MQ_Client(config.get('rabbitmq', 'host'), queue, messages)
        client.do_send()
    except:
        client = MQ_Client(config.get('rabbitmq', 'bak_host'), queue, messages)
        client.do_send()

def get(queue, batch_size):
    with queue_channel(queue) as channel:
        bodys = []
        while batch_size > 0:
            method_frame, header_frame, body = channel.basic_get(queue=queue)
            batch_size = batch_size - 1
            if method_frame:
                channel.basic_ack(delivery_tag=method_frame.delivery_tag)
                bodys.append(body)
            else:
                print('no message return')
                break
            # if method_frame.NAME == 'Basic.GetEmpty':
            #     break
            # else:
            #     channel.basic_ack(delivery_tag=method_frame.delivery_tag)
            #     bodys.append(body)
        return bodys

def clear(queue):
    with queue_channel(queue) as channel:
        while True:
            method_frame, header_frame, body = channel.basic_get(queue=queue)
            if method_frame.NAME == 'Basic.GetEmpty':
                break
            else:
                channel.basic_ack(delivery_tag=method_frame.delivery_tag)

@contextmanager
def queue_channel(queue):
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
    parameters = pika.URLParameters(BROKER_URL)
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

@contextmanager
def batch_messages(queue, batch_size):
    with queue_channel(queue) as channel:
        delivery_tags = []
        try:
            bodys = []
            while batch_size > 0:
                method_frame, header_frame, body = channel.basic_get(queue=queue)
                batch_size = batch_size - 1
                if method_frame.NAME == 'Basic.GetEmpty':
                    break
                else:
                    delivery_tags.append(method_frame.delivery_tag)
                    bodys.append(body)

            yield bodys
            for delivery_tag in delivery_tags:
                channel.basic_ack(delivery_tag=delivery_tag)
        except Exception:
            raise e


if __name__ == '__main__':
    queuename='url_queue'
    # put_json2(queuename,'abcdefg')
    print(get(queuename,3))





#