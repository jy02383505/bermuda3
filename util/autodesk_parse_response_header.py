#! -*- coding=utf-8 -*-
"""
@version: ??
@author: rubin
@license:
@contact: longjun.zhao@chinacache.com
@site: 
@software: PyCharm
@file: autodesk_parse_response_header.py
@time: 16-10-26 下午5:15
"""
import logging
import traceback
LOG_FILENAME = '/Application/bermuda3/logs/autodesk_postal.log'
# LOG_FILENAME = '/home/rubin/logs/autodesk_parse_response_header.log'

# logging.basicConfig(filename=LOG_FILENAME,
#                     format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s',
#                     level=logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s")
fh = logging.FileHandler(LOG_FILENAME)
fh.setFormatter(formatter)

logger = logging.getLogger('parse_header')
logger.addHandler(fh)
logger.setLevel(logging.DEBUG)


class ParseHeader():
    def __init__(self, buf, refresh_time):
        self.buf = buf
        self.refresh_time = refresh_time

    def get_code(self):
        """
        parse self.buf, get http code
        :param str: HTTP/1.1 200 OK
                    Content-Type: image/gif
                    Connection: close
                    X-DATE: 2016-10-26 16:22:49
                    ....
        :return: 200
        """
        try:
            first_line = self.buf.split('\r\n')[0]
            logger.debug('print first line:%s' % first_line)
        except Exception:
            logger.debug('get http header first line error:%s' % traceback.format_exc())
            return 0
        # after get first line, get http code
        try:
            code = first_line.split(' ')[1]
            logger.debug('get http header code :%s' % code)
            return code
        except Exception:
            logger.debug('get http header code error:%s' % traceback.format_exc())
            return 0

    def get_dict(self):
        """

        :return:
        """
        logger.debug('autodesk_parse_reponse_header get_dict type:%s, self.buf:%s' % (type(self.buf), self.buf))
        http_head_dict = {}
        try:
            lines = self.buf.split('\r\n')
            logger.debug('get_dict lines:%s' % lines)
            if len(lines) > 1:
                for line in lines[1:]:
                    key_value = line.split(':', 1)
                    if len(key_value) > 1:
                        key = key_value[0].strip()
                        value = key_value[1].strip()
                        http_head_dict[key] = value
            return http_head_dict
        except Exception:
            logger.debug('autodesk_parse_response_header get_dict error:%s' % e)
            return {}

    def get_age(self):
        """
        get the age of header
        :return: the content of Age   (int)
        """
        header_dict = self.get_dict()
        if 'Age' in header_dict:
            logger.debug('header_dict.Age:%s' % header_dict['Age'])
            return int(header_dict['Age'])
        elif 'age' in header_dict:
            logger.debug('header_dict.Age:%s' % header_dict['age'])
            return int(header_dict['age'])
        else:
            logger.debug('header_dic.Age have not have Age field')
            return None

    def get_cc_cache(self):
        """
        get the CC_CACHE of header
        :return: the content of CC_CACHE
        """
        # here add whether or not hit field
        header_dict = self.get_dict()
        if 'CC_CACHE' in header_dict:
            logger.debug('header_dict.CC_CACHE:%s' % header_dict['CC_CACHE'])
            return header_dict['CC_CACHE']
        else:
            logger.debug('header_dic not have CC_CACHE! ')
            return None

    def get_all_values(self):
        """
        get all values
        :return:
        """
        header_dict = self.get_dict()
        if header_dict:
            return list(header_dict.values())


    def refresh_result(self):
        """
        the result of refresh
        :return: success or failed
        """
        dict_values = self.get_all_values()
        judge_t = self.judge_value('mis', dict_values)
        try:
            code = self.get_code()
            if code != '200':
                return 'failed'
            elif code == '200':
                if 'mis' in self.get_cc_cache().lower():
                    return 'success'
                elif judge_t:
                    return 'success'
                else:
                    if self.get_age() < self.refresh_time:
                        return 'success'
            return 'failed'
        except Exception:
            logger.debug('get refresh_result error:%s' % traceback.format_exc())
            return 'error'

    def judge_value(self, str1, dict_str):
        """
        judge str1 is in or not dic_str
        :param str1: str
        :param dict_str:  dict
        :return: true or false
        """
        try:
            for dic in dict_str:
                if str1 in dic.lower():
                    return True
            return False
        except Exception:
            logger.debug('judge error:%s' % traceback.format_exc())
            return False










# Using this new class is really easy!

request_text ="""HTTP/1.1 200 OK
Content-Type: image/gif
Connection: close
X-DATE: 2016-10-26 16:22:49
Date: Wed, 26 Oct 2016 08:22:49 GMT
Cache-Control: max-age=2592000
ETag: 85ed33e88e
Content-Length: 4475
Last-Modified: Fri, 14 Oct 2016 02:35:06 GMT
Expires: Fri, 25 Nov 2016 08:22:49 GMT
Age: 598
Server: ngx_openresty
CC_CACHE: TCP_HIT
Accept-Ranges: bytes

"""




if __name__ == "__main__":
    temp = ParseHeader(request_text)
    print(temp.get_code())
    print(temp.get_dict())
    print(temp.print_buf())