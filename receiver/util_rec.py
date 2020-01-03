# -*- coding: UTF-8 -*-

from bson import ObjectId
from core.database import query_db_session, db_session, s1_db_session
import traceback
from util import log_utils
from core.config import config
from util.tools import get_mongo_str

from core import queue
import json
logger = log_utils.get_receiver_Logger()

db = db_session()
q_db = query_db_session()
monitor_db = s1_db_session()


def get_url_by_id(id, url=False):
    """

    :param id: the id of url
    :return:
    """
    if not url:
        result = {}
        try:

            result = q_db.url.find_one({'_id': ObjectId(id)})
        except Exception:
            logger.debug('find url error:%s, id:%s' % (e, id))
        if result:
            dev_id = str(result.get('dev_id'))
            return dev_id
    else:
        result = {}
        try:

            result = q_db.url.find_one({'_id': ObjectId(id)})
        except Exception:
            logger.debug('find url error:%s, id:%s' % (e, id))
        if result:
            dev_id = str(result.get('dev_id'))
            url_t = str(result.get('url'))
            return {"dev_id": dev_id, "url": url_t}
    return None


def get_urls_by_request(request_id):
    url_list = [{'u_id': x.get('_id'), 'url': x.get('url'), 'dev_id': x.get('dev_id')} for x in
                q_db.url.find({'r_id': ObjectId(request_id)})]
    return url_list

def get_request_by_request(request_id):
    request_m = q_db.request.find_one({'_id': ObjectId(request_id)})
    return request_m

def get_repsql_by_chanelName(chanelName):
    rep = q_db.repsql.find_one({'chanelName': chanelName})
    return rep

def get_refresh_result_by_sessinId(session_id):
    """
    根据session_id，返回要查询的信息
    Parameters
    ----------
    session_id   refresh_result collection  中的session_id

    Returns   返回refresh_result中的信息
    -------
    """
    # session_id = '5b3c835637d015a9cd07d69e'

    logger.debug('action    sessid_id type is {0}'.format(type(session_id)))
    str_num = ''
    try:
        num_str = config.get('refresh_result', 'num')
        str_num = get_mongo_str(str(session_id), num_str)
    except Exception:
        logger.debug('get refresh_result get number of refresh_result error:%s' % traceback.format_exc())
    logger.debug('-------------session_id:{0},str_num:{1}'.format(session_id, str_num))
    logger.debug('sessid_id type is {0}'.format(type(session_id)))
    res = monitor_db['refresh_result' + str_num].find({'session_id': str(session_id)})
    # for x in res:
    #    logger.debug('-------------session_id:{0}'.format(x))
    if not res:
        return []
    else:
        # return assembel_refresh_result(res)
        return res


def get_devs_by_id(dev_id):
    return q_db.device.find_one({'_id': ObjectId(dev_id)})
def send_result_error(err_message):
    #err_message = {'request_id': request_id, 'url': url.get('url'), 'success': ss_count, 'all': countAll,'channelName': url.get('channel_name')}
    rep = q_db.rep_channel.find_one({'channelName': err_message.get('channelName')})
    to_user =rep.get('userName',None)
    if to_user:
        to_user =rep.get('userName').split(',')
    else:
        to_user = ["pengfei.hao@chinacache.com"]
    email = [{"username": to_user, "to_addrs": to_user,"title": '刷新回调失败任务', "body": json.dumps(err_message)}]
    queue.put_json2('email',email)

if __name__ == "__main__":
    print(get_refresh_result_by_sessinId('5b3de57737d0155f543d7272'))
    print(get_request_by_request('5b3de57737d0155f543d7272'))


