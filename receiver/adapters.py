#-*- coding:utf-8 -*-
'''
Created on 2012-3-15

@author: wenwen
'''
import simplejson as json
import hashlib ,base64 ,httplib2 ,time,logging
from werkzeug.exceptions import Forbidden, BadRequest, Unauthorized, HTTPException
from simplejson.decoder import JSONDecodeError
from core import rcmsapi, authentication

logger = logging.getLogger('adapters')
logger.setLevel(logging.DEBUG)

CDN_KEY_TENCENT = "cccdnkey"
USERNAME_TENCENT = 'qq'
PASSWORD_KEY_TENCENT = 'aa@tencent@11.11'

CDN_KEY_NTEASE = "c$25er1kb"
PASSWORD_KEY_NTEASE = 'cc@ne.com'
CDN_KEY_ENCRYPT = "cccdnkey@snp"

SNDA_PASSWORD = 'ptyy@snda.com'

def get_tencent_task(ori_task, remote_addr):
    try:
        ori_task = json.loads(ori_task)
        refresh_task = {"username": USERNAME_TENCENT, "urls": ori_task.get('delete_urls', []), "update_urls":ori_task.get('update_urls', [])}
        if is_verify_request_timeout(ori_task.get('request_time')):
            return refresh_task, False, '{"ret": -102, "msg": "请求超时"}'
        if is_verify_tencent_failed(ori_task):
            raise Forbidden("verify failed.")
        authentication.verify(USERNAME_TENCENT, PASSWORD_KEY_TENCENT, remote_addr)
        return refresh_task, True, '{"ret": 0, "msg": ""}'
    except JSONDecodeError:
        raise BadRequest("%s 格式不正确。" % ori_task)
    except Forbidden:
        return refresh_task, False, '{"ret": -101, "msg": "未授权的上报IP:%s"}' % remote_addr

def is_verify_request_timeout(request_time):
    ISOTIMEFORMAT = '%Y-%m-%d %X'
    r_time = time.mktime(time.strptime(request_time, ISOTIMEFORMAT))
    return (time.time() - r_time) > 1800.0

def is_verify_tencent_failed(ori_task):
    md5 = hashlib.md5()
    params_key = "%s%s%s%s%s" % (ori_task.get('request_time'), str(ori_task.get('serial_num')), ''.join(ori_task.get('update_urls', '')) , ''.join(ori_task.get('delete_urls', '')) , CDN_KEY_TENCENT)
    md5.update(params_key.encode('utf-8'))
    base_key = base64.b64encode(md5.hexdigest())
    return base_key != ori_task.get('verify')


def get_ntease_task(ori_task, remote_addr):
    task = {"username": "163", "urls": [u.strip() for u in ori_task.get('url_list', '').split('\r\n')], "dirs":[u.strip() for u in ori_task.get('dir_list', '').split('\r\n')], "callback":{"ntease_itemid":ori_task.get('item_id')}}
    try:
        if not task.get('urls') and not task.get('dirs'):
            return task, False, '<item_id>%s</item_id><result>FAILURE</result><detail>ERROR:EmptyURLPara</detail>' % ori_task.get("item_id")
        if is_verify_ntease_failed(ori_task, remote_addr):
            return task, False, '<item_id>%s</item_id><result>FAILURE</result><detail>ERROR:UserCheckFailed</detail>' % ori_task.get("item_id")
    except HTTPException as e:
        return task, False, '<item_id>%s</item_id><result>FAILURE</result><detail>ERROR:%s</detail>' % (ori_task.get("item_id"), e.description)
    return task, True, '<item_id>%s</item_id><result>SUCCESS</result><detail>SUCCESS:Success</detail>' % ori_task.get("item_id")


def is_verify_ntease_failed(ori_task, remote_addr):
    authentication.verify(ori_task.get('username'), PASSWORD_KEY_NTEASE, remote_addr)
    md5 = hashlib.md5()
    params_key = "%s%s%s%s" % (time.strftime('%Y%m%d', time.localtime()), ori_task.get('username'), CDN_KEY_NTEASE , PASSWORD_KEY_NTEASE)
    md5.update(params_key.encode('utf-8'))
    logger.debug("base_key:%s verify:%s" % (md5.hexdigest(), ori_task.get('md5')))
    return md5.hexdigest() != ori_task.get('md5')


def get_error_url(username, urls):
    errorList = []
    BadFormat = ['\n' + urls.pop(i) for i, url in enumerate(urls) if len(url) > 255 or url.startswith('http://') == False]
    Failed404 = ['\n' + urls.pop(i) for i, url in enumerate(urls) if getHttpStatus(url) >= 404]
    NotValidUrl = ['\n' + urls.pop(i) for i, url in enumerate(urls) if rcmsapi.isValidUrl(username, url)[0] == False]

    if BadFormat:
        errorList.append('\nfollowing urls ignored because of bad format:\n')
        errorList.append('\n'.join(BadFormat))

    if NotValidUrl:
        errorList.append('\nfollowing urls ignored because of domain range:\n')
        errorList.append('\n'.join(NotValidUrl))

    if Failed404:
        errorList.append('\nfollowing urls ignored because of status code >= 404:\n')
        errorList.append('\n'.join(Failed404))

    return ''.join(errorList)

def is_verify_encrypt_receiver_failed(ori_task):
    md5 = hashlib.md5()
    params_key = "%s%s%s%s%s" % (time.strftime('%Y%m%d', time.gmtime()), ori_task.get('username'),CDN_KEY_ENCRYPT,''.join(ori_task.get('urls')),''.join(ori_task.get('dirs')))
    md5.update(params_key.encode('utf-8'))
    return md5.hexdigest() != ori_task.get('verify')

def is_verify_encrypt_search_failed(rid,verify):
    md5 = hashlib.md5()
    params_key = "%s%s%s" % (time.strftime('%Y%m%d', time.gmtime()), rid ,CDN_KEY_ENCRYPT)
    md5.update(params_key.encode('utf-8'))
    return md5.hexdigest() != verify

def getHttpStatus(url):
    http = httplib2.Http(timeout=3)
    response, s = http.request(url)
    return response.status

def verify_snda(username, password, time):
    KEY = username + 'qetsfh!3' + time
    md5 = hashlib.md5(KEY.encode('utf-8'))
    #print md5.hexdigest()
    if password != md5.hexdigest():
        return False
    return SNDA_PASSWORD

