# -*- coding:utf-8 -*-
"""
Created on 2011-5-26

@author: wenwen
"""
from monitor.mq_agent import Agent
import logging
from core.database import db_session
from core.config import config


LOG_FILENAME = '/Application/bermuda3/logs/mq_agent.log'
logging.basicConfig(filename = LOG_FILENAME, format = '%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s', level = logging.INFO)

logger = logging.getLogger('agent')
exec('logger.setLevel(%s)' % config.get('log', 'agent_level'))


def main():
    agent = Agent(db_session())
    agent.setName('mq_agent')
    agent.setDaemon(True)
    agent.run()

if __name__ == "__main__":
    main()
