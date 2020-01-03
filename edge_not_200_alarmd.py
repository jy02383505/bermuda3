#! -*- coding=utf-8 -*-
"""
@author: rubin
@create time: 2016/8/1 17:05
statistic the result of link detection, perform once an hour
"""
import logging
from util.edge_not_200_alarm import program_entry

LOG_FILENAME = '/Application/bermuda3/logs/edge_not_200_alarmd.log'
# logging.basicConfig(filename=LOG_FILENAME, format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s', level=logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s")
fh = logging.FileHandler(LOG_FILENAME)
fh.setFormatter(formatter)


def main():
    logging.debug("statistic the result ...")
    program_entry()
    logging.debug("statistic end ...")


if __name__ == "__main__":
    main()