#! -*- coding=utf-8 -*-
"""
@version: ??
@author: rubin
@license:
@contact: longjun.zhao@chinacache.com
@site: 
@software: PyCharm
@file: receiver_physical_del.py
@time: 17-8-7 下午4:53
"""
import simplejson as json
import traceback
from bson import ObjectId
import math
from util import log_utils
from core.database import query_db_session,db_session
from core import redisfactory



logger = log_utils.get_admin_Logger()

db = db_session()
q_db = query_db_session()


REWRITE_CACHE = redisfactory.getDB(15)


def physical_del_channel_qu(username, channel_original):
    """
    according username,channel_name, to find the relationship with the channel_name,
    :param username: the name of user
    :param channel_name: the name of url
    :return: the list of collection physical_del_channel like [{'_id':xxx, 'username':xxxx, 'channel_list':XXXx},\
          {'_id':xxx, 'username':xxxx, 'channel_list':XXXx}]
    """
    logger.debug("physical_del_channel_query  username:%s, physical_del_channel:%s" % (username, channel_original))
    list_physical_del_channel_temp = []
    result_list = []

    try:
        if username == '':
            list_physical_del_channel_temp = q_db.physical_del_channel.find()
        else:
            list_physical_del_channel_temp = q_db.physical_del_channel.find({"username": username})
    except Exception:
        logger.debug("can not get data from collection of rewrite_prefix, except:%s" % e)

    if channel_original == '':
        # solve json serializable problem
        for channel in list_physical_del_channel_temp:
            result_list.append(channel)
        return result_list
    else:
        for channel in list_physical_del_channel_temp:
            channel_mongo = channel.get("physical_del_channel", '')
            if channel_mongo:
                if channel_original in channel_mongo:
                    # if channel_name eq url in rewrite_list, add channel to list_rewrite
                    logger.debug("channel:%s" % channel)
                    # list_rewrite.append(channel)
                    # return list_rewrite
                    result_list.append(channel)

        logger.debug("list_physical_del_channel  physical :%s" % result_list)
        return result_list


def update_physical_del_channel_data(data):
    """
    according data,data has no id, insert into rewrite_new and update redis
    :param data: the content of rewrite_new
    :return:
    """

    length_c = len(data)
    if length_c >= 1:
        # first insert data into mongodb, then update redis
        try:
            db.physical_del_channel.insert(data)
            # operation_record_into_mongo(data.get('user_email'), 'channel_redirection', 'insert', data)
        except Exception:
            logger.debug("update_prefix_data, insert mongo error, data:%s, Exception:%s" % (data, traceback.format_exc()))
            return json.dumps({'msg': 'error', 'result': 'update_rewrite_no_id  exception:%s' % e})
        try:
            for data_t in data:
                username = data_t.get('username', 'default')
                physical_del_channel = data_t.get('physical_del_channel', '')
                if physical_del_channel:
                    REWRITE_CACHE.set('physical_del_channel_' + physical_del_channel, username)


        except Exception:
            logger.debug("update_prefix_data, update redis error, username:%s, Exception:%s" % (username,
                                                            traceback.format_exc()))
            return json.dumps({'msg': 'error', 'result': 'update_physical_del_channel update redis error exception:%s'
                                                         % traceback.format_exc()})
        return json.dumps({'msg': 'ok', 'result': 'update physical del channel success!'})
    return json.dumps({'msg':'error', 'result': 'received data has problem'})


def delete_physical_del_channel_id(data):
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
        result = q_db.physical_del_channel.find_one({"_id": ObjectId(id)})
        logger.debug('result:%s' % result)
    except Exception:
        logger.debug("delete_rewrite_prefix_id error, id:%s, exception:%s" % (id, e))
        return json.dumsp({"msg": 'error', 'result': 'get data from mongo error, exception:%s' % e})
    try:
        # delete data from mongo, according the id
        db.physical_del_channel.remove({"_id": ObjectId(id)})
        # operation_record_into_mongo(data.get('user_email'), 'channel_redirection', 'delete', result)
    except Exception:
        logger.debug("delete_rewrite_prefix_id error, delete data error, id:%s, exception:%s" % (id, e))
        return json.dumsp({"msg": 'error', 'result': 'del data from mongo error, exception:%s' % e})
    try:

        physical_del_channel = result.get("physical_del_channel", '')

        REWRITE_CACHE.delete('physical_del_channel_' + physical_del_channel)

    except Exception:
        logger.debug("delete_rewrite_prefix_id error, delete redis error, id:%s, exception:%s" % (id, e))
        return json.dumps({"msg": 'error', 'result': 'del data from redis error, exception:%s' % e})
    return json.dumps({'msg': 'ok', 'result': 'delete_rewrite_prefix_id, success!'})


def get_physical_del_channel_list(results, args):
    """
    handle the content of every page
    :param results:  the content of username and channel list
    :param args: the info of every page
    :return:  the content of current page
    """
    # each page shows the number of a domain relation
    per_page = 15
    args["total_page"] = int(math.ceil(len(results)/(per_page*1.0)))

    return results[per_page*args.get("curpage"):per_page*(args.get("curpage") + 1)]


if __name__ == "__main__":
    pass