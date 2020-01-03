# -*- coding:utf-8 -*-
"""
Created on 2011-5-26

@author: wenwen
"""
from monitor.mq_monitor import Monitor
import logging
from core.database import query_db_session
from core.config import config

LOG_FILENAME = '/Application/bermuda3/logs/monitor.log'
logging.basicConfig(filename = LOG_FILENAME, format = '%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s', level = logging.INFO)

logger = logging.getLogger('monitor')
exec('logger.setLevel(%s)' % config.get('log', 'monitor_level'))


def main():
    agent = Monitor(query_db_session())
    agent.setName('mq_monitor')
    agent.setDaemon(True)
    agent.run()

if __name__ == "__main__":
    main()
