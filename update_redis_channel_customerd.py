#! -*- coding=utf-8 -*-
"""
@version: ??
@author: rubin
@license:
@contact: longjun.zhao@chinacache.com
@site: 
@software: PyCharm
@file: update_redis_channel_customerd.py
@time: 16-8-30 下午5:08
"""
import logging
from util.update_redis_channel_customer import main_fun

LOG_FILENAME = '/Application/bermuda3/logs/update_redis_channel_customer.log'
logging.basicConfig(filename=LOG_FILENAME,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger('update_redis_channel_customer')
logger.setLevel(logging.DEBUG)


def main():
    logger.debug("update_redis_channel_customer begining...")
    main_fun()
    logger.debug("update_redis_channel_customer end...")


if __name__ == "__main__":
    main()
