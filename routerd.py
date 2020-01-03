# -*- coding:utf-8 -*-
"""
Created on 2011-5-26

@author: wenwen
"""
import sys
import os
from core.router import Router
from core.config import config
from logging import Formatter
import logging.handlers,logging
from util import log_utils
import time


# LOG_FILENAME = '/Application/bermuda3/logs/router.log'
# handler = logging.handlers.RotatingFileHandler(LOG_FILENAME, maxBytes=100000000, backupCount=5)
# handler.setFormatter(Formatter('%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s'))
# logger = logging.getLogger('router')
# exec('logger.setLevel(%s)' % config.get('log', 'router_level'))
# logger.addHandler(handler)

logger = log_utils.get_router_Logger()

def main():
    logger.debug("router begining...")
    while True:
        router = Router()
        router.run()
        time.sleep(5)
    logger.debug("router end.")
    os._exit(0) # fix :there are threads, not exit properly

if __name__ == "__main__":
    main()
    