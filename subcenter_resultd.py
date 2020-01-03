#! -*- coding=utf-8 -*-
"""
@author: rubin
@create time: 2016/8/1  16:33
link detection
"""
import logging
from util.subcenter_result import subcenter_main



LOG_FILENAME = '/Application/bermuda3/logs/subcenter_result.log'
# logging.basicConfig(filename=LOG_FILENAME, format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s', level=logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s")
fh = logging.FileHandler(LOG_FILENAME)
fh.setFormatter(formatter)

logger = logging.getLogger('subcenter_result')
logger.addHandler(fh)


def main():
    logger.debug("subcenter_result update start ...")
    subcenter_main()
    logger.debug('subcenter_result update end!')


if __name__ == '__main__':
    main()