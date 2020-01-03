#! -*- coding=utf-8 -*-
"""
@version: ??
@author: rubin
@license:
@contact: longjun.zhao@chinacache.com
@site: 
@software: PyCharm
@file: check_url_autodeskd.py
@time: 16-10-25 下午1:51
"""
import logging
import time
import traceback
import os
from util.check_url_autodesk import get_data
from core.autodesk_url_id import update_url_autodesk, udpate_url_dev_autodesk


LOG_FILENAME = '/Application/bermuda3/logs/check_url_autodesk.log'
# LOG_FILENAME = '/home/rubin/logs/check_url_autodesk.log'
# logging.basicConfig(filename=LOG_FILENAME, format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s', level=logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s")
fh = logging.FileHandler(LOG_FILENAME)
fh.setFormatter(formatter)

logger = logging.getLogger('check_url_autodeskd')
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
            url_id, different_time = get_data('autodesk2', timestamp)
            if url_id:
                print(('update_url_autodesk  url_id:%s' % url_id))
                logger.debug('update_url_autodesk  url_id:%s, different_time:%s' % (url_id, different_time))
                try:
                    update_url_autodesk.delay(url_id)
                    # the line is the function of the check refresh function, temporary note off
                    # udpate_url_dev_autodesk.delay(url_id, different_time)
                    # udpate_url_dev_autodesk(url_id, different_time)
                except Exception:
                    logger.debug("update_url_autodesk.delay:%s" % traceback.format_exc())
            else:
                logger.debug('sleep 5 seconds')
                time.sleep(5)
    except Exception:
        logger.debug('check_url_autodesk main error:%s' % traceback.format_exc())
    os._exit(0)

# def main():
#     logger.debug("check_url_autodeskd  begining...")
#     while True:
#         router = Router()
#         router.run()
#         time.sleep(5)
#     logger.debug("router end.")
#     os._exit(0) # fix :there are threads, not exit properly

if __name__ == "__main__":
    main()