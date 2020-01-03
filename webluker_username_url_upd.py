#! -*- coding=utf-8 -*-
"""
@version: ??
@author: rubin
@license:
@contact: longjun.zhao@chinacache.com
@site: 
@software: PyCharm
@file: webluker_username_url_upd.py
@time: 17-7-31 下午5:27
"""
import logging
from util.webluker_username_url_up import main_fun

# LOG_FILENAME = '/Application/bermuda3/logs/webluker_username_url_up.log'
# logging.basicConfig(filename=LOG_FILENAME,
#                     format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s',
#                     level=logging.INFO)
#
# logger = logging.getLogger('webluker')
# logger.setLevel(logging.DEBUG)

LOG_FILENAME = '/Application/bermuda3/logs/webluker_username_url_up.log'
# logging.basicConfig(filename=LOG_FILENAME, format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s', level=logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s")
fh = logging.FileHandler(LOG_FILENAME)
fh.setFormatter(formatter)

logger = logging.getLogger('webluker')
logger.addHandler(fh)
logger.setLevel(logging.DEBUG)


def main():
    logger.debug("webluker_username_url_up begining...")
    main_fun()
    logger.debug("webluker_username_url_up end...")


if __name__ == "__main__":
    main()
