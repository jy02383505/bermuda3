#! -*- coding=utf-8 -*-
"""
@version: ??
@author: rubin
@license:
@contact: longjun.zhao@chinacache.com
@site: 
@software: PyCharm
@file: autodesk_failed_emaild.py
@time: 16-11-30 上午9:45
"""
import logging
import time
import traceback
import os
from core.autodesk_url_id import failed_task_email, failed_task_email_other
from util.autodesk_failed_task_dev import get_r_id_from_request


LOG_FILENAME = '/Application/bermuda3/logs/check_url_autodesk.log'
# LOG_FILENAME = '/home/rubin/logs/check_url_autodesk.log'
# logging.basicConfig(filename=LOG_FILENAME, format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s', level=logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s")
fh = logging.FileHandler(LOG_FILENAME)
fh.setFormatter(formatter)

logger = logging.getLogger('autodesk_failed_emaild')
logger.addHandler(fh)
logger.setLevel(logging.DEBUG)


def main():
    """

    :return:
    """
    try:
        while True:
            time.sleep(0.1)
            timestamp = time.time()
            logger.debug("autodesk_failed_eamild timestamp:%s" % timestamp)
            r_id, username, created_time = get_r_id_from_request(timestamp)
            if r_id:
                logger.debug('autodesk_failed_emaild  r_id:%s, username:%s, created_time:%s' %
                             (r_id, username, created_time))
                try:
                    if username in ['autodesk2']:
                        failed_task_email.delay(r_id, username, created_time)
                    else:
                        failed_task_email_other.delay(r_id, username, created_time)
                except Exception:
                    logger.debug("autodesk_failed_eamild error:%s" % traceback.format_exc())
            else:
                logger.debug('sleep 5 seconds')
                time.sleep(5)
    except Exception:
        logger.debug('autodesk_failed_eamild main error:%s' % traceback.format_exc())
    os._exit(0)


if __name__ == "__main__":
    main()