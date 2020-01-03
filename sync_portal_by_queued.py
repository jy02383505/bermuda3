# !/usr/bin/env python
# -*- coding: utf-8 -*-
# Created by 'junyu.guo' on '02/25/16'.

__doc__ = ''
__ver__ = '1.0'
__author__ = 'junyu.guo'

from cache.updater_mongo_redis import sync_portal_by_queue

def main():
    sync_portal_by_queue()

if __name__ == "__main__":
    main()
    exit()
