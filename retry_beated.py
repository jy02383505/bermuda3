# -*- coding:utf-8 -*-
"""
Created on 2012-10-16

@author: cooler
"""
from monitor.retry_beat import Beat
import logging
from core.database import db_session,query_db_session
from core.config import config

LOG_FILENAME = '/Application/bermuda3/logs/retry_beated.log'
logging.basicConfig(filename=LOG_FILENAME, format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s', level=logging.INFO)

logger = logging.getLogger('monitor')
exec('logger.setLevel(%s)' % config.get('log', 'retry_beated_level'))


def main():
    beat = Beat(db_session(),query_db_session())
    beat.setName('retry_beat')
    beat.setDaemon(True)
    beat.run()

if __name__ == "__main__":
    main()