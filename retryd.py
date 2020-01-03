"""
Created on 2011-5-26

@author: wenwen
"""
import sys
from multiprocessing import Process
from core.retry_server import readconf
import logging
from core.config import config

LOG_FILENAME = 'logs/retry.log'
logging.basicConfig(filename=LOG_FILENAME, format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s', level=logging.INFO)

logger = logging.getLogger('router')
exec('logger.setLevel(%s)' % config.get('log', 'retry_level'))

def main():
    fileName = sys.argv[1] if len(sys.argv) > 1 else 'work'
    readconf(fileName)
        
if __name__ == '__main__':
    main()
    exit()