# -*- coding:utf-8 -*-
"""
Created on 2011-7-1

@author: cl
"""

import datetime
import logging

logger = logging.getLogger('report')
logger.setLevel(logging.DEBUG)

from .update import db_update

dt = datetime.datetime.now() - datetime.timedelta(seconds=600)


def report(xmlStr, host):
    return "ok"

def scanOverTimeTrace(db_session):
    dt = datetime.datetime.now() - datetime.timedelta(minutes=15)
    ydt = dt - datetime.timedelta(minutes= 15)
    for url in db_session.url.find({"created_time": {"$gte": ydt, "$lt": dt}, "status": "PROGRESS"}):
        logger.debug("timeout url  request_id:%s  .url_id:%s" % (url['r_id'], url['_id']))
        db_update(db_session.url,{"_id": url.get("_id")}, {"$set": {"status": "FINISHED", "finish_time":datetime.datetime.now(),"handle":"timeout"}})
        db_update(db_session.request,{"_id": url.get("r_id")}, {"$set": {"status": "FINISHED", "finish_time":datetime.datetime.now(),"handle":"timeout"}})

if __name__ == "__main__":
    #scanOverTimeTrace(db_session)
    pass
