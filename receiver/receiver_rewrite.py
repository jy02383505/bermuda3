#-*- coding: UTF-8 -*-
"""
@author:rubin
@create time 2016/06/07
"""

from bson import ObjectId
from core import redisfactory, rcmsapi
from datetime import datetime, timedelta
from core.database import query_db_session,db_session
from logging import Formatter
import traceback
import logging,hashlib ,re
import logging.handlers
import httplib2 as httplib
import pymongo,math,time
import simplejson as json
from util import log_utils
from util.tools import operation_record_into_mongo

# logger = logging.getLogger("admin")
# logger.setLevel(logging.DEBUG)
# logger = log_utils.get_admin_Logger()
logger = log_utils.get_receiver_Logger()

db = db_session()
q_db = query_db_session()


REWRITE_CACHE = redisfactory.getDB(15)




def rewrite_query_n_to_n(username, channel_name):
    """
    according username,channel_name, to find the relationship with the channel_name,
    :param username: the name of user
    :param channel_name: the name of url
    :return: the list of collection rewrite_new like [{'_id':xxx, 'username':xxxx, 'channel_list':XXXx},\
          {'_id':xxx, 'username':xxxx, 'channel_list':XXXx}]
    """
    list_rewrite = []
    if username == '':
        logger.debug("username is None!")
        return list_rewrite
    try:
        list_rewrite_temp = q_db.rewrite_new.find({"username": username})
    except Exception:
        logger.debug("can not get data from collection of rewrite_new, except:%s" % e)

    if channel_name == '':
        # solve json serializable problem
        for channel in list_rewrite_temp:
            list_rewrite.append(channel)
        return list_rewrite
    else:
        for channel in list_rewrite_temp:
            list_r = channel.get("channel_list", '')
            if list_r:
                if channel_name in list_r:
                    # if channel_name eq url in rewrite_list, add channel to list_rewrite
                    logger.debug("channel:%s" % channel)
                    # list_rewrite.append(channel)
                    # return list_rewrite
                    list_rewrite.append(channel)

        logger.debug("list_rewriet:%s" % list_rewrite)
        return list_rewrite


def rewrite_query(username, channel_name):
    """
    according username,channel_name, to find the relationship with the channel_name,
    :param username: the name of user
    :param channel_name: the name of url
    :return: the list of collection rewrite_new like [{'_id':xxx, 'username':xxxx, 'channel_list':XXXx},\
          {'_id':xxx, 'username':xxxx, 'channel_list':XXXx}]
    """
    list_rewrite = []

    try:
        if username == '':
            list_rewrite_temp = q_db.rewrite_new.find()
        else:
            list_rewrite_temp = q_db.rewrite_new.find({"username": username})
    except Exception:
        logger.debug("can not get data from collection of rewrite_new, except:%s" % e)

    if channel_name == '':
        # solve json serializable problem
        for channel in list_rewrite_temp:
            list_rewrite.append(channel)
        return list_rewrite
    else:
        for channel in list_rewrite_temp:
            list_r = channel.get("channel_list", '')
            if list_r:
                if channel_name in list_r:
                    # if channel_name eq url in rewrite_list, add channel to list_rewrite
                    logger.debug("channel:%s" % channel)
                    # list_rewrite.append(channel)
                    # return list_rewrite
                    list_rewrite.append(channel)

        logger.debug("list_rewriet:%s" % list_rewrite)
        return list_rewrite





def update_rewrite_no_id(data):
    """
    according data,data has no id, insert into rewrite_new and update redis
    :param data: the content of rewrite_new
    :return:
    """
    username = data.get("username", '')
    channel_list = data.get("channel_list", '')
    length_c = len(channel_list)
    if username and channel_list and length_c >= 2:
        # first insert data into mongodb, then update redis
        try:
            db.rewrite_new.insert(data)
            operation_record_into_mongo(data.get('user_email'), 'channel_redirection', 'insert', data)
        except Exception:
            logger.debug("update_rewrite_no_id, insert mongo error,username:%s, Exception:%s" % (username, e))
            return json.dumps({'msg': 'error', 'result': 'update_rewrite_no_id  exception:%s' % e})
        try:

            for i in range(length_c):
                channel = channel_list[i]
                channel_redis = REWRITE_CACHE.get(channel)
                channel_list.pop(i)
                if channel_redis:
                    # rewrite the redis info
                    rewrite_name = channel_redis + "," + (',').join(channel_list)
                    REWRITE_CACHE.set(channel, rewrite_name)
                    logger.debug("update redis success have channel:%s" % channel)
                else:
                    # direct update redis
                    REWRITE_CACHE.set(channel, (',').join(channel_list))
                    logger.debug("update redis success do not have channel:%s" % channel)
                channel_list.insert(i, channel)
        except Exception:
            logger.debug("update_rewrite_no_id, update redis error, username:%s, Exception:%s" % (username, e))
            return json.dumps({'msg': 'error', 'result': 'update_rewrite_no_id  exception:%s' % e})
        return json.dumps({'msg': 'ok', 'result': 'rewrite success!'})
    return json.dumps({'msg':'error', 'result': 'received data has problem'})







def update_rewrite_id(data):
    """
    according the data, update the mongo  and redis
    :param data:
    :return:
    """
    id = data.get("id", '')
    username = data.get("username", '')
    channel_list = data.get("channel_list", '')
    length_c = len(channel_list)
    if username and channel_list and length_c >= 2:
        # first get info from mongo, then update the mongo use the data
        try:
            # get data from mongo, according the _id
            channel_data = q_db.rewrite_new.find_one({"_id": ObjectId(id)})
            if channel_data:
                channel_list_old = channel_data.get("channel_list", '')
            # delete id field
            del data['id']
            db.rewrite_new.update({"_id": ObjectId(id)}, data)
        except Exception:
            logger.debug("update_rewrite_id update mongo error, username:%s, exception:%s" % (username, e))
            return json.dumps({'msg': 'error', 'result': 'update_rewrite_id  exception:%s' % e})
        # operation redis
        # first delete original info
        # second add new info
        # implement the first step
        try:
            # the length of old channel_list
            length_c_old = len(channel_list_old)
            for i in range(length_c_old):
                channel = channel_list_old[i]
                channel_list_old.pop(i)
                channels_redis = REWRITE_CACHE.get(channel)
                if channels_redis:
                    channel_list_redis = channels_redis.split(',')
                    for chann in channel_list_old:
                        if chann in channel_list_redis:
                            # delete old channel
                            channel_list_redis.remove(chann)
                    if channel_list_redis:
                        # if channel_list_redis is not None
                        REWRITE_CACHE.set(channel, (',').join(channel_list_redis))
                    else:
                        # if channel_list_redis is None, delete the key in redis
                        REWRITE_CACHE.delete(channel)
                channel_list_old.insert(i, channel)
        except Exception:
            logger.debug("update_rewrite_id delete redis content, username:%s, exception:%s" % (username, e))
            return json.dumps({'msg': 'error', 'result': 'update_rewrite_id  exception:%s' % e})
        # implement the second step
        try:
            for i in range(length_c):
                channel = channel_list[i]
                channel_list.pop(i)
                channels_redis = REWRITE_CACHE.get(channel)
                if channels_redis:
                    REWRITE_CACHE.set(channel, channels_redis + ',' + (',').join(channel_list))
                else:
                    REWRITE_CACHE.set(channel, (',').join(channel_list))
                channel_list.insert(i, channel)
        except Exception:
            logger.debug("update_rewrite_id add redis content, username:%s, exception:%s" % (username, e))
            return json.dumps({'msg': 'error', 'result': 'update_rewrite_id  exception:%s' % e})
        return json.dumps({'msg': 'ok', 'result': 'rewrite success!'})
    return json.dumps({'msg':'error', 'result': 'received data has problem'})


def delete_rewrite_id(data):
    """
    accoding the id of data, to delete info in mongo, udpate the redis info
    step:
    first: get data from mongo
    second: delete data in mongo
    third: update data in redis
    :param data:
    :return:
    """
    id = data.get('id', '')

    try:
        result = q_db.rewrite_new.find_one({"_id": ObjectId(id)})
        logger.debug('result:%s' % result)
    except Exception:
        logger.debug("delete_rewrite_id error, id:%s, exception:%s" % (id, e))
        return json.dumsp({"msg": 'error', 'result': 'get data from mongo error, exception:%s' % e})
    try:
        # delete data from mongo, according the id
        db.rewrite_new.remove({"_id": ObjectId(id)})
        operation_record_into_mongo(data.get('user_email'), 'channel_redirection', 'delete', result)
    except Exception:
        logger.debug("delete_rewrite_id error, delete data error, id:%s, exception:%s" % (id, e))
        return json.dumsp({"msg": 'error', 'result': 'del data from mongo error, exception:%s' % e})
    try:
        # the data of channel_list from mongo
        channel_list = result.get("channel_list", '')
        logger.debug("channel_list:%s" % channel_list)


        length_c = len(channel_list)
        # handle the lengh of channel_list bigger than 2 or eq 2
        if channel_list and length_c >= 2:
            for i in range(length_c):
                channel = channel_list[i]
                channel_list.pop(i)
                channels_redis = REWRITE_CACHE.get(channel)
                logger.debug("channel:%s, channels_redis:%s" % (channel, channels_redis))
                if channels_redis:
                    channels = channels_redis.split(',')
                    for chann in channel_list:
                        # delete the appropriate channel which is in mongo
                        channels.remove(chann)
                    if len(channels) >= 1:
                        REWRITE_CACHE.set(channel, (',').join(channels))
                    else:
                        # the length of value is 0, the delete the channel in redis
                        REWRITE_CACHE.delete(channel)
                # to restore the original appearance
                channel_list.insert(i, channel)
    except Exception:
        logger.debug("delete_rewrite_id error, delete redis error, id:%s, exception:%s" % (id, e))
        return json.dumps({"msg": 'error', 'result': 'del data from redis error, exception:%s' % e})
    return json.dumps({'msg': 'ok', 'result': 'delete_rewrite_id, success!'})



def update_prefix_data(data):
    """
    according data,data has no id, insert into rewrite_new and update redis
    :param data: the content of rewrite_new
    :return:
    """
    username = data.get("username", '')
    channel_original = data.get("channel_original", '')
    channels_after = data.get('channels_after', '')

    length_c = len(channels_after)
    if username and channel_original and length_c >= 1:
        # first insert data into mongodb, then update redis
        try:
            db.rewrite_prefix.insert(data)
            # operation_record_into_mongo(data.get('user_email'), 'channel_redirection', 'insert', data)
        except Exception:
            logger.debug("update_prefix_data, insert mongo error,username:%s, Exception:%s" % (username, e))
            return json.dumps({'msg': 'error', 'result': 'update_rewrite_no_id  exception:%s' % e})
        try:

            # for i in range(length_c):
            #     channel = channel_list[i]
            #     channel_redis = REWRITE_CACHE.get(channel)
            #     channel_list.pop(i)
            #     if channel_redis:
            #         # rewrite the redis info
            #         rewrite_name = channel_redis + "," + (',').join(channel_list)
            #         REWRITE_CACHE.set(channel, rewrite_name)
            #         logger.debug("update redis success have channel:%s" % channel)
            #     else:
            #         # direct update redis
            #         REWRITE_CACHE.set(channel, (',').join(channel_list))
            #         logger.debug("update redis success do not have channel:%s" % channel)
            #     channel_list.insert(i, channel)
            # REWRITE_CACHE.hincrby('url_prefix_list_users', username, 1)
            REWRITE_CACHE.sadd('prefix_username_' + username, channel_original)
            for i in range(length_c):
                REWRITE_CACHE.sadd('prefix_' + channel_original, channels_after[i])
            # store username number
            # REWRITE_CACHE.hincrby('url_prefix_list_users', username, 1)
        except Exception:
            logger.debug("update_prefix_data, update redis error, username:%s, Exception:%s" % (username, e))
            return json.dumps({'msg': 'error', 'result': 'update_prefix_data  exception:%s' % e})
        return json.dumps({'msg': 'ok', 'result': 'prifix rewrite success!'})
    return json.dumps({'msg':'error', 'result': 'received data has problem'})


def rewrite_prefix_query(username, channel_original):
    """
    according username,channel_name, to find the relationship with the channel_name,
    :param username: the name of user
    :param channel_name: the name of url
    :return: the list of collection rewrite_new like [{'_id':xxx, 'username':xxxx, 'channel_list':XXXx},\
          {'_id':xxx, 'username':xxxx, 'channel_list':XXXx}]
    """
    list_rewrite = []

    try:
        if username == '':
            list_rewrite_temp = q_db.rewrite_prefix.find()
        else:
            list_rewrite_temp = q_db.rewrite_prefix.find({"username": username})
    except Exception:
        logger.debug("can not get data from collection of rewrite_prefix, except:%s" % e)

    if channel_original == '':
        # solve json serializable problem
        for channel in list_rewrite_temp:
            list_rewrite.append(channel)
        return list_rewrite
    else:
        for channel in list_rewrite_temp:
            channel_mongo = channel.get("channel_original", '')
            if channel_mongo:
                if channel_original in channel_mongo:
                    # if channel_name eq url in rewrite_list, add channel to list_rewrite
                    logger.debug("channel:%s" % channel)
                    # list_rewrite.append(channel)
                    # return list_rewrite
                    list_rewrite.append(channel)

        logger.debug("list_rewriet  prefix:%s" % list_rewrite)
        return list_rewrite


def delete_rewrite_prefix_id(data):
    """
    accoding the id of data, to delete info in mongo, udpate the redis info
    step:
    first: get data from mongo
    second: delete data in mongo
    third: update data in redis
    :param data:
    :return:
    """
    id = data.get('id', '')

    try:
        result = q_db.rewrite_prefix.find_one({"_id": ObjectId(id)})
        logger.debug('result:%s' % result)
    except Exception:
        logger.debug("delete_rewrite_prefix_id error, id:%s, exception:%s" % (id, e))
        return json.dumsp({"msg": 'error', 'result': 'get data from mongo error, exception:%s' % e})
    try:
        # delete data from mongo, according the id
        db.rewrite_prefix.remove({"_id": ObjectId(id)})
        # operation_record_into_mongo(data.get('user_email'), 'channel_redirection', 'delete', result)
    except Exception:
        logger.debug("delete_rewrite_prefix_id error, delete data error, id:%s, exception:%s" % (id, e))
        return json.dumsp({"msg": 'error', 'result': 'del data from mongo error, exception:%s' % e})
    try:
        # the data of channel_list from mongo
        username = result.get('username', '')
        channel_original = result.get("channel_original", '')
        channels_after = result.get('channels_after', '')

        for i in range(len(channels_after)):
            REWRITE_CACHE.srem('prefix_' + channel_original, channels_after[i])
        REWRITE_CACHE.srem('prefix_username_' + username, channel_original)
        value_username = REWRITE_CACHE.hincrby('url_prefix_list_users', username, -1)
        # if value_username <= 0:
        #     REWRITE_CACHE.hdel('url_prefix_list_users', username)

    except Exception:
        logger.debug("delete_rewrite_prefix_id error, delete redis error, id:%s, exception:%s" % (id, e))
        return json.dumps({"msg": 'error', 'result': 'del data from redis error, exception:%s' % e})
    return json.dumps({'msg': 'ok', 'result': 'delete_rewrite_prefix_id, success!'})



















