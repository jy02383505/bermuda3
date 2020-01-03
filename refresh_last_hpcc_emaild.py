#! -*- coding=utf-8 -*-
"""
@version: ??
@author: rubin
@license:
@contact: longjun.zhao@chinacache.com
@site: 
@software: PyCharm
@file: refresh_last_hpcc_emaild.py
@time: 17-3-29 下午4:57
"""

import time
import traceback
import os
from core.autodesk_url_id import refresh_last_hpcc_report
from util.autodesk_failed_task_dev import get_r_id_from_request_refresh_last_hpcc
from core.database import db_session
from util.autodesk_failed_task_dev import get_email_to_list

import logging
LOG_FILENAME = '/Application/bermuda3/logs/refresh_last_hpcc_email.log'
# LOG_FILENAME = '/home/rubin/logs/check_url_autodesk.log'
# logging.basicConfig(filename=LOG_FILENAME, format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s', level=logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s")
fh = logging.FileHandler(LOG_FILENAME)
fh.setFormatter(formatter)

logger = logging.getLogger('refresh_last_hpcc_email')
logger.addHandler(fh)
logger.setLevel(logging.DEBUG)

db = db_session()


def main():
    """

    :return:
    """
    try:
        while True:
            time.sleep(0.02)
            timestamp = time.time()
            logger.debug("refresh_last_hpcc_email timestamp:%s" % timestamp)
            r_id, username, created_time = get_r_id_from_request_refresh_last_hpcc(timestamp)
            if r_id:
                logger.debug('refresh_last_hpcc_email  r_id:%s, username:%s, created_time:%s' %
                             (r_id, username, created_time))
                 # get email_to list
                email_to = get_email_to_list(username, address='email_address_end')
                logger.debug("autodesk_failed_task_dev email_to:%s" % email_to)
                if not email_to:
                    logger.debug("this custom is not configured to refresh send mail")
                else:
                    try:
                        refresh_last_hpcc_report.delay(r_id, username, created_time)
                    except Exception:
                        logger.debug("refresh_failed_eamild error:%s" % traceback.format_exc())
            else:
                logger.debug('sleep 5 seconds')
                time.sleep(5)
    except Exception:
        logger.debug('autodesk_failed_eamild main error:%s' % traceback.format_exc())
    os._exit(0)


if __name__ == "__main__":
    main()