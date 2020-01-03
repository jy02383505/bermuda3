#encoding=utf8
from datetime import *
from dateutil.relativedelta import relativedelta
import logging
import traceback

from core import database, redisfactory


db = database.db_session()
preload_cache = redisfactory.getDB(1)
today=datetime.combine(date.today(),time())

LOG_FILENAME = '/Application/bermuda3/logs/clean_db.log'
logging.basicConfig(filename=LOG_FILENAME, format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s', level=logging.DEBUG)
logger = logging.getLogger('clean_db')

def del_db_url():
    clean_day = today-timedelta(days=10)
    logger.debug("del_for_db_url is begining! The url_data and request_date in %s will be deleted! "%clean_day.date())
    for i in range(24):
        begin = clean_day + relativedelta(hours=i)
        end = begin + relativedelta(hours=1)

        url_count = db.url.find({"created_time": {"$gte": begin, "$lte": end}}).count()
        if url_count > 0:
            try:
                logger.debug("url begin:%s count:%s" % (begin, url_count))
                db.url.remove({"created_time": {"$gte": begin, "$lte": end}})
            except Exception:
                logger.debug("url error :%s" % traceback.format_exc())

        device_count = db.device.find({"created_time": {"$gte": begin, "$lte": end}}).count()
        if device_count > 0:
            try:
                logger.debug("device begin:%s count:%s" % (begin, device_count))
                db.device.remove({"created_time": {"$gte": begin, "$lte": end}})
            except Exception:
                logger.debug("device error :%s" % traceback.format_exc())

        request_count = db.request.find({"created_time": {"$gte": begin, "$lte": end}}).count()
        if request_count > 0:
            try:
                logger.debug("request begin:%s count:%s" % (begin, request_count))
                db.request.remove({"created_time": {"$gte": begin, "$lte": end}})
            except Exception:
                logger.debug("request error :%s" % traceback.format_exc())

        preload_url_count = db.preload_url.find({"created_time": {"$gte": begin, "$lte": end}}).count()
        if request_count > 0:
            try:
                logger.debug("preload_url begin:%s count:%s" % (begin, preload_url_count))
                db.preload_url.remove({"created_time": {"$gte": begin, "$lte": end}})
            except Exception:
                logger.debug("preload_url error :%s" % traceback.format_exc())

        preload_dev_count = db.preload_dev.find({"created_time": {"$gte": begin, "$lte": end}}).count()
        if preload_dev_count > 0:
            try:
                logger.debug("preload_dev begin:%s count:%s" % (begin, preload_dev_count))
                db.preload_dev.remove({"created_time": {"$gte": begin, "$lte": end}})
            except Exception:
                logger.debug("preload_url error :%s" % traceback.format_exc())

    logger.debug("del_for_db_url is end! ")

def del_refresh_errot_task():
    clean_day = today - timedelta(days=3)
    logger.debug("del_for_db_error_task is begining is begining! The error_task_data in %s will be deleted! "%clean_day.date())
    for i in range(24):
        begin = clean_day + relativedelta(hours=i)
        end = begin + relativedelta(hours=1)
        error_task_count = db.error_task.find({"created_time": {"$gte": begin, "$lte": end}}).count()
        if error_task_count > 0:
            try:
                logger.debug("preload_dev begin:%s count:%s" % (begin, error_task_count))
                db.error_task.remove({"created_time": {"$gte": begin, "$lte": end}})
            except Exception:
                logger.debug("error_task error :%s" % traceback.format_exc())

    logger.debug("del_for_db_error_task is end!")

def del_preload_errot_task():
    clean_day = today - timedelta(days=3)
    logger.debug("del_preload_errot_task is begining is begining! The error_task_data in %s will be deleted! "%clean_day.date())
    for i in range(24):
        begin = clean_day + relativedelta(hours=i)
        end = begin + relativedelta(hours=1)

        preload_error_task_count = db.preload_error_task.find({"last_retrytime": {"$gte": begin, "$lte": end}}).count()
        if preload_error_task_count > 0:
            try:
                logger.debug("preload_dev begin:%s count:%s" % (begin, preload_error_task_count))
                db.preload_error_task.remove({"last_retrytime": {"$gte": begin, "$lte": end}})
            except Exception:
                logger.debug("preload_error_task error :%s" % traceback.format_exc())

    logger.debug("del_preload_errot_task is end!")

def set_overtime_failed():
    try:
        logger.debug("set_overtime_failed is begining is begining!")
        clean_day = today - timedelta(days=2)
        for i in range(24):
            begin = clean_day + relativedelta(hours=i)
            end = begin + relativedelta(hours=1)
            urls = db.preload_url.find({"created_time":{"$gte":begin,"$lte":end},"status":"PROGRESS"})
            for url in urls:
                cache_body = preload_cache.get(str(url.get("_id")))
                cache_body["_id"] = url.get("_id")
                cache_body["status"] = "FAILED"
                # db.preload_result.insert(cache_body)
                #db.preload_url.update({"_id":url.get("_id")},{"status":"FAILED","finish_time":datetime.now()})
                preload_cache.delete(str(url.get("_id")))
        logger.debug("set_overtime_failed is begining is ending!")
    except Exception:
        logger.debug("set_overtime_failed error:%s " % e)

def main():
    logger.debug("clean_db begining...")
    del_db_url()
    del_refresh_errot_task()
    del_preload_errot_task()
    set_overtime_failed()
    logger.debug("clean_db end.")

if __name__ == "__main__":
    main()
    exit()
