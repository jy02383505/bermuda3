# !/usr/bin/env python
# -*- coding: utf-8 -*-
# Created by 'vance' on '11/25/14'.

__doc__ = ''
__ver__ = '1.0'
__author__ = 'vance'

from cache.updater_mongo_redis import  sync_all_rcms


def main():
    sync_all_rcms()


if __name__ == "__main__":
    main()
    exit()
