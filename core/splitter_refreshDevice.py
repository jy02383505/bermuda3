# -*- coding:utf-8 -*-
"""
Created on 2011-5-24

@author: archie
"""


import datetime as dtime
from datetime import datetime
import time
import logging
import re
import traceback
import copy
from util import log_utils
from util.tools import is_refresh_high_priority, get_channelname
import simplejson as json
# import bson
from core.generate_id import ObjectId
from celery.task import task
from redis.exceptions import WatchError

import socket
from core import redisfactory, rcmsapi, database, queue
from util.tools import add_rid_url_info_into_redis
from core.config import config


# logger = logging.getLogger('receiver')
# logger.setLevel(logging.DEBUG)

# logger = log_utils.get_receiver_Logger()
logger = log_utils.get_celery_Logger()

queue_name = 'request_queue'
REWRITE_CACHE = redisfactory.getDB(15)
COUNTER_CACHE = redisfactory.getDB(4)
REGEXCONFIG = redisfactory.getDB(8)
RECEIVER_HOST = socket.gethostname()


def get_refreshurl(username, url):
    '''

    组装URL字典，并根据username设置 layer_type

    Parameters:

        username :  用户

        url :  URL信息


    Returns:

    '''
    uid = str(url.pop("_id"))
    url['firstLayer'] = url.pop('is_multilayer')
    url['layer_type'] = "two" if url.get('firstLayer') else "one"
    url['r_id'] = str(url.get("r_id"))
    url['recev_host'] = RECEIVER_HOST
    url['id'] = uid
    del url['created_time']
    if username == 'sina_t' or username == 'sina_weibo' or username == 'autohome' or username == 'meipai':
        url['layer_type'] = "three"
    return url

db = database.db_session()

@task(ignore_result=True, default_retry_delay=10, max_retries=3)
def submit(refresh_task):
    '''
        提交任务到消息队列

    Parameters
    ----------
    refresh_task : 任务

    ignore_result       设置任务存储状态，如果为True,不存状态，也查询不了返回值
    default_retry_delay 设置重试提交到消息队列间隔时间，默认10 分钟，单位为秒
    max_retries         设置重试次数，默认为3

    Returns
    -------
    -------
    修饰符 @task 将submit函数变成了异步任务。在webapp中调用submit并不会立即执行该函数，
    而是将函数名、 参数等打包成消息发送到消息队列中，再由worker执行实际的代码
    '''
    try:
        urls = getUrlsInLimit(getUrls(refresh_task))
        logger.debug('submit: %s' % urls)
        if not urls:
            return
        setOveload(refresh_task, urls)
        # https add port 443
        # for url in urls:
        #     logger.debug("before url not have 443:%s" % url)
        #     url['url'] = add_https_443(url.get('url', ''))
        #     logger.debug('end url have 443:%s' % url)
        # logger.debug('submit: %s' % urls)
        db.url.insert(urls)
        username = refresh_task.get('username')
        try:
            user_list = eval(config.get('refresh_redis_store_usernames', 'usernames'))
        except Exception:
            logger.debug('splitter_new submit error:%s' % traceback.format_exc())
            user_list = []
        try:
            if username in user_list:
                add_rid_url_info_into_redis(refresh_task.get('r_id'), urls)
        except Exception:
            logger.debug('insert result into redis error:%s' % traceback.formate_exc(e))
        # logger.debug("rubin_test can delete  splitter_refreshDevice submit urls:%s" % urls)
        # re put the equipment into the URL
        for url_t in urls:
            url_t['devices'] = refresh_task.get('devices')
            # the interface does not have channel_code, instead of using the channel name
            url_t['channel_code'] = get_channelname(url_t.get('url'))
        #筛选优先级任务
        messages = []
        messages_high = []
        for url in urls:
            if url.get("status") == 'PROGRESS':
                url_info = get_refreshurl(refresh_task.get('username'), url)
                if url.get('high_priority', False):
                    messages_high.append(url_info)
                else:
                    messages.append(url_info)
        #messages = [get_refreshurl(refresh_task.get('username'), url) for url in urls if url.get("status") == 'PROGRESS']
        db.request.insert({"_id": refresh_task.get('r_id'), "username": refresh_task.get("username"), "parent": refresh_task.get("username"),
                   "callback": refresh_task.get("callback"), "status": "PROGRESS", "unprocess": len(messages),
                   "created_time": datetime.strptime(refresh_task.get('request_time'), '%Y-%m-%d %X') if refresh_task.get('request_time') else datetime.now(),
                    "remote_addr": refresh_task.get('remote_addr', ''), "serial_num": refresh_task.get('serial_num', '')})
        queue.put_json2('url_queue', messages)
        if messages_high:
            queue.put_json2('url_high_priority_queue', messages_high)
        if refresh_task.get('callback'):
            noticeEmail(refresh_task)
    except Exception:
        logger.warning('submit error! do retry. error:%s' % traceback.format_exc())
        raise submit.retry(exc=e)


def process(db, refresh_task, check_overload=False):
    '''
    处理任务

    Parameters
    ----------
    db : 数据库
    refresh_task : 刷新的任务
    check_overload : 是否检查超量

    Returns
    -------
    '''
    try:
        request_id = ObjectId()
        message = {"r_id": str(request_id)}
        refresh_task['r_id'] = request_id
        logger.debug("process refresh_task:%s %s %s " % (refresh_task['r_id'], refresh_task['username'], refresh_task['urls'] if 'urls' in list(refresh_task.keys()) else refresh_task['dirs']))
        if check_overload:
            url_overload = getOverload(refresh_task.get("username"), 'URL')  # 直接返回剩余数量
            dir_overload = getOverload(refresh_task.get("username"), 'DIR')
            url_length = len(refresh_task.get("urls") if refresh_task.get("urls") else []) + len(refresh_task.get("update_urls") if refresh_task.get("update_urls") else [])
            dir_length = len(refresh_task.get("dirs") if refresh_task.get("dirs") else [])

            if (url_length > 0 and url_overload > 0):
                message['urlExceed'] = url_length
                refresh_task['urls'] = []
                refresh_task['update_urls'] = []
                setCounterCache(refresh_task, url_length, 'URL')
                logger.error('process error ! refresh_task :%s,url:%s' % (refresh_task['r_id'], url_overload))

            if (dir_length > 0 and dir_overload > 0):
                message['dirExceed'] = dir_length
                refresh_task['dirs'] = []
                setCounterCache(refresh_task, dir_length, 'DIR')
                logger.error('process error ! refresh_task :%s,dir:%s ' % (refresh_task['r_id'], dir_overload))

            if len(refresh_task.get("urls") if refresh_task.get("urls") else []) > 0 or len(refresh_task.get("dirs") if refresh_task.get("dirs") else []) > 0 or len(refresh_task.get("update_urls") if refresh_task.get("update_urls") else []) > 0 :

                submit.delay(refresh_task)
                # submit(refresh_task)

        else:
            submit.delay(refresh_task)
    except Exception:
        logger.error(traceback.format_exc())
        logger.error('process error ! refresh_task :%s ' % refresh_task)
    return message

# return int ：< = 0 表示没超量。
def getOverload(username, refresh_type):
    '''
        检查在redis的记录是否超量

    Parameters
    ----------
    username : 用户
    refresh_type : 刷新类型（url,dir）

    Returns
    -------
    return int ：< = 0 表示没超量。

    COUNTER_CACHE redis存储的临时数据，在 4 库
    '''
    key = getUserKey(username, refresh_type)
    overload = COUNTER_CACHE.get(key)
    if overload:
        return 0 if int(overload) < 0 else int(overload)
    else:
        return  0

def getUserKey(username, refresh_type):
    '''
        生成在redis中的KEY

    Parameters
    ----------
    username : 用户
    refresh_type : 类型

    Returns
    -------
   '201405120815_URL_routon'
    '''
    hour = time.strftime("%Y%m%d%H", time.localtime(time.time()))
    return'%s_%s_%s' % (hour, refresh_type, username)

def setOveload(refresh_task, urls):
    setCounterCache(refresh_task, len([u for u in urls if not u['isdir']]), 'URL')
    setCounterCache(refresh_task, len([u for u in urls if u['isdir']]), 'DIR')

def setCounterCache(refresh_task, count, refresh_type):
    '''
    设置用户的URL,DIR数量，存于REDIS

    Parameters
    ----------
    refresh_task : 刷新任务
    count : 数量
    refresh_type : 类型

    Returns
    -------
    '''
    key = getUserKey(refresh_task.get('username'), refresh_type)
    with COUNTER_CACHE.pipeline() as pipe:
        while True:
            try:
                # 对序列号的键进行 WATCH
                pipe.watch(key)
                # WATCH 执行后，pipeline 被设置成立即执行模式直到我们通知它
                # 重新开始缓冲命令。
                # 这就允许我们获取序列号的值
                value = pipe.get(key)
                # 现在我们可以用 MULTI 命令把 pipeline 设置成缓冲模式
                pipe.multi()  # 标记事务开始
                next_value = -int(refresh_task.get('URL_OVERLOAD_PER_HOUR')) + count if refresh_type == 'URL' else -int(refresh_task.get('DIR_OVERLOAD_PER_HOUR')) + count
                if value:
                    next_value = int(value) + count
                    pipe.set(key, next_value)
                else:
                    pipe.set(key, next_value)
                pipe.expire(key, 3600)
                # 最后，执行 pipeline (set 命令)
                pipe.execute()
                break
            except WatchError as e:
                continue

def getUrlsInLimit(urls):
    tmpUrlList = copy.deepcopy(urls)
    # do rewrite
    for u in urls:
        if u.get('status') == 'PROGRESS':
            init_rewrite_url(tmpUrlList, u)
            init_regex_url(tmpUrlList, u)
    return tmpUrlList

def init_rewrite_url(tmpUrlList, u):
    """
    URL重定向,追加到原有URL列表,频道与原相同
    :param tmpUrlList:
    :param u:
    [{'status': 'PROGRESS', 'isdir': False, 'ignore_case': False, 'is_multilayer': True,
     'username': u'sina_t', 'url': u'http://ww2.sinaimg.cn/bmiddle/61b69811gw1dld19fhhelj.jpg',
     'r_id': ObjectId('53bbac202b8a6891d9deb8f1'), 'action': 'purge', 'created_time': datetime.datetime(2014, 7, 8, 16, 30, 24, 722266),
      'channel_code': '15032'}, {'status': 'PROGRESS', 'isdir': False, 'ignore_case': False, 'is_multilayer': True, 'action': 'purge',
       'r_id': ObjectId('53bbac202b8a6891d9deb8f1'), 'url': u'http://wp2.sina.cn/bmiddle/61b69811gw1dld19fhhelj.jpg', 'username': u'sina_t',
       'created_time': datetime.datetime(2014, 7, 8, 16, 30, 24, 723630), 'channel_code': '15032'
    """
    s = u.get('url').split('/', 3)
    channelname = s[0] + '//' + s[2]
    if len(s) > 3:
        method = '/' + s[3]
    else:
        method = ''
    if REWRITE_CACHE.exists(channelname):
        for rewrite in REWRITE_CACHE.get(channelname).split(","):
            rewriteUrl = rewrite + method
            tmpUrlList.append({"r_id": u.get('r_id'), 'ignore_case': u.get('ignore_case'), "url": rewriteUrl, "status": u.get('status'), "isdir": u.get('isdir'), "username": u.get("username"),
                               "created_time": datetime.now(), "action": u.get('action'), "is_multilayer": u.get('is_multilayer'), "parent": u.get("parent"), 'type':'rewrite',
                               "channel_code": u.get('channel_code'),"channel_name":u.get('channel_name'),'high_priority':u.get('high_priority')})
    else:
        # for the url is not in the redirection to determine whether the https, if it is https to increase the 443 port,
        # to retain the original url
        if s[0] == 'https:':
            rewriteUrl = channelname + ':443' + method
            tmpUrlList.append({"r_id": u.get('r_id'), 'ignore_case': u.get('ignore_case'), "url": rewriteUrl, "status": u.get('status'), "isdir": u.get('isdir'), "username": u.get("username"),
                               "created_time": datetime.now(), "action": u.get('action'), "is_multilayer": u.get('is_multilayer'), "parent": u.get("parent"), 'type':'rewrite',
                               "channel_code": u.get('channel_code')})

def init_regex_url(tmpUrlList, u):
    try:
        regexRedis = REGEXCONFIG.get(u.get("username"))
        if regexRedis:
            regexDict = json.loads(regexRedis)
            for regexId in list(regexDict.keys()):
                regexConfig = regexDict.get(regexId)
                if regexConfig.get('ignore') not in u.get("url") :
                    for regexUrl in re.findall(regexConfig.get('regex'), u.get("url")):
                        tmpUrlList.append({"r_id": u.get('r_id'), 'ignore_case': u.get('ignore_case'), "url": regexUrl + regexConfig.get('append', ''), "status": u.get('status'), "isdir": regexConfig.get("isdir"), "username": u.get("username"),
                                       "created_time": datetime.now(), "action": u.get('action'), "is_multilayer": u.get('is_multilayer'), "parent": u.get("parent"), 'type':'regex',
                                       "channel_code": u.get('channel_code'),"channel_name":u.get('channel_name'),'high_priority':u.get('high_priority')})
    except Exception:
        logger.info('regex splite error:%s' % traceback.format_exc())

def get_url(url, username, request_id, action, type, isdir, is_multilayer):
    """
    从RCMS获取用户的频道信息，匹配出channel_code

    :param url:
    :param username:
    :param request_id:
    :param action:
    :param isdir:
    :return:
    """
    if isdir:
    #检查dir情况下，url是否合法，不合法则变为url
        if not url.endswith('/'):
            logger.info('get url url is not dir: url %s isdir %s' %(url, isdir))
            isdir = False

    # isValid, is_multilayer, channel_code, ignore_case = rcmsapi.isValidUrl(username, url)
    # ignore_case  is mean  is not ignore case
    isValid, channel_code, ignore_case = True, None,  False
    #检查任务优先级
    high_priority = False
    if isValid:
        high_priority = is_refresh_high_priority(channel_code)
    return {"r_id": request_id, "url": url, "ignore_case": ignore_case, "status": 'PROGRESS' if isValid else 'INVALID',
            "isdir": isdir, "username": username, "parent": username, "created_time": datetime.now(), "action": action,
            "is_multilayer": is_multilayer, "channel_code": channel_code, 'type': type, 'high_priority':high_priority,
            "channel_name":get_channelname(url)}



def getUrlsFromRcms(turls, username, request_id, action, type, isdir, is_multilayer):
    re = []
    try:
        re = [get_url(u, username, request_id, action, type, isdir, is_multilayer) for u in turls if u and u.strip()]
    except Exception:
        logger.info('getUrlsFromRcms splite error:%s' % traceback.format_exc())
        logger.info('getUrlsFromRcms splite error:%s' % turls)
    return re

def getUrls(refresh_task):
    is_multilayer = judge_is_multilayer(refresh_task.get('devices'))
    urls = []
    urls += getUrlsFromRcms(refresh_task.get("urls") if refresh_task.get("urls") else [], refresh_task.get("username"), refresh_task.get("r_id"), "purge", refresh_task.get("type", 'other'), False, is_multilayer)
    urls += getUrlsFromRcms(refresh_task.get("dirs") if refresh_task.get("dirs") else [], refresh_task.get("username"), refresh_task.get("r_id"), "expire", refresh_task.get("type", 'other'), True, is_multilayer)
    urls += getUrlsFromRcms(refresh_task.get("purge_dirs") if refresh_task.get("purge_dirs") else [], refresh_task.get("username"), refresh_task.get("r_id"), "purge", refresh_task.get("type", 'other'), True, is_multilayer)
    urls += getUrlsFromRcms(refresh_task.get("update_urls") if refresh_task.get("update_urls") else [], refresh_task.get("username"), refresh_task.get("r_id"), "expire", refresh_task.get("type", 'other'), False, is_multilayer)
    return urls


def judge_is_multilayer(devices):
    """
    according device info, judge is multilayer or not
    Args:
        devices: [
        {
            "firstLayer": true,
            "host": "*",
            "name": "*",
            "port": 21108,
            "serialNumber": "28088713TA",
            "status": "SUSPEND",
            “type”:”HPCC”
        },
        {
            "firstLayer": true,
            "host": "*",
            "name": "*",
            "port": 21108,
            "serialNumber": "010104b3W6",
            "status": "OPEN",
            “type”:”FC”
        }]


    Returns:

    """
    logger.debug('devices type:%s' % (type(devices)))
    if not devices:
        return False
    else:
        for dev in devices:
            if dev.get('firstLayer'):
                logger.debug('juge_is_multilayer host:%s, serialNumber:%s' % (dev.get('host'), dev.get('serialNumber')))
                return True
    return False

def noticeEmail(refresh_task):
    try:
        callback = refresh_task.get('callback')
        if callback.get('email'):
            if callback.get('acptNotice'):
                email = [{"username": refresh_task.get('username'), "to_addrs": callback.get('email'),
                          "title": 'refresh callback', "body": get_email(refresh_task)}]
                queue.put_json2('email', email)
                logger.debug('email :%s put email_queue!' % callback.get('email'))
    except Exception:
        logger.error('sendEmail error!')
        logger.error(e)

def get_email(refresh_task):
    dt = datetime.now()
    if 'dirs' in refresh_task:
        estimated_time = dt + dtime.timedelta(seconds=600)
    else:
        estimated_time = dt + dtime.timedelta(seconds=300)
    strFormat = '%Y-%m-%d %H:%M:%S'
    urls = getUrls(refresh_task)
    urlCount = len(urls)
    emailBody = '\nThis message is to confirm that your content purge request has been accepted successfully by our Purge System.The details of your request are as follows:\n\tCustID:%s\n\tSubmission time:%s\n\tEstimated Completion time:%s\n\tURL count: %s\n\n\tContent committed:\n' % (refresh_task.get("username"), dt.strftime(strFormat), estimated_time.strftime(strFormat), urlCount)
    for url in urls:
        emailBody += '\t%s\n' % url.get('url')
    return emailBody + '''\n\tNote that the above list will be truncated if the full list is particularly long.\n\tPlease contact us ( globalsupport@chinacache.com ) if you have any questions or require further assistance.\n\tThank you from ChinaCache Customer Support.'''
