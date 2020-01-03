#!/usr/bin/python
# -*- coding:utf-8 -*-


VERSION = "1.0"

import time
import random
import string
import hashlib
import urllib.request, urllib.parse, urllib.error
import urllib.request, urllib.error, urllib.parse
from  core import config
import  json
from core import queue
from core.config import config
import logging
import traceback
import requests
LOG_FILENAME = '/Application/bermuda3/logs/link_portal_cms.log'

logger = logging.getLogger('link_portal_cms')
fileHander = logging.FileHandler(LOG_FILENAME)
fileHander.setFormatter(logging.Formatter(fmt='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s'))
fileHander.setLevel(logging.DEBUG)
logger.addHandler(fileHander)
url_cms_check ='http://cms3-apir.chinacache.com/apir/9040/checkCrtInfo'#正式地址
#url_cms_check = 'http://223.202.75.137:32000/apir/9040/checkCrtInfo'#测试地址

url_portal_delete = 'http://openapi.chinacache.com/cloud-ca/config/certificate'#正式地址
#url_portal_delete = 'http://openapi-test.chinacache.com/cloud-ca/config/certificate'#测试地址

url_cms_delete = 'http://cms3-apiw.chinacache.com/apiw/9040/delCrtInfo' #正式地址
#url_cms_delete = 'http://223.202.75.137:32000/apiw/9040/delCrtInfo'
email_group = ["pengfei.hao@chinacache.com","yanming.liang@chinacache.com","peifeng.zhao@chinacache.com","zhaoran.meng@chinacache.com","noc@chinacache.com"]
RETRY_NUM = 3
def check_cert_cms(cert_id_list):
    url = url_cms_check
    # req = urllib.request.Request(url, headers=send_headers)
    values = {
        "ROOT": {
            "HEADER": {
                "AUTH_INFO": {
                    "LOGIN_NO": "refresh_preload@chinacache.com",  # 用户名
                    #"LOGIN_PWD": "cert_2018_Q1",  # 密码
                    "LOGIN_PWD": "cert_2018_Q3",  # 密码
                    "FUNC_CODE": "9071"  # 功能编号
                }
            },
            "BODY": {
                "BUSI_INFO": {
                    "extnIds": cert_id_list  # ["59557edd3b1d487cff984226","59557edd3b1d487cff984250"] # 证书唯一ID
                }
            }
        }
    }
    send_headers = {
        'Content-Type': 'application/json'
    }
    jdata = json.dumps(values)
    request = urllib.request.Request(url, jdata, headers=send_headers)
    # request.add_header('Content-Type', 'application/json')
    # request.get_method = lambda: 'DELETE'  # 设置HTTP的访问方式

    try:
        request = urllib.request.urlopen(request)
        check_result = json.loads(request.read())
        message = check_result['ROOT']['BODY']['OUT_DATA']['certChannel']
        logger.debug("check cms result %s"%(check_result))
        if message:
            return False, message
        else:
            return True, None
    except Exception:
        logger.debug("check cms erros %s" % (e.message))
        return False, 'connet server error'

def cert_portal_delete(certid_list,method ="DELETE"):
    access_key = '51e7713a8e9e7d31'
    access_secret = '85053e054c735430e12f12850397545f'
    status = False
    message = ''
    for i in range(RETRY_NUM):
        try:
            timestamp = str(int(time.time()))
            nonce = "".join(random.sample(string.ascii_letters + string.digits, 10))
            url = url_portal_delete
            str_list = [access_key, access_secret, timestamp, nonce]
            str_list_sorted = sorted(str_list)
            str_sorted = "".join(str_list_sorted)
            print(str_sorted)
            signature = hashlib.sha1(str_sorted).hexdigest()

            content_type = 'application/json'
            send_headers = {
                'X-CC-Auth-Key': access_key,
                'X-CC-Auth-Timestamp': timestamp,
                'X-CC-Auth-Nonce': nonce,
                'X-CC-Auth-Signature': signature
            }
            if content_type:
                send_headers["Content-Type"] = content_type
            #req = urllib.request.Request(url, headers=send_headers)
            values = {"cert_ids": certid_list}
            jdata = json.dumps(values)
            request = urllib.request.Request(url, jdata,headers=send_headers)
            #request.add_header('Content-Type', 'application/json')
            request.get_method = lambda: 'DELETE'  # 设置HTTP的访问方式
            request = urllib.request.urlopen(request)
            result = json.loads(request.read())
            print(result)
            logger.debug("portal delete result : %s,%s"%(result,certid_list))
            if result['status'] == 0:
                status =True
                message = result['msg']
                break
            else:
                message = result
        except Exception:
            logger.debug("cert portal delete erros %s" % (e.message))
            print(e)
    if status != True:
        email = [{"to_addrs": email_group, "title": 'PORTAL证书转移失败', "body":"失败的证书id列表为%s;具体信息：%s"%(certid_list,message)}]
        queue.put_json2('email', email)
        print('FAILED')
    return status
def do_callback_portal(url, _type, command ):
    is_success = False
    start_time = time.time()
    json_command = json.dumps(command)

    for x in range(2):

        try:
            access_key = '51e7713a8e9e7d31'
            access_secret = '85053e054c735430e12f12850397545f'

            timestamp = str(int(time.time()))
            nonce = "".join(random.sample(string.ascii_letters + string.digits, 10))
            str_list = [access_key, access_secret, timestamp, nonce]
            str_list_sorted = sorted(str_list)
            str_sorted = "".join(str_list_sorted)
            signature = hashlib.sha1(str_sorted).hexdigest()
            content_type = 'application/json'
            send_headers = {
                'X-CC-Auth-Key': access_key,
                'X-CC-Auth-Timestamp': timestamp,
                'X-CC-Auth-Nonce': nonce,
                'X-CC-Auth-Signature': signature
            }
            if content_type:
                send_headers["Content-Type"] = content_type


            rc = requests.post(url, data=json_command, timeout=(5, 5), headers=send_headers)
            rc.raise_for_status()
            response_body = rc.text
            res = json.loads(response_body)
            print(res)
            logger.debug('%s callback json command %s res is %s' % (_type, json_command, res))
            if _type == 'portal':
                if res['status'] in [0]:
                    is_success = True
                    break
                elif res['status'] in [2]:
                    break
            elif _type == 'rcms':
                if res['ROOT']['BODY']['RETURN_CODE'] == '0':
                    is_success = True
                    break
        except Exception:
            logger.error(
                "%s callback error command is %s, error is %s" % (_type, json_command, traceback.format_exc()))
            continue

    end_time = time.time()
    logger.debug('%s do callback end cost seconds %s' % (json_command, (end_time - start_time)))
    return is_success

def cert_portal_delete2(certid_list,method ="DELETE"):
    access_key = '51e7713a8e9e7d31'
    access_secret = '85053e054c735430e12f12850397545f'
    timestamp = str(int(time.time()))
    nonce = "".join(random.sample(string.ascii_letters+string.digits, 10))
    url = url_portal_delete
    str_list = [access_key, access_secret, timestamp, nonce]
    str_list_sorted = sorted(str_list)
    str_sorted = "".join(str_list_sorted)
    print(str_sorted)
    signature = hashlib.sha1(str_sorted).hexdigest()

    content_type = 'application/json'
    send_headers = {
       'X-CC-Auth-Key': access_key,
       'X-CC-Auth-Timestamp': timestamp,
       'X-CC-Auth-Nonce': nonce,
       'X-CC-Auth-Signature': signature
    }
    if content_type :
        send_headers["Content-Type"] = content_type

    status = False
    message = ''
    for i in range(RETRY_NUM):
        try:
            #req = urllib.request.Request(url, headers=send_headers)
            values = {"cert_ids": certid_list}
            jdata = json.dumps(values)
            request = urllib.request.Request(url, jdata,headers=send_headers)
            #request.add_header('Content-Type', 'application/json')
            request.get_method = lambda: 'DELETE'  # 设置HTTP的访问方式
            request = urllib.request.urlopen(request)
            result = json.loads(request.read())
            if result['status'] == 0:
                status =True
                message = result['msg']
                break
            else:
                message = result['msg']
        except Exception:
            print(e)
    if status != True:
        email = [{"to_addrs": email_group, "title": 'PORTAL证书删除错误', "body":"失败的证书id列表为%s;具体信息：%s"%(certid_list,message)}]
        queue.put_json2('email', email)
        print('FAILED')

def cert_cms_delete(extnIds):
    url = url_cms_delete
    #url = 'http://223.202.75.137:32000/apiw/9040/delCrtInfo'
    # req = urllib.request.Request(url, headers=send_headers)
    values = {
        "ROOT": {
            "HEADER": {
                "AUTH_INFO": {
                    "LOGIN_NO": "refresh_preload@chinacache.com",
                    "LOGIN_PWD": "cert_2018_Q1",
                    "FUNC_CODE": "9072"}
            },
            "BODY": {
                "BUSI_INFO": {
                    "extnIds": extnIds
                }
            }
        }
    }
    send_headers = {
        'Content-Type': 'application/json'
    }
    jdata = json.dumps(values)
    status = False
    for i in range(RETRY_NUM):
        try:
            request = urllib.request.Request(url, jdata, headers=send_headers)
            request = urllib.request.urlopen(request)
            result = json.loads(request.read())
            logger.debug("cms delete result : %s,%s" % (result,extnIds))
            if result['ROOT']['BODY']['RETURN_MSG'] == 'OK':
                status = True
                print('OK')
                break
                # check_result = json.loads(request.read())
                # print check_result
        except Exception:
            logger.debug("cert cms delete erros %s" % (e.message))
            print(e)
    if status != True:
        email = [{"to_addrs": email_group, "title": 'CMS证书转移失败', "body":"失败的证书id列表为%s"%(extnIds)}]
        queue.put_json2('email', email)
        print('FAILED')
    return status
if __name__ == "__main__":
    url = 'http://openapi-test.chinacache.com/cloud-ca/ca/status/callback'
    _type = 'portal'
    command = {'taskId':'1111111111111111111'}
    print(do_callback_portal(url,_type,command))