# !/usr/bin/env python
# -*- coding: utf-8 -*-
# Created by 'junyu.guo' on '08/17/16'.

__doc__ = ''
__ver__ = '1.0'
__author__ = 'junyu.guo'

from cache.updater_mongo_redis import sync_portal_by_queue
from util import celery_monitor
import os

def main():
    try:
        celery_monitor.run()
    except Exception:
        print(e)
    finally:
        os._exit(0)

if __name__ == "__main__":

    main()
    exit()
