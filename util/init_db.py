# -*- coding:utf-8 -*-
__author__ = 'livefun'

import traceback, logging,urllib.request,urllib.parse,urllib.error
import simplejson as json
from core import database,redisfactory
from core.config import config
from util import log_utils
logger = log_utils.get_rtime_Logger()
# logger = logging.getLogger('init_db')
# logger.setLevel(logging.DEBUG)

db = database.db_session()
RCMS_ROOT = config.get('rcmsapi', 'RCMS_ROOT')

def init_preload_user():
    try:
        logger.debug("init_user begining...")
        CUSTOMERS_URL = "http://portal.chinacache.com/api/internal/account/getAllAccount.do"
        users = json.loads(urllib.request.urlopen(CUSTOMERS_URL).read())
        db.preload_user.remove()
        db.preload_user.insert([{"name":user.get('name'),"status":user.get('status'),"user_id":user.get('customerCode'),"accountType":user.get('accountType')} for user in users])
        logger.debug("init_user end.")
    except Exception:
        logger.warning('init_user work error:%s' % traceback.format_exc())

def init_rcms_channel():
    try:
        logger.debug("init_rcms_channel begining...")
        CUSTOMERS_URL = RCMS_ROOT + "/channels"
        channels = json.loads(urllib.request.urlopen(CUSTOMERS_URL).read())
        db.rcms_channel.remove()
        db.rcms_channel.insert(channels)
        logger.debug("init_rcms_channel end.")
    except Exception:
        logger.warning('init_rcms_channel work error:%s' % traceback.format_exc())

def init_rcms_user_enabled():
    try:
        logger.debug("rcms_user_enabled begining...")
        CUSTOMERS_URL = RCMS_ROOT + "/user/enabled"
        users = json.loads(urllib.request.urlopen(CUSTOMERS_URL).read())
        db.rcms_user_enabled.remove()
        db.rcms_user_enabled.insert(users)
        logger.debug("rcms_user_enabled end.")
    except Exception:
        logger.warning('rcms_user_enabled work error:%s' % traceback.format_exc())

def cp_rewrite_toDB():
    r = redisfactory.getDB(15)
    logger.debug("cp_rewrite_toDB begining...")
    rewrites = []
    for key in list(r.keys()):
        d = {"CHANNEL":key,"REWRITE":r.get(key)}
        rewrites.append(d)
    print(rewrites)
    database.db_session().rewrite.insert(rewrites)
    logger.debug("cp_rewrite_toDB end.")
