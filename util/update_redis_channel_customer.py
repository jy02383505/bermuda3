#! -*- coding=utf-8 -*-
"""
@version: ??
@author: rubin
@license:
@contact: longjun.zhao@chinacache.com
@site: 
@software: PyCharm
@file: updae_redis_channel_customer.py
@time: 16-8-30 下午4:17
"""
from stompy import Stomp
import simplejson as json
import logging
import core.rcms_change_worker as rcms_change_worker
from cache.rediscache import device_cache, firstlayer_cache, channels_cache
from core.config import config
import traceback
import pika

# LOG_FILENAME = '/Application/bermuda3/logs/update_redis_channel_customer.log'
# logging.basicConfig(filename=LOG_FILENAME,
#                     format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s',
#                     level=logging.INFO)
#
# logger = logging.getLogger('update_redis_channel_customer')
# logger.setLevel(logging.DEBUG)

LOG_FILENAME = '/Application/bermuda3/logs/update_redis_channel_customer.log'
# LOG_FILENAME = '/home/rubin/logs/update_redis_channel_customer.log'
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s")
fh = logging.FileHandler(LOG_FILENAME)
fh.setFormatter(formatter)

logger = logging.getLogger('update_redis_channel_customer')
logger.addHandler(fh)
logger.setLevel(logging.DEBUG)


def logger_redis_info(_id, _type, step):
    """
    according _id _type,step logger info of redis
    :param _id:
    :param _type:
    :param step:
    :return:
    """
    try:
        if _type == 'customer':
            _id = 'c_by_%s' %(_id)
            logger.debug('############%s %s###############'%(_id, step))
            logger.debug(channels_cache.hgetall(_id))
            logger.debug('############%s %s over##########'%(_id, step))
        elif _type == 'channel':
            _id_d = 'd_by_%s' %(_id)
            logger.debug('############%s %s###############'%(_id, step))
            logger.debug("down layer dev:%s" % device_cache.hgetall(_id_d))
            _id_f =  'fd_by_%s' % _id
            logger.debug("first layer dev:%s" % firstlayer_cache.hgetall(_id_f))
            logger.debug('############%s %s over##########'%(_id, step))
    except Exception:
        logger.error('logger_test_redis error is %s' % e)


def load_task(body):
    """
    parse json data
    :param body:
    :return:
    """
    try:
        return json.loads(body)
    except Exception:
        logger.debug("parse json data:%s, error:%s" % (body, e))
        return {'cumstomerIds': [], 'channelIds': []}


def on_message(channel, method_frame, header_frame, body):
    # channel.queue_declare(queue=body, auto_delete=True)
    print("body:%s" % body)
    channel.basic_ack(delivery_tag=method_frame.delivery_tag)

    result = {}
    try:
        result = load_task(body).get('ROOT').get('BODY').get('BUSI_INFO')
    except Exception:
        logger.error("result error:%s" % traceback.format_exc())
        logger.info('result frame.body:%s' % body)
    # get customer id list
    customerIds = result.get('customerIds', [])
    # get channels id list
    channelIds = result.get('channelIds', [])

    if channelIds:
        for c in channelIds:
            logger_redis_info(c, 'channel', 'before')
    if customerIds:
        for _c in customerIds:
            logger_redis_info(_c, 'customer', 'before')
    logger.debug("customerIds:%s, channelIds:%s" % (customerIds, channelIds))
    rcms_change_worker.get_new_info(channelIds, customerIds)
    if channelIds:
        for c in channelIds:
            logger_redis_info(c, 'channel', 'after')
    if customerIds:
        for _c in customerIds:
            logger_redis_info(_c, 'customer', 'after')


def main_fun():
    """
    main of the function
    :return:
    """
    credentials = pika.PlainCredentials(config.get('rcms_activemq', 'username'), config.get('rcms_activemq', 'password'))
    # parameters =  pika.ConnectionParameters('223.202.203.52', credentials=credentials, virtual_host='cms3')
    parameters =  pika.ConnectionParameters(config.get('rcms_activemq', 'host'),port=5672, credentials=credentials, virtual_host='cms3')
    connection = pika.BlockingConnection(parameters)

    channel = connection.channel()
    # channel.exchange_declare(exchange="test_exchange", exchange_type="direct", passive=False, durable=True, auto_delete=False)
    channel.queue_declare(queue="CMS3.channel.refresh", durable=True, auto_delete=False)
    # channel.queue_bind(queue="rabbit.test", exchange="test_exchange", routing_key="standard_key")
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(on_message, 'CMS3.channel.refresh')
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        channel.stop_consuming()

if __name__ == '__main__':
    main_fun()
