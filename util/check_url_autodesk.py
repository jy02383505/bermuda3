#! -*- coding=utf-8 -*-
"""
@version: ??
@author: rubin
@license:
@contact: longjun.zhao@chinacache.com
@site: 
@software: PyCharm
@file: check_url_autodesk.py
@time: 16-10-21 下午1:29
"""
# try:
#     from pymongo import ReplicaSetConnection as MongoClient
# except:
#     from pymongo import MongoClient

# from datetime import datetime, timedelta
# from bson import ObjectId
# import time
import logging

# import traceback
from core.database import query_db_session
import time



LOG_FILENAME = '/Application/bermuda3/logs/check_url_autodesk.log'
# LOG_FILENAME = '/home/rubin/logs/check_url_autodesk.log'
# logging.basicConfig(filename=LOG_FILENAME, format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s', level=logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s")
fh = logging.FileHandler(LOG_FILENAME)
fh.setFormatter(formatter)

logger = logging.getLogger('check_url_autodesk')
logger.addHandler(fh)
logger.setLevel(logging.DEBUG)




# conn = MongoClient('mongodb://bermuda:bermuda_refresh@223.202.52.82:27018/bermuda')
# db = conn.bermuda
db = query_db_session()

def get_data(username, timestamp):
   """
   according username, get data from url_autodesk
   :param username: the name of user
   :return: _id
   """
   # db.url_autodesk.insert_many([{'id': 1, 'name': 'xiaoming12'}, {'id': 11, 'name': 'xiaoming111'}])
   # url_autodesk autodesk_flag 0, representrative is not update,  autodesk_flag 1 represent have been update status
   # now, the username is not used
   try:
       # result = db.url_autodesk.find_one_and_update({'username': username, 'autodesk_flag': 0,
       #                          'executed_end_time_timestamp': {'$lte': timestamp + 10}}, {'$set': {'autodesk_flag': 1}})
       result = db.url_autodesk.find_one_and_update({'autodesk_flag': 0,
                                'executed_end_time_timestamp': {'$lte': timestamp + 15}}, {'$set': {'autodesk_flag': 1}})

       logger.debug('check_url_autodesk get data success')
       logger.debug('result:%s' % result)
   except Exception:
       logger.debug('check_url_autodesk get_data fidd_one_and_udpate error:%s' % e)
   if result:
       executed_end_time_timestamp = float(result.get('executed_end_time_timestamp'))
       created_time = result.get('created_time')
       logger.debug('check_url_autodesk get_data created_time:%s' % created_time)
       different_time = executed_end_time_timestamp - time.mktime(created_time.timetuple())
       return str(result.get('_id')), different_time
   return None, None



# def main():
#     """
#
#     :return:
#     """
#     try:
#         while True:
#             time.sleep(0.1)
#             timestamp = time.time()
#             url_id = get_data('autodesk2', timestamp)
#             if url_id:
#                 print ('update_url_autodesk  url_id:%s' % url_id)
#                 logger.debug('update_url_autodesk  url_id:%s' % url_id)
#                 try:
#                     update_url_autodesk.delay(url_id)
#                 except Exception, e:
#                     logger.debug("update_url_autodesk.delay:%s" % traceback.format_exc())
#             else:
#                 # at this place need a algorithm, to control time
#                 logger.debug('sleep 5 seconds')
#                 time.sleep(5)
#     except Exception, e:
#         logger.debug('check_url_autodesk main error:%s' % traceback.format_exc())









if __name__ == "__main__":
    # get_data('autodesk', 123.0)
    # main()
    pass