#!/usr/bin/env python
# coding=utf-8
import traceback
import requests

__author__ = 'vance'
__ver__ = '1.0'

import logging
import datetime
from core.database import query_db_session
from core import redisfactory
import simplejson as json
from bson import ObjectId
from core.sendEmail import send as send_mail
import urllib.request, urllib.error, urllib.parse
import uuid
import time
from xml.dom.minidom import parseString
from core.config import initConfig
import os
from multiprocessing.dummy import Pool as ThreadPool

# from core.verify import doPost
# try:
#     from pymongo import Connection as MongoClient
# except:
#     from pymongo import MongoClient

LOG_FILENAME = '/Application/bermuda3/logs/region_devs_retry.log'
# logging.basicConfig(filename=LOG_FILENAME,
#                     format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s',
#                     level=logging.INFO)

formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s")
fh = logging.FileHandler(LOG_FILENAME)
fh.setFormatter(formatter)

logger = logging.getLogger('region_devs_retry')
logger.addHandler(fh)
logger.setLevel(logging.DEBUG)

db = query_db_session()
# db = MongoClient("mongodb://bermuda:bermuda_refresh@172.16.21.205/bermuda", 27017)['bermuda']
# db = MongoClient("mongodb://bermuda:bermuda_refresh@172.16.21.205:27017/bermuda, 27017)['bermuda']
# db = MongoClient("mongodb://bermuda:bermuda_refresh@223.202.52.135/bermuda", 27017)['bermuda']
preload_cache = redisfactory.getDB(1)
PRELOAD_DEVS = redisfactory.getDB(5)
MONITOR_USER = ["cztv"]
config = initConfig()
REG_CHAN_MAP = {}


def get_result_by_id(url_id):
    try:
        result = preload_cache.get(url_id)
        if result:
            return json.loads(result)
        else:
            return db.preload_result.find_one({"_id": ObjectId(url_id)})
    except Exception:
        return {}


# """<?xml version="1.0" encoding="utf-8"?><preload_task sessionid="38be89acdb3a11e3a7c090e2ba343030">
# <action>refresh,preload</action><priority>0</priority><nest_track_level>0</nest_track_level><check_type>MD5</check_type><limit_rate>0</limit_rate><preload_address>127.0.0.1:80</preload_address><report_address need="yes">223.202.52.43:80</report_address><is_override>1</is_override><url_list><url id="53731c95922be573cf34d1e4">http://bakdl.sjk.ijinshan.com/apk/mumayi/338/com.mobi.common.main.fzlmv.14.2715306.apk</url><url id="53731c95922be573cf34d1e5">http://bakdl.sjk.ijinshan.com/apk/AppChina/285/kk.fruit_link.66.2156328.apk</url><url id="53731c95922be573cf34d1e6">http://bakdl.sjk.ijinshan.com/apk/AppChina/279/com.xs.cn.119.5529256.apk</url><url id="53731c95922be573cf34d1e7">http://bakdl.sjk.ijinshan.com/apk/mumayi/398/com.mobi.livewallpaper.hdsj4.37.3161195.apk</url><url id="53731c95922be573cf34d1e8">http://bakdl.sjk.ijinshan.com/apk/m91/94/com.douban.group.231.3097473.apk</url></url_list></preload_task>"""

def calRegionDevicePer(reg_count, fail_count):
    if round(float(fail_count) / float(reg_count), 2) > 0.2:
        return True
    else:
        return False


def del_preload_errot_task(id, host):
    logger.debug("start remove errot_task: {0}".format(id))
    db.preload_error_task.remove({"url_id": id, "host": host})
    logger.debug("end errot_task")


def preload_callback(channel, callback_body, info={}):
    """
    任务处理完成的汇报，处理预加载结果，调用提交的callback(email,url)
    :param channel:
    :param callback_body:
    :param info:
    """
    try:
        if channel.get('callback', {}).get('email'):
            send_mail(channel.get('callback').get('email'),
                      'preload callback', str(callback_body))
        if channel.get('callback', {}).get('url'):
            ca_url = channel.get('callback').get('url')
            # call_url = "http://223.202.52.83/receiveService"
            curls = []
            if ca_url:
                curls.append(ca_url)
            for call_url in curls:
                status = doPost(call_url, json.dumps(callback_body))
                logger.debug('request : %s ,urlcallback status:%s.' % (
                            channel.get('callback').get('url'), status))
                if status != 200:
                    for i in range(3):
                        status = doPost(channel.get('callback').get('url'), json.dumps(callback_body))
                        logger.debug('request : %s ,urlcallback retry count:%s ,status:%s.' % (
                            channel.get('callback').get('url'), i, status))
                        if status == 200:
                            break
        if info and channel.get('username', '') == 'snda':
            import hashlib
            import urllib.request, urllib.parse, urllib.error
            time_md5 = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            post_data = {'username': channel.get('username'), 'time': time_md5, 'password': hashlib.md5(
                channel.get('username') + 'qetsfh!3' + time_md5).hexdigest()}
            if callback_body.get('status') == 'FINISHED':
                post_data['context'] = json.dumps(
                    [{"task_id": callback_body.get('task_id'), "status": True}])
            else:
                post_data['context'] = json.dumps(
                    [{"task_id": callback_body.get('task_id'), "status": False,
                      "err_text": "Error dev count: %s" % (info.get('total_count') - info.get('count'))}])
            params = urllib.parse.urlencode(post_data)
            logger.debug(post_data)
            logger.debug(params)
            for i in range(3):
                response = urllib.request.urlopen("http://116.211.20.45/api/preload_report?cdn_id=1005", params)
                ret = json.loads(response.read())
                if ret.get('success') == True:
                    break
    except Exception:
        logger.debug("preload_callback error: %s url_id: %s " % (e, callback_body.get("url_id")))


def report_task(channel_code, region_channel_map, url):
    logger.debug("send region report, devs: {0}".format(str(url.get('_id'))))
    reg_list = region_channel_map[channel_code]
    preload_callback(db.preload_channel.find_one({"channel_code": channel_code}), {
        "task_id": url.get('task_id'), "status": "SUCCESS", "percent": "100", "region": reg_list})
    logger.debug("end region report, devs")


def send_task(fail_devs, fail_region_devs, url, v):
    logger.debug("start region post to fc,devs: {0}".format(fail_region_devs))
    results, wrongRet = doSend_HTTP_Req(fail_devs, get_command([url], url.get('action'), v.get("host")))
    logger.debug("end region post to fc,results: {0}".format(results))


def doSend_HTTP_Req(devs, command):
    """
     重试时直接用requests发送，会增加一个返回码的判断
    :param devs:
    :param command:
    :return:
    """
    results = []
    wrongRet = []
    for dev in devs:
        r_code = 200
        total_cost = 0
        try:
            start_time = time.time()
            rc = requests.post("http://%s:%d" % (dev['host'], 31108), data=command,
                               timeout=(2, 10))  # connect_timeout 2s reponse_timeout 5s
            rc.raise_for_status()

            response_body = rc.text
            total_cost = time.time() - start_time

            results.append(dev['host'] + '\r\n' + response_body + '\r\n%.2f' % (total_cost))

        except requests.ConnectionError as e:
            r_code = 503
            total_cost = time.time() - start_time
            wrongRet.append(dev['host'] + '\r\n%d\r\n%.2f' % (r_code, total_cost))
        except requests.Timeout:
            r_code = 501
            total_cost = time.time() - start_time
            wrongRet.append(dev['host'] + '\r\n%d\r\n%.2f' % (r_code, total_cost))
        except Exception:
            r_code = 502
            total_cost = time.time() - start_time
            wrongRet.append(dev['host'] + '\r\n%d\r\n%.2f' % (r_code, total_cost))
            logger.error("%s connect error." % dev.get('host'))
            logger.error("connect error :%s ." % (traceback.format_exc()))
        logger.debug('retry %s  r_code: %d r_cost: %.2f' % (dev['host'], r_code, total_cost))
    return results, wrongRet


def get_command(urls, action, dev_ip):
    """
    组装下发格式
    :param urls:
    :param action:
    :return:
    """
    try:
        sid = uuid.uuid1().hex
        command_str = '<preload_task sessionid="%s">' % sid
        command_str += '<action>%s</action>' % action
        command_str += '<priority>%s</priority>' % urls[0].get("priority")
        command_str += '<nest_track_level>%s</nest_track_level>' % urls[0].get("nest_track_level")
        command_str += '<check_type>%s</check_type>' % urls[0].get("check_type")
        command_str += '<limit_rate>%s</limit_rate>' % urls[0].get("get_url_speed")
        command_str += '<preload_address>%s</preload_address>' % urls[0].get("preload_address")
        command_str += '<lvs_address>%s</lvs_address>' % dev_ip
        command_str += '<report_address need="yes">%s</report_address>' % config.get("server", "preload_report")
        command_str += '<is_override>1</is_override>'
        command_str += '</preload_task>'
        content = parseString(command_str)
        url_list = parseString('<url_list></url_list>')
        for url in urls:
            uelement = content.createElement('url')
            uelement.setAttribute('id', str(sid))
            uelement.appendChild(content.createTextNode(url.get('url')))
            url_list.documentElement.appendChild(uelement)
        content.documentElement.appendChild(url_list.documentElement)
        logger.debug(content.toxml('utf-8'))
        return content.toxml('utf-8')
    except Exception:
        print(e)


def doPost(url, urlResult):
    headers = {'content-type': 'application/json'}
    try:
        request = urllib.request.Request(url, urlResult, headers=headers)
        response = urllib.request.urlopen(request)
        return response.getcode()
    except Exception:
        return 0


def getCallbackData(url):
    count = db.callback.find({"task_id": url["task_id"],"reponse":{"$ne":"ok"},"create_time":{"$gte":url["created_time"]}}).count()
    if count > 0:
        return False
    else:
        return True


def run():
    now = datetime.datetime.now()
    start_str = 'start script on {datetime}'.format(datetime=now)
    logger.info(start_str)
    # cur_time = datetime.datetime.combine(now.date(), now.time().replace(minute=0, second=0, microsecond=0))
    cur_time = now
    pre_time = cur_time - datetime.timedelta(hours=1)
    last_time = cur_time - datetime.timedelta(minutes=30)
    # last_time = cur_time + datetime.timedelta(hours=0)
    logger.info('begin_date:%s  end_date:%s' % (pre_time, last_time))
    region_channels = db.preload_channel.find({"username": {"$in": MONITOR_USER}, "region": {"$nin": ["null", []]}},
                                              {"channel_code": 1, "region": 1, "_id": 0})
    region_channel_list = []

    for channel in region_channels:
        if str(channel["channel_code"]) not in region_channel_list:
            region_channel_list.append(str(channel["channel_code"]))
            if "region" in channel:
                REG_CHAN_MAP[str(channel["channel_code"])] = channel["region"]
    # channel_code = channel["channel_code"]
    ind_url_dic = {"channel_code": {"$in": region_channel_list}, "created_time": {"$gte": pre_time, "$lt": last_time}
                   }  # "finish_time": {"$exists": "true"}
    channel_urls = db.preload_url.find(ind_url_dic, no_cursor_timeout=True)
    need_count = channel_urls.count()
    logger.debug("url count:%d" % need_count)
    if need_count == 0:
        return
    pool = ThreadPool(100)
    pool.map(process_url, channel_urls)
    # #close the pool and wait for the work to finish
    pool.close()
    pool.join()

    logger.debug("process url end")


def process_url(url):
    global REG_CHAN_MAP
    try:
        get_data = get_result_by_id(str(url["_id"]))["devices"]
    except Exception:
        logger.error(traceback.format_exc())
        return
    channel_code = str(url["channel_code"])
    region_devs = PRELOAD_DEVS.get(channel_code)
    fail_devs = []
    dev_list = []
    for k, v in list(get_data.items()):
        if v["preload_status"] != 200:
            dev = {"host": v.get('host')}
            dev_list.append(v.get('host'))
            fail_devs.append(dev)
    reg_name_list = []
    reg_host_list = []
    try:
        if getCallbackData(url):
            report_task(channel_code, REG_CHAN_MAP, url)
            logger.debug("retry send callback %s" % url["task_id"])
        [(reg_name_list.append(dd['name']), reg_host_list.append(dd['host'])) for dd in
         json.loads(region_devs)]
        fail_region_devs = list(set(reg_host_list).intersection(set(dev_list)))
        if fail_region_devs and calRegionDevicePer(len(reg_name_list), len(fail_region_devs)):
            # report_task(channel_code, region_channel_map, url)

            send_task(fail_devs, fail_region_devs, url, v)

            del_preload_errot_task(url.get('_id'), v.get("host"))
            # try:
            #     if getCallbackData(url):
            #         report_task(channel_code, region_channel_map, url)
            #         logger.debug("retry send callback %s" % url["task_id"])
            # except Exception,ex:
            #     logger.error(ex)


    except Exception:
        logger.error(traceback.format_exc())
        logger.error("error code:%s" % url["channel_code"])


if __name__ == '__main__':
    run()
    os._exit(0)
