#!/usr/bin/env python
# coding=utf-8
# Created by vance on 2015-03-09.

__author__ = 'vance'

from flask import Blueprint, request, make_response, jsonify
from core import database, postal, rcmsapi
from bson import ObjectId
import datetime
import traceback
from util import log_utils
from celery.task import task
from util.check_error_url import get_fail_url_device
import json
from bson.objectid import ObjectId
retry = Blueprint('retry', __name__, )
query_db_session = database.query_db_session()
db_session = database.db_session()
logger = log_utils.get_celery_Logger()

@retry.route("/internal/retry_user", methods=['GET', 'POST'])
def retry_user():
    try:
        result = {}
        logger.info(request.data)
        query_args = json.loads(request.data)
        logger.info(query_args)
        query_type = query_args.get('query_type')
        if query_type == 'normal_query':
            dt =datetime.datetime.strptime(query_args.get("date"), "%m/%d/%Y")
            query = {'created_time':{"$gte":dt, "$lt":(dt + datetime.timedelta(days=1))}}
        else:
            start_datetime =datetime.datetime.strptime(query_args.get("start_datetime"), "%Y-%m-%d %H")
            end_datetime = datetime.datetime.strptime(query_args.get("end_datetime"), "%Y-%m-%d %H")
            query = {'created_time':{"$gte":start_datetime, "$lt": end_datetime}}
        if query_args.get("username"):
            append_userfield(query_args.get("username"),query)
        #query['status']={"$ne":"FINISHED"}
        query['status']="FAILED"
        logger.info(query)
        dev_list=db_session.url.aggregate([{'$match':query},{'$group' : {'_id' : "$dev_id"}}])
        dev_list=list(dev_list)
        logger.info(dev_list)
        for dev_id in dev_list:
            dev_id=dev_id['_id']
            query['dev_id']=dev_id
            urls_list=db_session.url.find(query)

            dir_url_list=[]
            no_dir_url_list=[]
            for url_u in urls_list:
                if url_u['isdir']==True:
                    dir_url_list.append(url_u['_id'])
                else:
                    no_dir_url_list.append(url_u['_id'])

            for url_dir in dir_url_list:
                retry_task_urls([url_dir])
            if len(no_dir_url_list)>0:
                retry_task_urls(no_dir_url_list)
        result["code"] = 200
        result["message"] = 'ok'
        return jsonify(result)
    except Exception:
        logger.debug("retry error:%s" % traceback.format_exc())
        return jsonify({"code": 500, "message": "retry faild"})
@retry.route("/internal/page_retry", methods=['GET', 'POST'])
def page_retry():
    try:
        result = {}
        logger.info(request.data)
        query_args = json.loads(request.data)
        logger.info(query_args)
        strurl=query_args.get('strurl')
        urls=strurl.split(',')
        retrydict={}
        dirList=[]
        for urlid in urls:
            url=db_session.url.find_one({"_id": ObjectId(urlid)})
            if url.get('isdir'):
                dirList.append(ObjectId(urlid))
            else:
                retrydict.setdefault(url.get('dev_id'), []).append(ObjectId(urlid))
        for urldir in dirList:
            retry_task_urls([urldir])
        for keys in list(retrydict.keys()):
            retry_task_urls(retrydict.get(keys))
        result["code"] = 200
        result["message"] = 'ok'
        return jsonify(result)
    except Exception:
        logger.debug("retry error:%s" % traceback.format_exc())
        return jsonify({"code": 500, "message": "retry faild"})

def append_userfield(username,query):
    from cache import rediscache
    if rediscache.isFunctionUser(username):
        query['username']=username
    else:
        query['parent'] = username

@retry.route("/internal/retry/<uid>", methods=['GET'])
def retry_task(uid):
    """

    :param uid:
    :return:
    code  message
    200    ok
    404    Not found uid
    500    retry faild
    """
    try:
        logger.debug("get retry task uid {0}".format(uid))
        result = {}
        db_request = query_db_session.ref_err.find_one({"uid": ObjectId(uid)})
        if db_request:
            # queue.put_json2("retry_task", (uid,))
            if "retry_success" not in db_request:
                retry_worker.delay((uid,))
            else:
                logger.debug("get retry task uid {0} is success".format(uid))
            result["code"] = 200
            result["message"] = 'ok'
        else:
            if sync_ref_err(uid):
                # queue.put_json2("retry_task", (uid,))
                retry_worker.delay((uid,))
                result["code"] = 200
                result["message"] = 'ok'
            else:
                result["code"] = 404
                result["message"] = 'Not found uid {0}'.format(uid)
        logger.debug("finish retry task uid {0}".format(uid))
        return jsonify(result)
    except Exception:
        logger.debug("retry error:%s" % traceback.format_exc())
        return jsonify({"code": 500, "message": "retry faild"})


def sync_ref_err(uid):
    u_dic = get_fail_urls(uid)
    if u_dic:
        try:
            db_session.ref_err.insert(u_dic)
            return True
        except Exception:
            logger.debug("internal_search_task error:%s" % traceback.format_exc())
            return False
    else:
        return False


def get_fail_urls(uid):
    obj_url = query_db_session.url.find_one({"_id": ObjectId(uid)})
    if obj_url:
        u_dic = {}
        create_date = obj_url["created_time"]
        date = datetime.datetime.combine(create_date.date(),
                                         create_date.time().replace(minute=0, second=0, microsecond=0))
        u_dic['username'] = obj_url["parent"]  # 取主账户
        u_dic['uid'] = obj_url["_id"]
        u_dic['url'] = obj_url["url"]
        u_dic['channel_code'] = obj_url["channel_code"]
        u_dic['datetime'] = date
        u_dic['dev_id'] = obj_url["dev_id"]
        # u_dic['failed'], u_dic['f_devs'], u_dic['firstLayer'] = get_fail_url_device(obj_url["dev_id"])
        u_dic['failed'], u_dic['f_devs'], u_dic['firstLayer'], u_dic['devices'] = get_fail_url_device(query_db_session.device,obj_url["dev_id"])
        return u_dic
    else:
        return None




def get_url(uid):
    obj_url = query_db_session.url.find_one({"_id": ObjectId(uid)})
    if obj_url:
        return obj_url
    else:
        return None
def get_url_add_id(uid):
    obj_url = query_db_session.url.find_one({"_id": ObjectId(uid)})
    if obj_url:
        obj_url['id']=uid
        return obj_url
    else:
        return None


def get_rcms_devices(urls):
    devs_f = []
    devs = rcmsapi.getDevices(urls[0].get("channel_code"))
    dev_s = [dev['name'] for dev in devs if dev['status'] == 'OPEN']

    logger.debug('get_rcms_device:%s' % urls[0].get("layer_type"))
    if urls[0].get("is_multilayer"):
        devs_f = rcmsapi.getFirstLayerDevices(urls[0].get("channel_code"))
        devs_f = [dev['name'] for dev in devs_f if dev['status'] == 'OPEN']
    return dev_s, devs_f


def update_devices(dev_id, results):
    dev_obj = query_db_session.device.find_one({"_id": dev_id})
    fail_list = []
    for d in results:
        code = d['code']
        if code not in [200, 204]:
            fail_list.append(d['name'])
        dev_obj['devices'][d['name']]['code'] = code
        dev_obj['devices'][d['name']]['connect_cost'] = d['connect_cost']
        dev_obj['devices'][d['name']]['total_cost'] = d['total_cost']
        dev_obj['devices'][d['name']]['response_cost'] = d['response_cost']

    dev_obj["finish_time"] = datetime.datetime.now()
    db_session.device.save(dev_obj)
    return fail_list


def save_rey_devices(results):
    # TTL: db.retry_device.ensureIndex( { "finish_time": -1 }, { expireAfterSeconds: 60*60*24*7 })

    fail_list = [d['name'] for d in results["devices"] if d['code'] not in [200, 204]]

    results["finish_time"] = datetime.datetime.now()
    r_obj = db_session.retry_device.insert(results)

    return fail_list, r_obj

def update_url(uid, retry_obj, fail_list):
    url_obj = query_db_session.url.find_one({"_id": uid})
    url_obj["retry_time"] = datetime.datetime.now()
    try:
        url_obj["retrys"] += 1
        url_obj["r_dev_id"] = retry_obj
    except:
        url_obj["retrys"] = 1
        url_obj["r_dev_id"] = retry_obj

    logger.debug('fail_list %s'%fail_list)
    if not fail_list:
        url_obj["status"] = 'FINISHED'
        url_obj["retry_success"] = 1
        err_obj =query_db_session.ref_err.find_one({"uid": uid})
        err_obj["retry_success"] = 1
        db_session.ref_err.save(err_obj)
    else:
        url_obj["status"] = 'FAILED'

    db_session.url.save(url_obj)

#同一个设备组
def retry_task_urls(uids):
    """

    :param uid:
    :return:
    code  message
    200    ok
    404    Not found uid
    500    retry faild
    """
    logger.debug("get retry task uids {0}".format(uids))
    uid_list=[]
    for uid in uids:
        try:
            db_request = query_db_session.ref_err.find_one({"uid": uid})#找到url
            if db_request:
                # queue.put_json2("retry_task", (uid,))
                if "retry_success" not in db_request:
                    uid_list.append(uid)
                else:
                    logger.debug("get retry task uid {0} is success".format(uid))
            else:
                if sync_ref_err(str(uid)):#没有将url同步到ref_err中
                    # queue.put_json2("retry_task", (uid,))
                    uid_list.append(uid)
            #logger.debug("finish retry task uid {0}".format(uid))
        except Exception:
            logger.debug("retry error:%s" % traceback.format_exc())
    retry_new_work.delay((uid_list,))

@task(ignore_result=True, default_retry_delay=10, max_retries=3)
def retry_new_work(task):
    logger.info("retry worker get uids {0}".format(task[0]))
    devs_f = []
    devs = []
    devices = []
    results= {}
    dev_fail = []
    uid_list= task[0]
    isDir=False
    if len(uid_list)<1 :
        return
    elif len(uid_list)==1 :
        isDir=query_db_session.url.find_one({"_id": uid_list[0]})['isdir']

    urls=[]
    for uid in uid_list:
        urls.append(get_url_add_id(uid))
    db_ref_err = query_db_session.ref_err.find_one({"uid": uid_list[0]})   
    rcms_dev_s, rcms_dev_f = get_rcms_devices(urls)#根据url中的channels信息，从redis中寻找设备，redis中

    if db_ref_err['firstLayer']:
        devs_f = [{"name": k, "host": v, 'firstLayer': True, "status": "OPEN" if k in rcms_dev_f else "SUSPEND"} for k, v in
                  list(db_ref_err['f_devs'].items())]
    if isDir:
        logger.info("dir retry id list: %s"%uid_list)
        devices.extend(update_result(devs_f, postal.do_send_dir(urls[0], devs_f)))#保存设备，下发url
    else:
        devices.extend(update_result(devs_f, postal.do_send_url(urls, devs_f)))#保存设备，下发url
        
    logger.info("send first layer devs {0}".format(len(devs_f)))

    devs = [{"name": k, "host": v, 'firstLayer': False, "status": "OPEN" if k in rcms_dev_s else "SUSPEND"} for d in
            db_ref_err['failed'] for dd in d["devices"] for k, v in list(dd.items())]
    if devs:
        if isDir:
            devices.extend(update_result(devs, postal.do_send_dir(urls[0], devs)))
        else:
            devices.extend(update_result(devs, postal.do_send_url(urls, devs)))
        logger.debug(devices)
    results["devices"] = devices
    dev_fail, retry_obj = save_rey_devices(results)#保存重试device数据库
    for uid in uid_list :
    	update_url(ObjectId(uid), retry_obj, dev_fail)#保存url数据库，插入成功的数据，错误列表

    logger.info("send second layer devs {0}".format(len(devs)))

def update_result(devices,result):
     # [t1 if t1.update(t2) else t2 for t1 in aa for t2 in bb if t1['name']==t2['name']]
    # [dict(t1,**t2) for t1 in aa for t2 in bb if t1['name']==t2['name']]
    return [dict(dd, **re) for dd in devices for re in result if dd["name"] == re["name"]]


@task(ignore_result=True, default_retry_delay=10, max_retries=3)
def retry_worker(task):
    logger.info("retry worker get uid {0}".format(task[0]))
    uid = task[0]
    devs_f = []
    devs = []
    devices = []
    results= {}
    dev_fail = []
    results ={"created_time":datetime.datetime.now()}
    db_ref_err = query_db_session.ref_err.find_one({"uid": ObjectId(uid)})
    db_url = query_db_session.url.find_one({"_id": ObjectId(uid)})
    try:
        if db_ref_err:
            urls = [get_url(uid)]
            rcms_dev_s, rcms_dev_f = get_rcms_devices(urls)
            if db_ref_err['firstLayer']:
                devs_f = [{"name": k, "host": v, 'firstLayer': True, "status": "OPEN" if k in rcms_dev_f else "SUSPEND"} for k, v in
                          list(db_ref_err['f_devs'].items())]
                if db_url['isdir']:
                    devices.extend(update_result(devs_f, postal.do_send_dir(urls, devs_f)))
                else:
                    devices.extend(update_result(devs_f, postal.do_send_url(urls, devs_f)))

                logger.info("send first layer devs {0}".format(len(devs_f)))

            devs = [{"name": k, "host": v, 'firstLayer': False, "status": "OPEN" if k in rcms_dev_s else "SUSPEND"} for d in
                    db_ref_err['failed'] for dd in d["devices"] for k, v in list(dd.items())]
            if devs:
                if db_url['isdir']:
                    devices.extend(update_result(devs, postal.do_send_dir(urls, devs)))
                else:
                    devices.extend(update_result(devs, postal.do_send_url(urls, devs)))
                logger.debug(devices)
            results["devices"] = devices
            dev_fail, retry_obj = save_rey_devices(results)
            update_url(ObjectId(uid), retry_obj, dev_fail)

            logger.info("send second layer devs {0}".format(len(devs)))
    except Exception:
        logger.info("retry worker get devices {0}".format(traceback.format_exc()))

        # [{'code': 503, 'name': u'CHN-WX-b-3SE', 'total_cost': 0, 'connect_cost': 0, 'host': u'58.215.107.35', 'response_cost': 0, 'firstLayer': None}, {'code': 503, 'name': u'CHN-JG-2-3Se', 'total_cost': 0, 'connect_cost': 0, 'host': u'221.233.42.66', 'response_cost': 0, 'firstLayer': None}, {'code': 503, 'name': u'CHN-JG-2-3Sc', 'total_cost': 0, 'connect_cost': 0, 'host': u'221.233.42.64', 'response_cost': 0, 'firstLayer': None}, {'code': 503, 'name': u'CHN-JG-2-3SL', 'total_cost': 0, 'connect_cost': 0, 'host': u'221.233.42.47', 'response_cost': 0, 'firstLayer': None}, {'code': 503, 'name': u'CNC-CQ-2-3SG', 'total_cost': 0, 'connect_cost': 0, 'host': u'113.207.20.164', 'response_cost': 0, 'firstLayer': None}, {'code': 503, 'name': u'CHN-SX-2-3SO', 'total_cost': 0, 'connect_cost': 0, 'host': u'115.231.15.55', 'response_cost': 0, 'firstLayer': None}, {'code': 503, 'name': u'CHN-QX-f-3SG', 'total_cost': 0, 'connect_cost': 0, 'host': u'171.107.84.91', 'response_cost': 0, 'firstLayer': None}, {'code': 503, 'name': u'CNC-LQ-c-3WG', 'total_cost': 0, 'connect_cost': 0, 'host': u'61.240.135.199', 'response_cost': 0, 'firstLayer': None}, {'code': 503, 'name': u'CNC-XD-b-3W1', 'total_cost': 0, 'connect_cost': 0, 'host': u'221.204.21.2', 'response_cost': 0, 'firstLayer': None}, {'code': 503, 'name': u'CNC-CQ-2-3SO', 'total_cost': 0, 'connect_cost': 0, 'host': u'113.207.20.174', 'response_cost': 0, 'firstLayer': None}, {'code': 503, 'name': u'CHN-YN-b-3SV', 'total_cost': 0, 'connect_cost': 0, 'host': u'61.178.248.52', 'response_cost': 0, 'firstLayer': None}, {'code': 503, 'name': u'WAS-HZ-1-3dB', 'total_cost': 0, 'connect_cost': 0, 'host': u'113.215.1.202', 'response_cost': 0, 'firstLayer': None}]
        # [2015-03-17 16:20:23,199: DEBUG/MainProcess] [{'code': 503, 'name': u'CHN-WX-b-3SE', 'total_cost': 0, 'connect_cost': 0, 'host': u'58.215.107.35', 'response_cost': 0, 'firstLayer': None}, {'code': 503, 'name': u'CHN-JG-2-3Se', 'total_cost': 0, 'connect_cost': 0, 'host': u'221.233.42.66', 'response_cost': 0, 'firstLayer': None}, {'code': 503, 'name': u'CHN-JG-2-3Sc', 'total_cost': 0, 'connect_cost': 0, 'host': u'221.233.42.64', 'response_cost': 0, 'firstLayer': None}, {'code': 503, 'name': u'CHN-JG-2-3SL', 'total_cost': 0, 'connect_cost': 0, 'host': u'221.233.42.47', 'response_cost': 0, 'firstLayer': None}, {'code': 503, 'name': u'CNC-CQ-2-3SG', 'total_cost': 0, 'connect_cost': 0, 'host': u'113.207.20.164', 'response_cost': 0, 'firstLayer': None}, {'code': 503, 'name': u'CHN-SX-2-3SO', 'total_cost': 0, 'connect_cost': 0, 'host': u'115.231.15.55', 'response_cost': 0, 'firstLayer': None}, {'code': 503, 'name': u'CHN-QX-f-3SG', 'total_cost': 0, 'connect_cost': 0, 'host': u'171.107.84.91', 'response_cost': 0, 'firstLayer': None}, {'code': 503, 'name': u'CNC-LQ-c-3WG', 'total_cost': 0, 'connect_cost': 0, 'host': u'61.240.135.199', 'response_cost': 0, 'firstLayer': None}, {'code': 503, 'name': u'CNC-XD-b-3W1', 'total_cost': 0, 'connect_cost': 0, 'host': u'221.204.21.2', 'response_cost': 0, 'firstLayer': None}, {'code': 503, 'name': u'CNC-CQ-2-3SO', 'total_cost': 0, 'connect_cost': 0, 'host': u'113.207.20.174', 'response_cost': 0, 'firstLayer': None}, {'code': 503, 'name': u'CHN-YN-b-3SV', 'total_cost': 0, 'connect_cost': 0, 'host': u'61.178.248.52', 'response_cost': 0, 'firstLayer': None}, {'code': 503, 'name': u'WAS-HZ-1-3dB', 'total_cost': 0, 'connect_cost': 0, 'host': u'113.215.1.202', 'response_cost': 0, 'firstLayer': None}]

        # [{'status': 'OPEN', 'name': 'CMN-BJ-5-3SM', 'serialNumber': '07001053SM', 'host': '221.179.182.164', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'GWB-GZ-2-3C9', 'serialNumber': '23002023C9', 'host': '211.162.60.149', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CNC-DX-2-3WI', 'serialNumber': '06011023WI', 'host': '183.95.152.113', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CNC-SY-b-3g1', 'serialNumber': '060024b3g1', 'host': '218.60.45.42', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CNC-ZB-2-3g1', 'serialNumber': '06053323g1', 'host': '27.195.145.12', 'firstLayer': False, 'port': 21108}, {'status': 'SUSPEND', 'name': 'CNC-YJ-3-338', 'serialNumber': '0604333338', 'host': '122.136.65.137', 'firstLayer': False, 'port': 21108}, {'status': 'SUSPEND', 'name': 'CNC-ZU-2-3SN', 'serialNumber': '06075623SN', 'host': '112.90.147.177', 'firstLayer': False, 'port': 21108}, {'status': 'SUSPEND', 'name': 'CNC-NK-3-3gE', 'serialNumber': '06011933gE', 'host': '125.39.78.153', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CHN-CA-g-3SJ', 'serialNumber': '010519g3SJ', 'host': '58.216.31.174', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CNC-WZ-2-3g9', 'serialNumber': '06057723g9', 'host': '60.12.50.10', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CHN-YL-c-3SD', 'serialNumber': '010112c3SD', 'host': '175.6.10.162', 'firstLayer': False, 'port': 21108}, {'status': 'SUSPEND', 'name': 'CNC-JN-Q-356', 'serialNumber': '060531Q356', 'host': '60.217.232.249', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CHN-GL-c-3g1', 'serialNumber': '010773c3g1', 'host': '222.84.188.200', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CNC-QD-2-3O5', 'serialNumber': '06053223O5', 'host': '123.235.33.48', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CHN-NB-4-3SB', 'serialNumber': '01057443SB', 'host': '183.136.195.39', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CNC-HT-5-3g7', 'serialNumber': '06047153g7', 'host': '116.114.22.227', 'firstLayer': False, 'port': 21108}, {'status': 'SUSPEND', 'name': 'CNC-YZ-2-3S2', 'serialNumber': '06051423S2', 'host': '112.84.133.33', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CNC-CY-3-3SJ', 'serialNumber': '06001733SJ', 'host': '111.202.7.182', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CNC-HT-5-3P1', 'serialNumber': '06047153P1', 'host': '116.114.22.21', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CMN-GY-1-3S7', 'serialNumber': '07085113S7', 'host': '117.135.194.44', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CHN-KI-b-3gB', 'serialNumber': '010147b3gB', 'host': '182.247.232.32', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CNC-CT-2-3gH', 'serialNumber': '06011323gH', 'host': '101.28.252.4', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CNC-CP-2-3HA', 'serialNumber': '06013723HA', 'host': '113.207.33.11', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CHN-FS-2-3B4', 'serialNumber': '01075723B4', 'host': '183.60.196.7', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'BGC-BJ-3-3SH', 'serialNumber': '16001033SH', 'host': '111.206.10.158', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CHN-JG-2-3SL', 'serialNumber': '01038023SL', 'host': '221.233.42.47', 'firstLayer': False, 'port': 21108}, {'status': 'SUSPEND', 'name': 'CNC-BJ-9-3SR', 'serialNumber': '06001093SR', 'host': '111.206.216.178', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CNC-SY-b-3H1', 'serialNumber': '060024b3H1', 'host': '218.60.45.5', 'firstLayer': False, 'port': 21108}, {'status': 'SUSPEND', 'name': 'CER-GZ-1-3PA', 'serialNumber': '03002013PA', 'host': '222.201.134.13', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CHN-YL-b-3TV', 'serialNumber': '010112b3TV', 'host': '175.6.10.102', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CNC-YG-2-3gB', 'serialNumber': '06015423gB', 'host': '222.163.198.56', 'firstLayer': False, 'port': 21108}, {'status': 'SUSPEND', 'name': 'CNC-ZZ-5-397', 'serialNumber': '0603715397', 'host': '61.158.249.138', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CHN-DG-6-3SN', 'serialNumber': '01076963SN', 'host': '183.61.240.121', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CNC-CQ-2-3SO', 'serialNumber': '06002323SO', 'host': '113.207.20.174', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CNC-YZ-2-3g1', 'serialNumber': '06051423g1', 'host': '112.84.133.81', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CHN-JG-2-3Se', 'serialNumber': '01038023Se', 'host': '221.233.42.66', 'firstLayer': False, 'port': 21108}, {'status': 'SUSPEND', 'name': 'CMN-CD-2-3g4', 'serialNumber': '07002823g4', 'host': '117.139.18.137', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CHN-YZ-2-3g2', 'serialNumber': '01051423g2', 'host': '180.97.183.126', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CNC-HB-2-3g3', 'serialNumber': '06045123g3', 'host': '210.76.58.79', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CHN-WY-2-3gB', 'serialNumber': '01014923gB', 'host': '58.220.22.100', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'GWB-BJ-4-3SC', 'serialNumber': '23001043SC', 'host': '124.202.164.213', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CNC-CY-2-3gL', 'serialNumber': '06001723gL', 'host': '111.202.7.32', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'UNI-HZ-2-3g2', 'serialNumber': '05057123g2', 'host': '101.71.11.63', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CMN-SH-1-3SA', 'serialNumber': '07002113SA', 'host': '117.144.230.48', 'firstLayer': False, 'port': 21108}, {'status': 'SUSPEND', 'name': 'CNC-SY-A-3SA', 'serialNumber': '060024A3SA', 'host': '124.95.142.216', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CNC-LQ-c-3Sb', 'serialNumber': '060320c3Sb', 'host': '61.240.135.176', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CNC-ST-2-3SN', 'serialNumber': '06075423SN', 'host': '163.177.135.54', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CNC-JS-b-3WC', 'serialNumber': '060111b3WC', 'host': '182.118.77.13', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CHN-DL-2-3SF', 'serialNumber': '01041123SF', 'host': '42.202.151.46', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CNC-LQ-c-3WG', 'serialNumber': '060320c3WG', 'host': '61.240.135.199', 'firstLayer': False, 'port': 21108}, {'status': 'SUSPEND', 'name': 'CHN-JA-g-3S3', 'serialNumber': '010271g3S3', 'host': '116.211.123.206', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CNC-ZZ-9-3S7', 'serialNumber': '06037193S7', 'host': '182.118.46.149', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CNC-GX-c-3gH', 'serialNumber': '060120c3gH', 'host': '211.90.28.233', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'WAS-HZ-1-3dB', 'serialNumber': '95057113dB', 'host': '113.215.1.202', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CHN-WX-b-3SE', 'serialNumber': '010051b3SE', 'host': '58.215.107.35', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CHN-TH-2-3gH', 'serialNumber': '01011623gH', 'host': '115.231.150.15', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CHN-XY-3-3S1', 'serialNumber': '01044133S1', 'host': '221.235.199.20', 'firstLayer': False, 'port': 21108}, {'status': 'SUSPEND', 'name': 'CNC-GX-b-3gB', 'serialNumber': '060120b3gB', 'host': '211.90.28.98', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CNC-ZJ-2-3g1', 'serialNumber': '06075923g1', 'host': '163.177.169.100', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CHN-DJ-2-3g6', 'serialNumber': '01012823g6', 'host': '183.131.128.32', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CHN-MY-1-3S5', 'serialNumber': '01081613S5', 'host': '220.166.65.36', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'BGC-BJ-3-3SM', 'serialNumber': '16001033SM', 'host': '111.206.10.164', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CHN-CY-4-3SS', 'serialNumber': '01001743SS', 'host': '119.90.14.65', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CNC-DX-2-3gB', 'serialNumber': '06011023gB', 'host': '183.95.152.2', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CNC-DL-3-3g4', 'serialNumber': '06041133g4', 'host': '218.60.107.133', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CHN-YN-b-3SV', 'serialNumber': '010117b3SV', 'host': '61.178.248.52', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CNC-HQ-f-3WH', 'serialNumber': '060105f3WH', 'host': '119.188.139.40', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CNC-XT-2-3gD', 'serialNumber': '06031923gD', 'host': '60.6.197.24', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CNC-JS-c-3WB', 'serialNumber': '060111c3WB', 'host': '182.118.78.12', 'firstLayer': False, 'port': 21108}, {'status': 'SUSPEND', 'name': 'CHN-LH-c-3gB', 'serialNumber': '010035c3gB', 'host': '60.165.56.60', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CHN-GL-b-3g1', 'serialNumber': '010773b3g1', 'host': '222.84.188.70', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CNC-NS-2-3gE', 'serialNumber': '06011823gE', 'host': '36.250.90.5', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CNC-BJ-4-3kB', 'serialNumber': '06001043kB', 'host': '123.125.19.85', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CHN-SX-2-3SO', 'serialNumber': '01057523SO', 'host': '115.231.15.55', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CHN-QX-f-3SG', 'serialNumber': '010107f3SG', 'host': '171.107.84.91', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CNC-ZU-2-3HD', 'serialNumber': '06075623HD', 'host': '112.90.147.194', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CNC-NK-3-3g2', 'serialNumber': '06011933g2', 'host': '125.39.78.164', 'firstLayer': False, 'port': 21108}, {'status': 'SUSPEND', 'name': 'CNC-GX-b-3SB', 'serialNumber': '060120b3SB', 'host': '211.90.28.42', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CNC-XD-b-3W1', 'serialNumber': '060108b3W1', 'host': '221.204.21.2', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CHN-ST-I-39A', 'serialNumber': '010754I39A', 'host': '202.104.237.112', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CNC-CQ-2-3SG', 'serialNumber': '06002323SG', 'host': '113.207.20.164', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CNC-JS-b-3SS', 'serialNumber': '060111b3SS', 'host': '182.118.77.69', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CHN-LH-b-3gB', 'serialNumber': '010035b3gB', 'host': '60.165.55.168', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CNC-CC-b-3H7', 'serialNumber': '060431b3H7', 'host': '222.161.226.63', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CHN-JM-2-3gB', 'serialNumber': '01072423gB', 'host': '221.235.254.115', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CNC-DZ-2-3gB', 'serialNumber': '06053423gB', 'host': '218.58.209.106', 'firstLayer': False, 'port': 21108}, {'status': 'SUSPEND', 'name': 'CNC-TY-7-3B1', 'serialNumber': '06035173B1', 'host': '221.204.242.126', 'firstLayer': False, 'port': 21108}, {'status': 'SUSPEND', 'name': 'CNC-BZ-3-3yN', 'serialNumber': '06054333yN', 'host': '218.59.209.176', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CNC-XD-b-3SZ', 'serialNumber': '060108b3SZ', 'host': '221.204.21.56', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CNC-HQ-f-3Sa', 'serialNumber': '060105f3Sa', 'host': '119.188.139.111', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CHN-JP-c-3g1', 'serialNumber': '010124c3g1', 'host': '171.107.188.173', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CHN-DG-6-3Se', 'serialNumber': '01076963Se', 'host': '14.17.87.22', 'firstLayer': False, 'port': 21108}, {'status': 'SUSPEND', 'name': 'CNC-HB-2-3SK', 'serialNumber': '06045123SK', 'host': '210.76.58.51', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CNC-TI-2-3g1', 'serialNumber': '06014523g1', 'host': '218.24.17.40', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CHN-JG-2-3Sc', 'serialNumber': '01038023Sc', 'host': '221.233.42.64', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CHN-NC-b-3gB', 'serialNumber': '010791b3gB', 'host': '59.63.195.54', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CHN-LU-2-3gF', 'serialNumber': '01083023gF', 'host': '61.139.127.81', 'firstLayer': False, 'port': 21108}, {'status': 'SUSPEND', 'name': 'CNC-SY-3-3gB', 'serialNumber': '06002433gB', 'host': '124.95.148.104', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CHN-CO-2-3gB', 'serialNumber': '01015123gB', 'host': '180.97.235.68', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CNC-YY-2-3gB', 'serialNumber': '06014023gB', 'host': '58.20.132.56', 'firstLayer': False, 'port': 21108}, {'status': 'SUSPEND', 'name': 'CNC-ZZ-5-3SJ', 'serialNumber': '06037153SJ', 'host': '182.118.12.157', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'GWB-BJ-4-3S3', 'serialNumber': '23001043S3', 'host': '124.202.164.202', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CHN-CS-4-3SV', 'serialNumber': '01073143SV', 'host': '124.232.148.93', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CHN-JA-h-3ST', 'serialNumber': '010271h3ST', 'host': '116.211.124.40', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CHN-FH-2-3g5', 'serialNumber': '01015823g5', 'host': '111.170.232.34', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CER-BJ-3-354', 'serialNumber': '0300103354', 'host': '121.194.1.123', 'firstLayer': False, 'port': 21108}, {'status': 'SUSPEND', 'name': 'CHN-XA-1-3yZ', 'serialNumber': '01002913yZ', 'host': '117.34.23.49', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CMN-BJ-5-3SK', 'serialNumber': '07001053SK', 'host': '221.179.182.162', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CNC-YZ-2-3X1', 'serialNumber': '06051423X1', 'host': '112.84.133.6', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CHN-FS-3-3q3', 'serialNumber': '01075733q3', 'host': '183.60.196.205', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'BNC-BJ-1-3SO', 'serialNumber': '59001013SO', 'host': '49.5.6.228', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CHN-MY-1-3SD', 'serialNumber': '01081613SD', 'host': '220.166.65.44', 'firstLayer': False, 'port': 21108}, {'status': 'OPEN', 'name': 'CHN-HH-2-3gB', 'serialNumber': '01057223gB', 'host': '115.231.28.100', 'firstLayer': False, 'port': 21108}, {'status': 'SUSPEND', 'name': 'CHN-HZ-1-3C2', 'serialNumber': '01057113C2', 'host': '61.175.171.102', 'firstLayer': True, 'port': 21108}, {'status': 'OPEN', 'name': 'CHN-LN-f-3Sb', 'serialNumber': '010106f3Sb', 'host': '122.228.85.112', 'firstLayer': True, 'port': 21108}, {'status': 'OPEN', 'name': 'CHN-LG-c-3g7', 'serialNumber': '010123c3g7', 'host': '122.228.115.82', 'firstLayer': True, 'port': 21108}, {'status': 'OPEN', 'name': 'CHN-LN-g-3SS', 'serialNumber': '010106g3SS', 'host': '122.228.85.167', 'firstLayer': True, 'port': 21108}, {'status': 'SUSPEND', 'name': 'CHN-ST-H-39A', 'serialNumber': '010754H39A', 'host': '202.104.237.16', 'firstLayer': True, 'port': 21108}, {'status': 'OPEN', 'name': 'UNI-ZM-2-3gB', 'serialNumber': '05039623gB', 'host': '202.110.80.22', 'firstLayer': True, 'port': 21108}, {'status': 'SUSPEND', 'name': 'CHN-HZ-4-35A', 'serialNumber': '010571435A', 'host': '61.164.60.241', 'firstLayer': True, 'port': 21108}]
