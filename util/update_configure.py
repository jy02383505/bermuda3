#encoding=utf8

import sys
import traceback
import logging
import os
import core.redisfactory as redisfactory
#from pymongo import ReplicaSetConnection, Connection
from pymongo import MongoClient
from core.database import query_db_session

LOG_FILENAME = '/Application/bermuda3/logs/update_configure.log'
logging.basicConfig(filename=LOG_FILENAME,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger('update_configure')
logger.setLevel(logging.DEBUG)
PRELOAD_DEVS = redisfactory.getDB(5)
REWRITE_CHANNEL = redisfactory.getDB(15)
batch_size = 500

#db = Connection("172.16.31.222", 27017)['bermuda']#
# db = Connection('mongodb://bermuda:bermuda_refresh@%s:27017/bermuda' %('101.251.97.145'))['bermuda']
# db = Connection("101.251.97.201", 27017)['bermuda']
# db = ReplicaSetConnection('%s:27017,%s:27017,%s:27017' % ('172.16.12.136', '172.16.12.135', '172.16.12.134'), replicaSet ='bermuda_db')['bermuda']

# active_db = Connection("223.202.52.134", 27017)['bermuda']
# active_db = ReplicaSetConnection('%s:27017,%s:27017,%s:27017' % ('223.202.52.134', '223.202.52.135', '223.202.52.136'), replicaSet ='bermuda_db')['bermuda']
#SH
#s_uri = 'mongodb://bermuda:bermuda_refresh@%s:27017,%s:27017,%s:27017/bermuda?replicaSet=bermuda_db' % ('172.16.31.222','172.16.32.254','172.16.32.3')
#BJ
s_uri = 'mongodb://bermuda:bermuda_refresh@%s:27017,%s:27017,%s:27017/bermuda?replicaSet=bermuda_db' % ('172.16.12.136', '172.16.12.135', '172.16.12.134')
db = MongoClient(s_uri)['bermuda']

#uri = 'mongodb://bermuda:bermuda_refresh@%s:27017,%s:27017,%s:27017/bermuda?replicaSet=bermuda_db' % ('223.202.52.134', '223.202.52.135', '223.202.52.136')
#active_db = ReplicaSetConnection(uri)['bermuda']

# active_db = Connection("mongodb://bermuda:bermuda_refresh@%s:27018/bermuda"%'223.202.52.135')['bermuda']
active_db = MongoClient("mongodb://bermuda:bermuda_refresh@%s:27018/bermuda"%'223.202.52.135')['bermuda']

# rubin test
rubin_test_db = query_db_session()


def update_configure(db_name):
    try:
        logger.info('db_name: %s' %db_name)
        db_list = active_db[db_name].find()
        print(db_list)
        if db_list:
            db[db_name].remove()
            db[db_name].insert(db_list)
            if db_name == "preload_channel":
                update_redis5(db_list)
            if db_name == "rewrite_new":
                update_redis15(db_list)
    except Exception:
         logger.error(traceback.format_exc())


def update_redis15(channel_content):
    """
    update the redis library according to the channel information
    Args:
        channel_content: [{
                     "_id" : ObjectId("57b56f7b2b8a6894cee1f0f8"),
                     "username" : "noName",
                     "channel_list" : [
                     "http://fr.beijing2008.cn",
                      "http://fr.bhay.cn"
                       ]
                     }, {...}]

    Returns:

    """
    # channel_content = rubin_test_db.rewrite_new.find()
    map_key_value = {}
    if channel_content:
        for ch_content in channel_content:
            channel_list = ch_content.get('channel_list')
            logger.debug('update_redis15  channel_list:%s' % channel_list)
            if channel_list and len(channel_list) > 1:
                length_channel_list = len(channel_list)
                for i in range(length_channel_list):
                    key = channel_list[i]
                    channel_list.pop(i)
                    value = ','.join(channel_list)
                    if key in map_key_value:
                        value = map_key_value[key] + ',' + value

                    map_key_value[key] = value
                    channel_list.insert(i, key)
    # print map_key_value
    set_redis15(map_key_value)


def set_redis15(map_domain_name):
    """

    Args:
        map_domain_name: {"key": "value", "key1": "value1"}

    Returns:

    """
    if map_domain_name:
        pipe_t = REWRITE_CHANNEL.pipeline()
        count = 0
        try:
            for key in map_domain_name:
                count += 1
                value = map_domain_name[key]
                logger.debug("set_redis 15 key:%s, value:%s" % (key, value))
                pipe_t.set(key, value)
                if not count % batch_size:
                    pipe_t.execute()
                    count = 0
            # send the last batch
            pipe_t.execute()
        except Exception:
            logger.debug("set_redis15 error:%s" % traceback.format_exc())


def update_redis5(preload_channel_content):
    """
    according preload_channel content,  insert channel_name, config_count into redis
    :param preload_channel_content:
    :return:
    """
    try:
        if preload_channel_content:
            for channel in preload_channel_content:
                PRELOAD_DEVS.set(channel["channel_name"], channel['config_count'])
    except Exception:
        logger.error(traceback.format_exc())



db_names = ['rewrite','rewrite_new','channel_ignore','regex_config','overloads_config','admin_user','preload_channel',
            'preload_config_device', 'key_customers_monitor', 'email_management']

if __name__ == "__main__":
    logger.debug('update_configure is start')
    if len(sys.argv) == 2:
        update_configure(sys.argv[1])
    else:
        for db_name in db_names:
            update_configure(db_name)
    logger.info('update_configure is end')
    os._exit(0)

# if __name__ == "__main__":
#     res = [{"channel_list": ['1', '2', '3']}, {"channel_list": ['2', '3', '4', '5']}]
#     update_redis15("")
