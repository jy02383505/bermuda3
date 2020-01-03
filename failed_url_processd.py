#! -*- coding=utf-8 -*-
"""
@version: ??
@author: rubin
@license:
@contact: longjun.zhao@chinacache.com
@site: 
@software: PyCharm
@file: failed_url_processd.py
@time: 17-7-28 下午5:05
"""
import logging
from util.failed_url_process import main_fun

# LOG_FILENAME = '/Application/bermuda3/logs/failed_url_process.log'
# logging.basicConfig(filename=LOG_FILENAME,
#                     format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s',
#                     level=logging.INFO)
#
# logger = logging.getLogger('failed_url_process')
# logger.setLevel(logging.DEBUG)

LOG_FILENAME = '/Application/bermuda3/logs/failed_url_process.log'
# LOG_FILENAME = '/home/rubin/logs/update_redis_channel_customer.log'
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s")
fh = logging.FileHandler(LOG_FILENAME)
fh.setFormatter(formatter)

logger = logging.getLogger('failed_url_process')
logger.addHandler(fh)
logger.setLevel(logging.DEBUG)


def main():
    logger.debug("failed url process begining...")
    main_fun()
    logger.debug("failed url process end...")


if __name__ == "__main__":
    main()