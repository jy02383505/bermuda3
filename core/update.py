# -*- coding:utf-8 -*-
'''
Created on 2014-3-11

@author: likun
'''

import logging
import traceback



logger = logging.getLogger('db_update')
logger.setLevel(logging.DEBUG)

RETRY_COUNT = 3


def db_update(collection,find,modification):
    for retry_count in range(RETRY_COUNT):
        try:
            ret = collection.update(find, modification)
            if ret.get("updatedExisting") == True and ret.get("n") > 0:
                return
        except Exception:
            logger.debug("db_update error, message=%s" % (traceback.format_exc()))
