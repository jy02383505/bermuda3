#! -*- coding=utf-8 -*-
"""
@author: rubin
@create time: 2016/8/1  16:33
link detection
"""
import logging
from util.postal_r import link_entrance


LOG_FILENAME = '/Application/bermuda3/logs/postal_r.log'
# logging.basicConfig(filename=LOG_FILENAME, format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s', level=logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s")
fh = logging.FileHandler(LOG_FILENAME)
fh.setFormatter(formatter)

logger = logging.getLogger('postal_r')
logger.addHandler(fh)


def main():
    logger.debug("link detection start ...")
    link_entrance()
    logger.debug('link detection end!')


if __name__ == '__main__':
    main()