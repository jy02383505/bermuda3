# -*- coding:utf-8 -*-
"""
Created on 2011-5-26

@author: mo
"""
import logging

from core.preload_timer import Timers
from core.config import config
from util import init_db
from util import log_utils

# LOG_FILENAME = '/Application/bermuda3/logs/timer.log'
# # logging.basicConfig(filename=LOG_FILENAME, format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s', level=logging.INFO)
# formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s")
# fh = logging.FileHandler(LOG_FILENAME)
# fh.setFormatter(formatter)
#
# logger = logging.getLogger('timer')
# logger.addHandler(fh)

logger = log_utils.get_rtime_Logger()

exec('logger.setLevel(%s)' % config.get('log', 'router_level'))

def main():
    logger.debug("Preload Timer task begining...")
    timer = Timers()
    timer.timer_run()
    timer.calllback()
    logger.debug("Preload Timer task end.")

    logger.debug("init_db begining...")
    init_db.init_preload_user()
    # init_db.init_rcms_channel()
    # init_db.init_rcms_user_enabled()
    logger.debug("init_db end.")

if __name__ == "__main__":
    main()
