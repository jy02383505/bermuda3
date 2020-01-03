#! -*- coding=utf-8 -*-
"""
@version: ??
@author: rubin
@license:
@contact: longjun.zhao@chinacache.com
@site: 
@software: PyCharm
@file: change_url.py
@time: 17-1-17 下午3:57
生成的url 包含特殊字符, 目前只改空格
"""
import string
import urllib.request, urllib.error, urllib.parse
import logging
import traceback
import copy


LOG_FILENAME = '/Application/bermuda3/logs/change_url.log'
# LOG_FILENAME = '/home/rubin/logs/change_url.log'
logging.basicConfig(filename=LOG_FILENAME,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger('count_deivce')
logger.setLevel(logging.DEBUG)

def encode_balank(urls):
    """
    如果urls　list 里面每个 中的url 包含空格，编码一下
    Args:
        urls:
        {"r_id": u.get('r_id'), 'ignore_case': u.get('ignore_case'), "url": rewriteUrl, "status": u.get('status'), "isdir": u.get('isdir'),
        "username": u.get("username"),
                               "created_time": datetime.now(), "action": u.get('action'),
                               "is_multilayer": u.get('is_multilayer'), "parent": u.get("parent"),
                               'type':'rewrite',
                               "channel_code": u.get('channel_code'), 'executed_end_time': u.get('executed_end_time'),
                               'executed_end_time_timestamp': u.get('executed_end_time_timestamp')}

    Returns:

    """
    result = []
    try:
        if urls:
            for url_t in urls:
                url = url_t.get('url')
                result.append(url_t)
                try:
                    if string.count(url, ' ') > 0:
                        url_new = {}
                        url_new['r_id'] = url_t.get('r_id')
                        url_new['ignore_case'] = url_t.get('ignore_case')
                        url_new['status'] = url_t.get('status')
                        url_new['isdir'] = url_t.get('isdir')
                        url_new['username'] = url_t.get('username')
                        url_new['created_time'] = url_t.get('created_time')
                        url_new['action'] = url_t.get('action')
                        url_new['is_multilayer'] = url_t.get('is_multilayer')
                        url_new['parent'] = url_t.get('parent')
                        url_new['type'] = url_t.get('type')
                        url_new['channel_code'] = url_t.get('channel_code')
                        url_new['executed_end_time'] = url_t.get('executed_end_time')
                        url_new['executed_end_time_timestamp'] = url_t.get('executed_end_time_timestamp')
                        url_new['url'] = url.replace(' ', '%20')
                        logger.debug('url old:%s, url new:%s' % (url, url_new['url']))
                        result.append(url_new)
                except Exception:
                    logger.debug('copy error:%s, url:%s' % (traceback.format_exc(), url))
                    continue
    except Exception:
        logger.debug("encode_balank  error:%s" % traceback.formate_exc(e))
        return urls
    print(result)
    return result

def test_url():
    """

    Returns:

    """
    url = 'http://www.baidu.com/1  2 3'
    print(string.count(url, ' '))
    print(urllib.parse.quote(url))
    print(url.replace(' ', '%20'))

if __name__ == "__main__":
    urls = [{'url':'http://www.baidu.com/1 2', 'name': 'xiaoming'}, {'url': 'http://ww.baidu.com', 'name': 'xiao'}]
    encode_balank(urls)