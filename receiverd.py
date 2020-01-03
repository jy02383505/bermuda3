from multiprocessing import Process
from logging import Formatter
import logging
from util import log_utils
from flup.server.fcgi import WSGIServer

from  receiver import receiver
from core.config import config


# LOG_FILENAME = '/Application/bermuda3/logs/receiver.log'
# # handler = logging.handlers.RotatingFileHandler(LOG_FILENAME, maxBytes=100000000, backupCount=5)
# handler = logging.FileHandler(LOG_FILENAME)
# handler.setFormatter(Formatter('%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s'))
# # logging.basicConfig(filename=LOG_FILENAME, format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s', level=logging.INFO)
# logger = logging.getLogger('receiver')
# exec('logger.setLevel(%s)' % config.get('log', 'receiver_level'))
# logger.addHandler(handler)

logger = log_utils.get_receiver_Logger()

def server(num):
    WSGIServer(receiver.r_app, bindAddress=(config.get('server', 'host'), 8000 + num)).run()

def main():
    for i in range(8):
        Process(target=server, args=(i,)).start()

if __name__ == '__main__':
    main()
