# -*- coding:utf-8 -*-
__author__ = 'root'
import urllib.request, urllib.error, urllib.parse,traceback,string
import simplejson as sjson


from util import log_utils

logger = log_utils.get_redis_Logger()


RETRY_TIMES=4
TIMEOUT_OUTERURL=60
class ApiOuter(object):
    def read_from_outer(self,url,times=1,need_retry=True, time_out=0):
        try:
            '''backspace is existed'''
            url = string.replace(url,' ','%20')
            if time_out == 0:
                out_objects = urllib.request.urlopen(url,timeout=TIMEOUT_OUTERURL).read()
            else:
                logger.warn('ApiOuter  read_from_outer time_out:%s, url:%s' % (time_out, url))
                out_objects = urllib.request.urlopen(url, timeout=time_out).read()


            if out_objects:
                return out_objects
            else:
                raise 'object is null from url %s' % url

        except UnicodeError as e:
            logger.error('ApiOuter UnicodeError error, url:%s, error:%s, times:%s' % (url, traceback.format_exc(), times))
            url=url.encode('utf-8')
            return self.retry(url, times)
        except urllib.error.HTTPError as e:
            logger.error('ApiOuter HTTPError error, url:%s, error:%s, times:%s' % (url, traceback.format_exc(), times))
            return self.retry(url,times)
        except Exception:
            logger.error('for url== [%s] for times %d read_from_outer  exception is : %s' % (url,times,traceback.format_exc()))
            if (need_retry) :
                return self.retry(url,times)
            else:
                return None
    def retry(self,url,times):
        times+=1
        if (times>RETRY_TIMES):
            return None
        else:
            return self.read_from_outer(url,times)

    def get_valid_jsonstr(self,jsonStr):
        try:
            return sjson.loads(jsonStr)
        except Exception:
            logger.error("Passed, The string: %s  is not a valid json string, pass it" % jsonStr)
            return False

    def utfize_username(self,user_name):
        user_name_utf8=user_name
        try:
            user_name_utf8=user_name.encode('utf-8')
        except UnicodeEncodeError as e:
            logger.debug('user name is not utf8,username== %s' % user_name)
            user_name_utf8=user_name
        # logger.warn('sync_allObjects.utfize_username---user_name==%s ' % user_name_utf8)
        return user_name_utf8
    def is_diff_sort_cmp(self,devices_rcms,devices_mongo):
        if devices_rcms!=devices_mongo:
            return True
        else:
            return False