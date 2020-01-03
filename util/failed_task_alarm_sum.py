#encoding=utf8

import sys
import traceback
import logging
from datetime import datetime, timedelta

from core import queue

#from pymongo import ReplicaSetConnection, Connection
# from pymongo import MongoClient
from core import database
LOG_FILENAME = '/Application/bermuda3/logs/failed_tesk_alarm.log'
logging.basicConfig(filename=LOG_FILENAME,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger('failed_tesk_alarm')
logger.setLevel(logging.DEBUG)

# db = MongoClient("172.16.21.205", 27017)['bermuda']
db =database.query_db_session()
# db = ReplicaSetConnection('%s:27017,%s:27017,%s:27017' % ('172.16.12.136', '172.16.12.135', '172.16.12.134'), replicaSet ='bermuda_db')['bermuda']

def get_ref_errs(begin_date,end_date):
    ref_err_dic = {}
    find_dic = {"datetime": {"$gte": begin_date, "$lt": end_date}}
    # return db.ref_err.find(find_dic).limit(100)
    return db.ref_err.find().limit(100)
def get_key_customers_monitor():
    config_dic = {}
    key_customers_monitor = db['key_customers_monitor']
    for config in key_customers_monitor.find():
        key = '%s_%s'%(str(config.get('USERNAME','')),str(config.get('Channel_Code','')))
        config_dic[key] = config
    return config_dic

if __name__ == "__main__":
    now = datetime.now()
    start_str = 'start script on {datetime}'.format(datetime=now)
    logger.info(start_str)
    print(start_str)
    emails = []
    cur_time = datetime.combine(now.date(), now.time().replace(hour=0, minute=0, second=0, microsecond=0))
    pre_time = cur_time + timedelta(days=1)
    error_task ={}
    # config_dic = get_key_customers_monitor()
    for ref_err in get_ref_errs(cur_time, pre_time):
        key = '%s_%s'%(str(ref_err.get('username','')),str(ref_err.get('channel_code','')))
        error_task.setdefault(
                    key, []).append(ref_err)
    # print emails
    for key in list(error_task.keys()):
        print(key, len(error_task.get(key)))
    exit()
