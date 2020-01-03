"""
Created on 2011-5-26

@author: wenwen
"""
import sys
from multiprocessing import Process
from core import database
from core.report_server import scanOverTimeTrace
import logging
from core.config import config
from monitor import send_error_mail


LOG_FILENAME = '/Application/bermuda3/logs/report.log'
logging.basicConfig(filename=LOG_FILENAME, format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s', level=logging.INFO)

logger = logging.getLogger('report')
exec('logger.setLevel(%s)' % config.get('log', 'report_level'))

def main():
    scanOverTimeTrace(database.db_session())

if __name__ == '__main__':
    main()
