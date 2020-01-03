"""
Created on 2011-5-26

@author: wenwen
"""
import sys
from multiprocessing import Process
import logging
from core import queue,database
from monitor import send_error_mail

logging.basicConfig(format='%(asctime)s %(levelname)s - %(message)s', filename='/Application/bermuda3/logs/error_mail.log')
logger = logging.getLogger('error_email')
logger.setLevel(logging.DEBUG)

def main():
    logger.debug("error_email start!")
    concurrency = 10
    bodys = queue.get('error_task', 5000)
    logger.debug("bodys count:%s!" % len(bodys))

    step = len(bodys) / concurrency + 1
    steped_bodys = [bodys[i:i + step] for i in range(0, len(bodys), step)]

    for steped_body in steped_bodys:
        Process(target=send_error_mail.run, args=(database.query_db_session(),steped_body,)).start()
        
if __name__ == '__main__':
    main()
    exit()