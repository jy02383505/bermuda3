# -*- coding:utf-8 -*-
"""
Created on 2017-11-21

"""
import os
from core.refresh_result import Refresh_router
from util import log_utils
import time
import threading

# LOG_FILENAME = '/Application/bermuda3/logs/router.log'
# handler = logging.handlers.RotatingFileHandler(LOG_FILENAME, maxBytes=100000000, backupCount=5)
# handler.setFormatter(Formatter('%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s'))
# logger = logging.getLogger('router')
# exec('logger.setLevel(%s)' % config.get('log', 'router_level'))
# logger.addHandler(handler)

logger = log_utils.get_logger_refresh_result()

def run():
    logger.debug("refresh begining...")
    #while True:
    try:
        router = Refresh_router()
        router.run()
    except Exception:
        logger.debug(e.message)
    #time.sleep(5)
    logger.debug("refresh end.")
    #os._exit(0) # fix :there are threads, not exit properly
def main():
    #while True:
        Ts=[]
        for i in  range(10):
            th=threading.Thread(target=run)
            Ts.append(th)
        for thr in Ts:
            thr.start()
        for th in Ts:
            threading.Thread.join(th)
# def main():
#     logger.debug("refresh begining...")
#     while True:
#         router = Refresh_router()
#         router.run()
#         time.sleep(5)
#     logger.debug("refresh end.")
#     os._exit(0) # fix :there are threads, not exit properly

if __name__ == "__main__":
    main()

