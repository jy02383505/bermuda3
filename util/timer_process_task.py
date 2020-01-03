#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Created by vance on 7/31/14.
from core.splitter import get_refreshurl


__author__ = 'vance'
__doc__ = 'fix db switch'
__ver__ = '1.0'

import traceback, logging
from core import database, queue
from datetime import datetime, timedelta
import simplejson as json

logger = logging.getLogger('refresh_timer')
logger.setLevel(logging.DEBUG)


class RTimers(object):
    def __init__(self):
        self.dt = datetime.now()
        self.query_db = database.query_db_session()
        self.db = database.db_session()


    def process_url(self, username, url):
        logging.debug('%s %s' % (username, url))
        return get_refreshurl(username, url)

    def timer_run(self):
        """
        refresh定时任务运行,执行前30-前5之间的数据

        """
        try:
            logger.debug("refresh timer work begining...")
            # json.dumps([dict((key, item[key]) for key in item if key != '_id') for item in doc.find()]) .update({'id':str(task['_id'])})
            task_list = [self.process_url(task['username'], dict((key, task[key]) for key in task)) for task in
                         self.query_db.url.find({"status": "PROGRESS",
                                                 "created_time": {"$lte": self.dt - timedelta(seconds=300),
                                                                  "$gte": self.dt - timedelta(seconds=1800)}},
                                                {'status': 1, 'isdir': 1, 'ignore_case': 1, 'layer_type': 1, '_id': 1,
                                                 'username': 1, 'url': 1, 'r_id': 1, 'action': 1, 'firstLayer': 1,
                                                 'channel_code': 1, 'is_multilayer': 1, 'created_time': 1})]
            #print task_list,json.loads(json.dumps(task_list))
            queue.put_json2('url_queue', json.loads(json.dumps(task_list)))
            logging.debug("refresh timer.work process messages end, count: %d " % len(task_list))
        except Exception:
            print(e)
            logger.warning('timer work error:%s' % traceback.format_exc())


if __name__ == '__main__':
    logger.debug("timer begining...")
    timer = RTimers()
    timer.timer_run()
    logger.debug("timer end.")
    exit()