# -*- coding:utf-8 -*-
#author: tong.zhang@chinacache.com
from util import log_utils
from celery.task import task
from cache.api_mongo import ApiMongo
import traceback

api_mongo = ApiMongo()
logger = log_utils.get_redis_Logger()

@task(ignore_result=True, default_retry_delay=10, max_retries=3)
def get_new_info(channelIds,customerIds):
    try:
        if channelIds:
            for channelId in channelIds:
            # update the database and redis,first database then redis
                api_mongo.sync_firstLayer_devices(channelId)
                api_mongo.sync_devices(channelId)
        if customerIds:
            for customerId in customerIds:
                api_mongo.sync_channels(customerId) 
    except Exception:
        logger.error("wrong in rcms_worker.get_new_info(): %s" % (traceback.format_exc(),))

