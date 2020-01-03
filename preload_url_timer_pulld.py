#! -*- coding=utf-8 -*-
"""
@version: ??
@author: rubin
@license:
@contact: longjun.zhao@chinacache.com
@site: 
@software: PyCharm
@file: preload_url_timer_pulld.py
@time: 17-2-6 下午4:20
"""
import logging
from util.preload_url_timer_pull import main as main_run

LOG_FILENAME = '/Application/bermuda3/logs/preload_url_timer.log'
# logging.basicConfig(filename=LOG_FILENAME, format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s', level=logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s")
fh = logging.FileHandler(LOG_FILENAME)
fh.setFormatter(formatter)


def main():
    logging.debug("preload_url_timer_pull starting...")
    main_run()
    logging.debug("preload_url_timer_pull end ...")


if __name__ == "__main__":
    main()
