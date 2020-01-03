#-*- coding: UTF-8 -*-

from bson import ObjectId
from core import redisfactory, rcmsapi, models
from datetime import datetime, timedelta
from core.database import query_db_session,db_session, s1_db_session
from logging import Formatter
import traceback, gzip, os, copy
import logging,hashlib ,re
import logging.handlers
import httplib2 as httplib
import pymongo,math,time
import simplejson as json
from util import log_utils ,dict_add
from util.tools import get_current_date_str, DatetimeJSONEncoder, JSONEncoder
from core.models import MONITOR_DEVICE_STATUS, MONITOR_DEVICE_STATUS_FAILED
from util.tools import calculate_diff_between_time, strip_list, operation_record_into_mongo
from util.cert_tools import make_validity_to_China
from core.config import config
from util.tools import get_mongo_str
#from receiver.retry_task import retry_task_urls
# logger = logging.getLogger("admin")
# logger.setLevel(logging.DEBUG)
logger = log_utils.get_admin_Logger()

db = db_session()
q_db = query_db_session()
monitor_db = s1_db_session()

COUNTER_CACHE = redisfactory.getDB(4)
BLACKLIST = redisfactory.getDB(1)
H_PRIORITY_CACHE = REWRITE_CACHE = redisfactory.getDB(15)
REGEXCONFIG = redisfactory.getDB(8)
CERT_TRANS_CACHE = redisfactory.getDB(10)
CERT_QUERY_CACHE = redisfactory.getDB(9)
TRANSFER_CERT_CACHE = redisfactory.getDB(9)

#monitor
M_CACHERECORD = redisfactory.getMDB(7)

CALLBACK_CACHE = redisfactory.getDB(14)
prefix_callback_email_username = "CALLBACK_EMAIL_"

DOMAIN_INGNOE = redisfactory.getDB(9)
DOMAIN_KEY = "domain_ignore"

DIRANDURL = redisfactory.getDB(9)
DIRANDURL_KEY = "dir_and_url"


class User():
    def __init__(self, account, role="guest"):
        self.account = account
        self.role = role

def find_urls(query_args):
    per_page = 30
    urls_dict = {"urls":[],"totalpage":0}
    query_type = query_args.get('query_type')
    if query_type == 'normal_query':
        dt = datetime.strptime(query_args.get("date"), "%m/%d/%Y")
        query = {'created_time':{"$gte":dt, "$lt":(dt + timedelta(days=1))}}
    else:
        start_datetime = datetime.strptime(query_args.get("start_datetime"), "%Y-%m-%d %H")
        end_datetime = datetime.strptime(query_args.get("end_datetime"), "%Y-%m-%d %H")
        query = {'created_time':{"$gte":start_datetime, "$lt": end_datetime}}
    if query_args.get("username"):
        append_userfield(query_args.get("username"),query)
    if query_args.get("channel_name"):
        query['channel_name'] = query_args.get('channel_name')
    url_str = query_args.get("url")
    if  url_str:
        if (url_str.find('*')>0):
            url_str=url_str.replace('*','\*')
        query['url'] = re.compile("^%s.*" %url_str)

    if query_args.get("status") != "ALL":
        query['status'] = query_args.get("status")
    if query_args.get("status") == "ALL" and query_args.get("username") == '' and query_args.get("url") == '' and query_args.get('channel_name') == '':
        pass
    else:
        logger.debug("query:%s" % str(query))
        totalpage = int(math.ceil(q_db.url.find(query).limit(600).count(True)/(per_page*1.00)))
        urls_dict ={"urls": load_url([u for u in q_db.url.find(query).sort('created_time', pymongo.DESCENDING).skip(query_args.get("curpage")*per_page).limit(per_page)]) ,"totalpage" : totalpage}
    return urls_dict


def find_cert_tasks(query_args):
    '''
    查询证书下发任务
    '''
    per_page = 30
    tasks_dict = {"tasks":[],"totalpage":0}
    query_type = query_args.get('query_type')
    if query_type == 'normal_query':
        dt = datetime.strptime(query_args.get("date"), "%m/%d/%Y")
        query = {'created_time':{"$gte":dt, "$lt":(dt + timedelta(days=1))}}
    else:
        start_datetime = datetime.strptime(query_args.get("start_datetime"), "%Y-%m-%d %H")
        end_datetime = datetime.strptime(query_args.get("end_datetime"), "%Y-%m-%d %H")
        query = {'created_time':{"$gte":start_datetime, "$lt": end_datetime}}
    if query_args['task_id']:
        query['_id'] = ObjectId(query_args['task_id'])
    if query_args.get("username"):
        query['username'] = query_args['username']
    if query_args.get("status") != "ALL":
        query['status'] = query_args.get("status")
        logger.debug("query:%s" % str(query))
    if query_args.get("status") == "ALL" and query_args.get("username") == '' and query_args.get("task_id") == '':
        pass
    else:
        totalpage = int(math.ceil(monitor_db.cert_trans_tasks.find(query).limit(600).count(True)/(per_page*1.00)))
        tasks_dict ={"tasks": load_cert_task([u for u in monitor_db.cert_trans_tasks.find(query).sort('created_time', pymongo.DESCENDING).skip(query_args.get("curpage")*per_page).limit(per_page)]) ,"totalpage" : totalpage}

    return tasks_dict

def find_cert_query_tasks(query_args):
    '''
    证书查询任务下发
    '''
    per_page = 30
    tasks_dict = {"tasks":[],"totalpage":0}
    query_type = query_args.get('query_type')
    if query_type == 'normal_query':
        dt = datetime.strptime(query_args.get("date"), "%m/%d/%Y")
        query = {'created_time':{"$gte":dt, "$lt":(dt + timedelta(days=1))}}
    else:
        start_datetime = datetime.strptime(query_args.get("start_datetime"), "%Y-%m-%d %H")
        end_datetime = datetime.strptime(query_args.get("end_datetime"), "%Y-%m-%d %H")
        query = {'created_time':{"$gte":start_datetime, "$lt": end_datetime}}
    if query_args['task_id']:
        query['_id'] = ObjectId(query_args['task_id'])
    if query_args.get("username"):
        query['username'] = query_args['username']
    if query_args.get("status") != "ALL":
        query['status'] = query_args.get("status")
        logger.debug("query:%s" % str(query))
    if query_args.get("status") == "ALL" and query_args.get("username") == '' and query_args.get("task_id") == '':
        pass
    else:
        totalpage = int(math.ceil(monitor_db.cert_query_tasks.find(query).limit(600).count(True)/(per_page*1.00)))
        tasks_dict ={"tasks": load_cert_task([u for u in monitor_db.cert_query_tasks.find(query).sort('created_time', pymongo.DESCENDING).skip(query_args.get("curpage")*per_page).limit(per_page)]) ,"totalpage" : totalpage}

    return tasks_dict

def find_transfer_cert_tasks(query_args):
    '''
    转移证书任务下发
    '''
    per_page = 30
    tasks_dict = {"tasks":[],"totalpage":0}
    query_type = query_args.get('query_type')
    if query_type == 'normal_query':
        dt = datetime.strptime(query_args.get("date"), "%m/%d/%Y")
        query = {'created_time':{"$gte":dt, "$lt":(dt + timedelta(days=1))}}
    else:
        start_datetime = datetime.strptime(query_args.get("start_datetime"), "%Y-%m-%d %H")
        end_datetime = datetime.strptime(query_args.get("end_datetime"), "%Y-%m-%d %H")
        query = {'created_time':{"$gte":start_datetime, "$lt": end_datetime}}
    if query_args['task_id']:
        query['_id'] = ObjectId(query_args['task_id'])
    if query_args.get("username"):
        query['username'] = query_args['username']
    if query_args.get("status") != "ALL":
        query['status'] = query_args.get("status")
        logger.debug("query:%s" % str(query))
    if query_args.get("status") == "ALL" and query_args.get("username") == '' and query_args.get("task_id") == '':
        pass
    else:
        totalpage = int(math.ceil(monitor_db.transfer_cert_tasks.find(query).limit(600).count(True)/(per_page*1.00)))
        tasks_dict ={"tasks": load_cert_task([u for u in monitor_db.transfer_cert_tasks.find(query).sort('created_time', pymongo.DESCENDING).skip(query_args.get("curpage")*per_page).limit(per_page)]) ,"totalpage" : totalpage}

    return tasks_dict


def find_cert(query_args):
    '''
    查询证书
    '''
    per_page = 30
    certs_dict = {"certs":[],"totalpage":0}
    query = {}
    if query_args['cert_id']:
        query['_id'] = ObjectId(query_args['cert_id'])
    if query_args.get('username'):
        query['username'] = query_args['username']
    if query_args.get('cert_alias'):
        query['cert_alias'] = query_args['cert_alias']
    if query_args.get('save_name'):
        query['save_name'] = query_args['save_name']
    if query_args.get('type')=='all':
        totalpage = int(math.ceil(monitor_db.cert_detail.find(query).count(True)/(per_page*1.00)))
        certs_dict ={"certs": make_cert_validity([u for u in monitor_db.cert_detail.find(query).sort('_id', pymongo.DESCENDING).skip(query_args.get("curpage")*per_page).limit(per_page)]) ,"totalpage" : totalpage}
        for c in certs_dict["certs"]:
            c["validity_china"]["end_time"]=datetime.strptime(c["validity_china"]["end_time"], "%Y%m%d%H%M%S")
            c["validity_china"]["begin_time"]=datetime.strptime(c["validity_china"]["begin_time"], "%Y%m%d%H%M%S")
    elif query_args.get('type')=='expired':
        all_cert = monitor_db.cert_detail.find(query)
        nowtime = int(time.strftime("%Y%m%d%H%M%S", time.localtime()))
        cert_list=[]
        sum = 0
        for cert in all_cert:
            cert['validity_china'] = make_validity_to_China(cert['validity'])
            t = int(cert['validity_china']['end_time'])
            tt = t - nowtime
            if tt <  0:
                sum += 1
                cert_list.append(cert)
        totalpage = int(sum/(per_page*1.00))
        curpage = query_args.get("curpage")
        certs_dict ={"certs": cert_list[(curpage-1)*per_page:curpage*per_page - 1] ,"totalpage" : totalpage}
        for c in certs_dict["certs"]:
            c["validity_china"]["end_time"]=datetime.strptime(c["validity_china"]["end_time"], "%Y%m%d%H%M%S")
            c["validity_china"]["begin_time"]=datetime.strptime(c["validity_china"]["begin_time"], "%Y%m%d%H%M%S")
            c['c_type'] = 'expired'
    elif query_args.get('type')=='transfered':
        query.update({'t_id':{"$exists":True}})
        totalpage = int(math.ceil(monitor_db.cert_detail.find(query).count(True)/(per_page*1.00)))
        cert_list=[]
        for u in make_cert_validity(list(monitor_db.cert_detail.find(query).sort('_id', pymongo.DESCENDING).skip(query_args.get("curpage")*per_page).limit(per_page))):
            u['c_type'] = 'transfered'
            cert_list.append(u)
        certs_dict={"certs":cert_list,"totalpage" : totalpage}
        for c in certs_dict["certs"]:
            c["validity_china"]["end_time"]=datetime.strptime(c["validity_china"]["end_time"], "%Y%m%d%H%M%S")
            c["validity_china"]["begin_time"]=datetime.strptime(c["validity_china"]["begin_time"], "%Y%m%d%H%M%S")
    return certs_dict




def find_cert_query(query_args):
    '''
    证书查询任务
    '''
    per_page = 30
    certs_dict = {"certs":[],"totalpage":0}
    query = {}
    if query_args['cert_query_id']:
        query['_id'] = ObjectId(query_args['cert_query_id'])
    if query_args.get('username'):
        query['username'] = query_args['username']
    if query_args.get('channel'):
        query['channel'] = query_args['channel']
    if query_args.get('cert_name'):
        query['cert_name'] = query_args['cert_name']
    if query_args.get("username") == '' and query_args.get("cert_name") == '' and query_args.get("_id") == '' and query_args.get("channel") == '':
        pass
    else:
        totalpage = int(math.ceil(monitor_db.cert_detail.find(query).limit(600).count(True)/(per_page*1.00)))
        certs_dict ={"cert_query": [u for u in monitor_db.cert_query_info.find(query).sort('_id', pymongo.DESCENDING).skip(query_args.get("curpage")*per_page).limit(per_page)] ,"totalpage" : totalpage}
    return certs_dict


def make_cert_validity(certs):
    '''
    转换证书时间　－> China
    '''
    for cert in certs:
        cert['validity_china'] = make_validity_to_China(cert['validity'])

    return certs


def cert_all_count():
    '''
    证书总数
    '''
    return monitor_db.cert_detail.find().count()


def find_urls_custom(query_args):
    per_page = 30
    urls_dict = {"urls":[],"totalpage":0}
    query_type = query_args.get('query_type')
    if query_type == 'normal_query':
        dt = datetime.strptime(query_args.get("date"), "%m/%d/%Y")
        query = {'created_time':{"$gte":dt, "$lt":(dt + timedelta(days=1))}}
    else:
        start_datetime = datetime.strptime(query_args.get("start_datetime"), "%Y-%m-%d %H")
        end_datetime = datetime.strptime(query_args.get("end_datetime"), "%Y-%m-%d %H")
        query = {'created_time':{"$gte":start_datetime, "$lt": end_datetime}}
    if query_args.get("username"):
        append_userfield(query_args.get("username"),query)
    if query_args.get("channel_name"):
        query['channel_name'] = query_args.get('channel_name')
    url_str = query_args.get("url")
    if  url_str:
        if (url_str.find('*')>0):
            url_str=url_str.replace('*','\*')
        query['url'] = re.compile("^%s.*" %url_str)

    if query_args.get("status") != "ALL":
        query['status'] = query_args.get("status")
    if query_args.get("status") == "ALL" and query_args.get("username") == '' and query_args.get("url") == '' and query_args.get('channel_name') == '':
        pass
    else:
        logger.debug("query:%s" % str(query))
        totalpage = int(math.ceil(q_db.url_autodesk.find(query).limit(600).count(True)/(per_page*1.00)))
        urls_dict ={"urls": load_url([u for u in q_db.url_autodesk.find(query).sort('created_time', pymongo.DESCENDING).skip(query_args.get("curpage")*per_page).limit(per_page)]) ,"totalpage" : totalpage}
    return urls_dict

def find_urls_for_csv(args):
    '''
    查询输出csv的url
    '''
    query = {}
    username = args.get('username')
    if username:
        query['username'] = username
    url = args.get('url')
    if url:
        query['url'] = url
    channel_name = args.get('channel_name')
    if channel_name:
        query['channel_name'] = channel_name
    status = args.get('status')
    if status and status != 'ALL':
        query['status'] = status

    start_datetime = args.get('start_datetime')
    end_datetime = args.get('end_datetime')
    if start_datetime and end_datetime:
        start_datetime = datetime.strptime(start_datetime, "%Y-%m-%d %H")
        end_datetime = datetime.strptime(end_datetime, "%Y-%m-%d %H")
        query['created_time'] = {'$gte':start_datetime, '$lt': end_datetime }

    logger.debug("find_urls_for_csv query:%s" % str(query))

    return q_db.url.find(query).sort('created_time', pymongo.DESCENDING)
    

def append_userfield(username,query):
    from cache import rediscache
    if rediscache.isFunctionUser(username):
        query['username']=username
    else:
        query['parent'] = username

def load_url(urls):
    for url in urls:
        if url.get("finish_time"):
            url["hs"] = str(int(time.mktime(url.get("finish_time").timetuple()) - time.mktime(url.get("created_time").timetuple())))+"秒"
            url["finish_time"] = url.get("finish_time").strftime('%Y-%m-%d %H:%M:%S')
            url['remain_time'] = 0
        else:
            url["hs"] = '未知'
            url["finish_time"] = '未知'
            if url.get('executed_end_time'):
                url['remain_time'] = str(int(time.mktime(url.get('executed_end_time').timetuple()) -
                                             time.mktime(datetime.now().timetuple()))) + '秒'
        url["created_time"] = url.get("created_time").strftime('%Y-%m-%d %H:%M:%S')
        if url.get("retry_time"):
            url["retry_time"] = url.get("retry_time").strftime('%Y-%m-%d %H:%M:%S')
        if url.get('executed_end_time'):
            url['executed_end_time'] = url.get('executed_end_time').strftime('%Y-%m-%d %H:%M:%S')

    return urls

def load_cert_task(tasks):
    for t in tasks:
        #下发时间
        if t.get("finish_time"):
            t["hs"] = str(int(time.mktime(t.get("finish_time").timetuple()) - time.mktime(t.get("created_time").timetuple())))+"秒"
            t["finish_time"] = t.get("finish_time").strftime('%Y-%m-%d %H:%M:%S')
        else:
            t["hs"] = '未知'
            t["finish_time"] = '未知'
        #最终结束时间
        if t.get('hpc_finish_time'):
            t["hpc_hs"] = str(int(time.mktime(t.get("hpc_finish_time").timetuple()) - time.mktime(t.get("created_time").timetuple())))+"秒"
            t["hpc_finish_time"] = t.get("hpc_finish_time").strftime('%Y-%m-%d %H:%M:%S')
        else:
            t["hpc_hs"] = '未知'
            t["hpc_finish_time"] = '未知'

        t["created_time"] = t.get("created_time").strftime('%Y-%m-%d %H:%M:%S')
    return tasks

def get_expired_cert_res(cert_id):
    '''
    根据cert_id 查询结果
    '''
    cert_detail_dic = monitor_db.cert_detail.find_one({'_id': ObjectId(cert_id)})
    cert_dns=cert_detail_dic.get("DNS","")
    cert_subject=json.dumps(cert_detail_dic.get("subject",""))
    cert_issuer=json.dumps(cert_detail_dic.get("issuer",""))
    cert_type=cert_detail_dic.get("cert_type",'crt')
    return cert_dns,cert_subject,cert_issuer,cert_type


def get_devs_cert_task(dev_id):
    '''
    根据cert task的dev_id 查询下发结果
    '''
    all_devs = monitor_db.cert_trans_dev.find_one({'_id': ObjectId(dev_id)})
    success_devs = []
    success_strs = []
    failed_devs = []
    for dev in list(all_devs['devices'].values()):
        if dev['code'] != 503:
            res_code = dev['code']
        else:
            res_code = dev['r_code']
        if res_code == 200:
            success_strs.append('%s_%s'%(dev['name'],dev['host']))
            if len(success_strs) >= 4:
                success_devs.append(' '.join(success_strs))
                success_strs = []
        else:
            failed_devs.append(dev)

    if success_strs:
        success_devs.append(' '.join(success_strs))

    return success_devs, failed_devs, all_devs['unprocess'], len(all_devs['devices'])


def get_devs_cert_task_res(task_id):
    '''
    get cert dev res
    '''
    is_cache = True
    res_cache_key = '%s_res'%(task_id)
    unprocess_cache_key = '%s_res_unprocess'%(task_id)
    all_res = CERT_TRANS_CACHE.hgetall(res_cache_key)
    success_cache_key = '%s_res_success'%(task_id)
    success_num = CERT_TRANS_CACHE.scard(success_cache_key)
    if success_num:
        unprocess = len(all_res) - int(success_num)
    else:
        unprocess = len(all_res)

    if not all_res:
        info = monitor_db.cert_trans_result.find_one({'_id':ObjectId(task_id)})
        all_res = info['devices']
        unprocess = info['unprocess']
        is_cache = False

    success_devs = []
    success_strs = []
    failed_devs = []
    for v in list(all_res.values()):
        if is_cache:
            v = json.loads(v)
        if v['result_status'] == 200:
            success_strs.append('%s_%s'%(v['name'],v['host']))
            if len(success_strs) >= 4:
                success_devs.append(' '.join(success_strs))
                success_strs = []
        else:
            failed_devs.append(v)

    if success_strs:
        success_devs.append(' '.join(success_strs))

    return success_devs, failed_devs, unprocess, len(all_res)

def get_devs_cert_query_task(dev_id):
    '''
    根据cert task的dev_id 查询下发结果
    '''
    all_devs = monitor_db.cert_query_dev.find_one({'_id': ObjectId(dev_id)})
    success_devs = []
    success_strs = []
    failed_devs = []
    for dev in list(all_devs['query_dev_ip'].values()):
        if dev['code'] != 503:
            res_code = dev['code']
        else:
            res_code = dev['r_code']
        if res_code == 200:
            success_strs.append('%s_%s'%(dev['name'],dev['host']))
            if len(success_strs) >= 4:
                success_devs.append( ' '.join(success_strs))
                success_strs = []
        else:
            failed_devs.append(dev)

    if success_strs:
        success_devs.append(' '.join(success_strs))

    return success_devs, failed_devs, all_devs['unprocess'], len(all_devs['query_dev_ip'])

def get_devs_cert_query_task_res(task_id):
    '''
    get cert query dev res
    '''
    is_cache = True
    res_cache_key = '%s_res'%(task_id)
    unprocess_cache_key = '%s_res_unprocess'%(task_id)
    all_res = CERT_QUERY_CACHE.hgetall(res_cache_key)
    success_cache_key = '%s_res_success'%(task_id)
    success_num = CERT_QUERY_CACHE.scard(success_cache_key)
    if success_num:
        unprocess = len(all_res) - int(success_num)
    else:
        unprocess = len(all_res)

    if not all_res:
        info = monitor_db.cert_query_result.find_one({'_id':ObjectId(task_id)})
        logger.debug("info is %s"%info)
        all_res = info['devices']
        unprocess = info['unprocess']
        is_cache = False

    success_devs = []
    failed_devs = []
    for v in list(all_res.values()):
        if is_cache:
            v = json.loads(v)
        if v['result_status'] == 200:
            success_devs.append(v)
        else:
            failed_devs.append(v)
    if success_devs:
        for dev in success_devs:
            cert_info = dev.get('result').get('cert_info')
            key_info = dev.get('result').get('key_info')
            if cert_info:
                cert_created_time_str = cert_info.split('\n')[1]
                cert_timeArray = time.strptime(cert_created_time_str, "%Y-%m-%d %H:%M:%S")
                cert_otherStyleTime = time.strftime("%Y/%m/%d %H:%M", cert_timeArray)
                dev['cert_created_time']= str(cert_otherStyleTime)
                logger.debug("cert_otherStyleTime is %s" % cert_otherStyleTime)
            if key_info:
                key_created_time_str = key_info.split('\n')[1]
                key_timeArray = time.strptime(key_created_time_str, "%Y-%m-%d %H:%M:%S")
                key_otherStyleTime = time.strftime("%Y/%m/%d %H:%M", key_timeArray)
                dev['key_created_time']= str(key_otherStyleTime)
                logger.debug("key_otherStyleTime is %s" % key_otherStyleTime)
    logger.debug("success_devs:%s" % success_devs)
    logger.debug("failed_devs:%s" % failed_devs)

    return success_devs, failed_devs, unprocess, len(all_res)

def get_devs_cert_query_task_detail(task_id):
    '''
    get cert query dev detail
    '''
    is_cache = True
    res_cache_key = '%s_res'%(task_id)
    unprocess_cache_key = '%s_res_unprocess'%(task_id)
    all_res = CERT_TRANS_CACHE.hgetall(res_cache_key)
    success_cache_key = '%s_res_success'%(task_id)
    success_num = CERT_TRANS_CACHE.scard(success_cache_key)
    if success_num:
        unprocess = len(all_res) - int(success_num)
    else:
        unprocess = len(all_res)

    if not all_res:
        info = monitor_db.cert_query_result.find_one({'_id':ObjectId(task_id)})
        all_res = info['devices']
        unprocess = info['unprocess']
        is_cache = False

    success_devs = []
    #success_strs = []
    failed_devs = []
    #for v in all_res.values():
    for k,v in list(all_res.items()):
        if is_cache:
            v = json.loads(v)
        if v['result_status'] == 200:
            v['result']['device']=k
            #success_devs.append(str(v['result']))
            success_devs.append(json.dumps(v['result']))
            #success_devs.append(v)
        else:
            failed_devs.append(v)
    logger.debug("success_devs:%s" % success_devs)
    logger.debug("failed_devs:%s" % failed_devs)

    return success_devs, failed_devs, unprocess, len(all_res)

def get_devs_transfer_cert_task(dev_id):
    '''
    根据transfer_cert_task的dev_id 查询下发结果
    '''
    all_devs = monitor_db.transfer_cert_dev.find_one({'_id': ObjectId(dev_id)})
    success_devs = []
    success_strs = []
    failed_devs = []
    for dev in list(all_devs['devices'].values()):
        if dev['code'] != 503:
            res_code = dev['code']
        else:
            res_code = dev['r_code']
        if res_code == 200:
            success_strs.append('%s_%s'%(dev['name'],dev['host']))
            if len(success_strs) >= 4:
                success_devs.append( ' '.join(success_strs))
                success_strs = []
        else:
            failed_devs.append(dev)

    if success_strs:
        success_devs.append(' '.join(success_strs))

    return success_devs, failed_devs, all_devs['unprocess'], len(all_devs['devices'])

def get_devs_transfer_cert_task_res(task_id):

    #get transfer cert  dev res

    is_cache = True
    res_cache_key = '%s_res'%(task_id)
    unprocess_cache_key = '%s_res_unprocess'%(task_id)
    all_res = TRANSFER_CERT_CACHE.hgetall(res_cache_key)
    success_cache_key = '%s_res_success'%(task_id)
    success_num = TRANSFER_CERT_CACHE.scard(success_cache_key)
    if success_num:
        unprocess = len(all_res) - int(success_num)
    else:
        unprocess = len(all_res)

    if not all_res:
        info = monitor_db.transfer_cert_result.find_one({'_id':ObjectId(task_id)})
        logger.debug("info is %s"%info)
        all_res = info['devices']
        dic_res = {}
        for dd in list(all_res.values()):
            dic_res[dd['host']] = dd['name']
        unprocess = info['unprocess']
        is_cache = False

    success_strs = []
    success_devs = []
    failed_certs = {}
    all_devs = []
    res = {}
    task_info = monitor_db.transfer_cert_tasks.find_one({'_id':ObjectId(task_id)})
    save_name_list =  task_info['save_name'].split(',')
    for save_name in save_name_list:
        res[save_name] = {}
        for v in list(all_res.values()):
            if is_cache:
                v = json.loads(v)
            #res[save_name] = {}
            host = v['host']
            if v['result_status'] != 200:
                res[save_name][host] = 0
                    #failed_devs.append(v)
            else:
                res[save_name][host] = v['result'][save_name.replace('.','%')]
    #result = {}
    logger.debug("res is:%s" % res)
    for k,v in list(res.items()):
        num = 0
        for m,code in list(v.items()):
            if code == 200:
                num += 1
        if num == len(v):
            success_strs.append(k)
        else:
            failed_certs[k]=v
    logger.debug("success_strs is %s"%success_strs)
    logger.debug("failed_certs is %s"%failed_certs)
    all_certs = ""
    for cert in list(res.keys()):
        all_certs += cert+","+" "
    return success_strs,failed_certs, unprocess, len(all_res), dic_res, all_certs[:-1]

def get_devs_transfer_cert_task_detail(task_id):
    '''
    get transfer cert  dev detail
    '''
    is_cache = True
    res_cache_key = '%s_res'%(task_id)
    unprocess_cache_key = '%s_res_unprocess'%(task_id)
    all_res = TRANSFER_CERT_CACHE.hgetall(res_cache_key)
    success_cache_key = '%s_res_success'%(task_id)
    success_num = TRANSFER_CERT_CACHE.scard(success_cache_key)
    if success_num:
        unprocess = len(all_res) - int(success_num)
    else:
        unprocess = len(all_res)
    if not all_res:
        info = monitor_db.transfer_cert_result.find_one({'_id':ObjectId(task_id)})
        all_res = info['devices']
        unprocess = info['unprocess']
        is_cache = False
    success_devs = []
    #success_strs = []
    failed_devs = []
    #for v in all_res.values():
    for k,v in list(all_res.items()):
        if is_cache:
            v = json.loads(v)
        if v['result_status'] == 200:
            v['result']['device']=k
            #success_devs.append(str(v['result']))
            success_devs.append(json.dumps(v['result']))
            #success_devs.append(v)
        else:
            failed_devs.append(v)
    logger.debug("success_devs:%s" % success_devs)
    logger.debug("failed_devs:%s" % failed_devs)

    return success_devs, failed_devs, unprocess, len(all_res)


def get_devs_by_id(dev_id):

    return q_db.device.find_one({'_id': ObjectId(dev_id)})

#hpf
def get_retry_re_id(u_id):

    retry_list=db.retry_re.find({"uid":ObjectId(u_id)})
    retry_list=list(retry_list)
    return retry_list
#hpf--------------------
'''
def retry_user(query_args):
    query_type = query_args.get('query_type')
    if query_type == 'normal_query':
        dt = datetime.strptime(query_args.get("date"), "%m/%d/%Y")
        query = {'created_time':{"$gte":dt, "$lt":(dt + timedelta(days=1))}}
    else:
        start_datetime = datetime.strptime(query_args.get("start_datetime"), "%Y-%m-%d %H")
        end_datetime = datetime.strptime(query_args.get("end_datetime"), "%Y-%m-%d %H")
        query = {'created_time':{"$gte":start_datetime, "$lt": end_datetime}}
    if query_args.get("username"):
        append_userfield(query_args.get("username"),query)
    #query['status']={"$ne":"FINISHED"}
    query['status']="FAILED"
    dev_list=db.url.aggregate([{'$match':query},{'$group' : {'_id' : "$dev_id"}}])
    dev_list=list(dev_list)
    for dev_id in dev_list:
        dev_id=dev_id['_id']
        query['dev_id']=dev_id
        urls_list=db.url.find(query)

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
'''
def get_url_by_id(id):
    """

    :param id: the id of url
    :return:
    """
    result = {}
    try:

        result = q_db.url.find_one({'_id': ObjectId(id)})
    except Exception:
        logger.debug('find url error:%s, id:%s' % (e, id))
    if result:
        dev_id = str(result.get('dev_id'))
        return dev_id
    return None


def get_devs_custom_by_id(dev_id):
    """

    :param dev_id:
    :return:
    """
    return q_db.device_autodesk.find_one({'_id': ObjectId(dev_id)})

def get_url_by_url(url_id):
    """

    Parameters
    ----------
    url_id   url  collection 中  的   _id

    Returns   返回url对应的信息
    -------

    """
    return q_db.url.find_one({'_id':url_id})


def parse_dev_custom_result(result):
    """

    :param result: the content of device custom
    :return: the all number of device, the number of 204, the number of success, the number of failed, the number of error
    """
    if not result:
        return 0, 0, 0, 0, 0
    else:
        num_all = 0
        num_204 = 0
        num_success = 0
        num_failed = 0
        num_error = 0
        for dev in result:
            if dev.get('code') == 204:
                num_all += 1
                num_204 += 1
            elif dev.get('http_refresh_result') == 'success':
                num_all += 1
                num_success += 1
            elif dev.get('http_refresh_result') == 'failed':
                num_all += 1
                num_failed += 1
            else:
                num_all += 1
                num_error += 1
        return num_all, num_204, num_success, num_failed, num_error


def get_refresh_result_by_sessinId(session_id):
    """
    根据session_id，返回要查询的信息
    Parameters
    ----------
    session_id   refresh_result collection  中的session_id

    Returns   返回refresh_result中的信息
    -------

    """
    str_num = ''
    try:
        num_str =config.get('refresh_result', 'num')
        str_num = get_mongo_str(str(session_id), num_str)
    except Exception:
        logger.debug('get refresh_result get number of refresh_result error:%s' % traceback.format_exc())

    res = monitor_db['refresh_result' + str_num].find({'session_id': session_id})
    if not res:
        return []
    else:
        # return assembel_refresh_result(res)
        return res


# def assembel_refresh_result(refresh_result):
#     """
#     accoreding the result of refresh_result, according name, find device_app,get host,status,firstlayer,type
#     :param refresh_result:
#     :return:
#     """
#     result = []
#     for res in refresh_result:
#         name = res.get('name', None)
#         logger.debug("name:%s" % name)
#         res['host'], res['status'], res['firstLayer'], res['type'] = get_host_info(name)
#         logger.debug('host:%s, status:%s, firstLayer:%s, type:%s' % (res['host'], res['status'], res['firstLayer'], res['type']))
#         result.append(res)
#     logger.debug(refresh_result)
#     return result


def get_host_info(host_name):
    """
    according host name, query host ip
    :param host_name: the name of remote device
    :return: the ip of remote device
    """
    try:
        host_info = q_db.device_app.find_one({'name': host_name})
    except Exception:
        logger.debug("receiver_branch get_host_ip query device_app error:%s" % e)
        return None, None, None, None
    if not host_info:
        return None, None, None, None

    # the ip of host_name(device)
    ip_t = host_info.get('host', None)

    # the status of (device) host_name
    status_t = host_info.get('status', None)

    # the layer of device(host_name)
    firstLayer_t = host_info.get('firstlayer', None)

    # the type of device(host_name)
    type_t = host_info.get('type', None)
    return ip_t, status_t, firstLayer_t, type_t

def get_no_send_number(devs):
    """
    parameter: devs  设备的信息
    return： 返回设备中 状态码为code = 204 或着 code = 0的设备的数量
    """
    count = 0
    for de in devs:
        if de['code'] == 204:
            count +=1
    return count

def get_retryDevice_by_id(dev_id):
    return q_db.retry_device.find_one({'_id': ObjectId(dev_id)})


def get_retry_dev_branch_by_id(retry_branch_id):
    """
    according retry_branch_id, get data from retry_device_branch
    :param retry_branch_id: the _id of retry_device_branch collection
    :return:
    """
    devices = []
    try:
        devices_result = q_db.retry_device_branch.find_one({"_id": ObjectId(retry_branch_id)})
    except Exception:
        logger.debug("get_retry_dev_branch_by_id query mongo error:%s" % e)
        return devices
    if not devices_result:
        return devices
    else:
        dev_temp = devices_result.get('devices', '')
        if dev_temp:
            return dev_temp
        else:
            return devices

def get_retry_dev_bran_by_id(retry_branch_id):
    """
    according retry_branch_id, get data from retry_device_branch
    :param retry_branch_id: the _id of retry_device_branch collection
    :return:
    """
    devices = []
    rest = {}
    try:
        devices_result = monitor_db.cert_subcenter_task.find_one({"_id": ObjectId(retry_branch_id)})
    except Exception:
        logger.debug("get_retry_dev_branch_by_id query mongo error:%s" % e)
        return devices
    if not devices_result:
        return devices
    else:
        edge_sub_dic = devices_result.get('ralation_faildev_subcenter', '')
        for edge_host,v in list(edge_sub_dic.items()):
            rest[str(edge_host.replace('#','.'))]= []
            for subcenter_host in v:
                res = monitor_db.cert_subcenter_result.find_one({"edge_host":edge_host.replace('#','.'),"subcenter_host":subcenter_host,"t_id":retry_branch_id})
                code = res.get('edge_result','')
                created_time = res.get('created_time')
                edge_return_time = res.get('edge_return_time','')
                ack_content = res.get('ack_content','')
                #create_time_timestamp = time.mktime(created_time.timetuple())
                if edge_return_time:
                    #edge_return_time_timestamp = time.mktime(edge_return_time.timetuple())
                    consume_time = (edge_return_time - created_time).total_seconds()
                    result={'edge_host':str(edge_host.replace('#','.')),'code':code,'subcenter_host':str(subcenter_host),'consume_time':consume_time,'ack_content':ack_content}
                else:
                    result={'edge_host':str(edge_host.replace('#','.')),'code':0,'subcenter_host':str(subcenter_host),'consume_time':'--','ack_content':ack_content}
                rest[str(edge_host.replace('#','.'))].append(result)
        logger.debug("rest is %s" %rest )
        return rest



def statistic_banch_code(devs):
    """
    statistic  code number,  have  branch_code, not have branch_code
    :param devs:
    :return: the number of all device,  the number of device not have branch_code
    """
    not_have_code_number = 0
    all_dev = len(devs)
    logger.debug("modes statistic_branch devs:%s" % devs)
    if devs:
        for dev in devs:
            if dev.get('branch_code', 0) == 0:
                not_have_code_number += 1
                dev['branch_code'] = 0
    return all_dev, not_have_code_number

def get_user(user_info):
    if user_info.get("account") in ['canquan.wen@chinacache.com', 'peng.zhou@chinacache.com', 'li.chang@chinacache.com'] :
        user = User(user_info.get('account'),"admin")
    else:
        user = User(user_info.get('account'),"guest")
        db_user = q_db.admin_user.find_one({"_id":user_info.get("account")})
        if db_user :
            user.role = db_user.get("role")
    return user

def get_user_list():
    return [user for user in q_db.admin_user.find()]

def add_user(user):
    db.admin_user.save({"_id":user.account,"role":user.role})

def del_user(account):
    db.admin_user.remove({"_id":account})

def get_rewrite_list(args):
    per_page = 30
    CHANNEL_NAME = args.get("CHANNEL_NAME") if args.get("CHANNEL_NAME") else "*"
    keys = REWRITE_CACHE.keys(CHANNEL_NAME)
    rewrite_list = []
    for key in keys:
        for rewrite_addr in REWRITE_CACHE.get(key).split(","):
            if args.get("REWRITE_NAME") in rewrite_addr:
                rewrite_list.append({'CHANNEL_NAME':key, 'REWRITE_NAME':rewrite_addr})
    args["totalpage"] = int(math.ceil(len(rewrite_list)/(per_page)*1.0))
    return rewrite_list[per_page*args.get("curpage"):per_page*(args.get("curpage")+1)]


def get_rewrite_list_new(results, args):
    """
    handle the content of every page
    :param results:  the content of username and channel list
    :param args: the info of every page
    :return:  the content of current page
    """
    # each page shows the number of a domain relation
    per_page = 15
    args["totalpage"] = int(math.ceil(len(results)/(per_page*1.0)))

    return results[per_page*args.get("curpage"):per_page*(args.get("curpage") + 1)]


def add_rewrite_data(CHANNEL_NAME,REWRITE_NAME):
    try:
        if REWRITE_CACHE.get(CHANNEL_NAME) :
            REWRITE_NAME = REWRITE_NAME + "," + REWRITE_CACHE.get(CHANNEL_NAME)
        REWRITE_CACHE.set(CHANNEL_NAME, REWRITE_NAME)
        new_rewrite_data = {"CHANNEL":CHANNEL_NAME,"REWRITE":REWRITE_NAME.split(",")[0]}
        db.rewrite.insert(new_rewrite_data)
        logger.debug("add rewrite:%s" % (str(new_rewrite_data)))
    except:
        return 'add rewrite feiled!'
    return "successful"

def del_rewrite_data(CHANNEL_NAME,REWRITE_NAME):
    rewrite_list = REWRITE_CACHE.get(CHANNEL_NAME).split(",")
    rewrite_list.remove(REWRITE_NAME)
    try:
        if rewrite_list:
            REWRITE_CACHE.set(CHANNEL_NAME, str(",".join(rewrite_list)))
        else:
            REWRITE_CACHE.delete(CHANNEL_NAME)
        db.rewrite.remove({"CHANNEL":CHANNEL_NAME,"REWRITE":REWRITE_NAME})
        logger.debug("del rewrite:[%s:%s]" % (CHANNEL_NAME,REWRITE_NAME))
    except Exception:
        logger.debug("delete rewrite feiled %s" % str(e) )
        return 'delete rewrite feiled!'
    return "successful"

def get_regex_list():
    config_list = []
    keys = list(REGEXCONFIG.keys())
    for key in keys:
        configs=json.loads(REGEXCONFIG.get(key))
        for regex_id in configs :
            config_list.append(
                {
                    'id':regex_id,
                    'username':configs.get(regex_id).get('username',''),
                    'isdir':configs.get(regex_id).get('isdir',''),
                    'regex':configs.get(regex_id).get('regex',''),
                    'append':configs.get(regex_id).get('append',''),
                    'ignore':configs.get(regex_id).get('ignore',''),
                }
            )
    return config_list

def get_regex_list_h():
    config_list = []
    keys = list(REGEXCONFIG.keys())
    for key in keys:
        if 'regex_' not in key :
            continue
        regexDic=json.loads(REGEXCONFIG.get(key))
        for id in list(regexDic.keys()) :
            regex_dic=regexDic.get(id)
            config_list.append(
                {
                    'id': id,
                    "username": regex_dic.get('username',''),
                    "domain": regex_dic.get('domain',''),
                    "isdir": regex_dic.get('isdir',''),
                    "regex": regex_dic.get('regex',''),
                    "method": regex_dic.get('method',''),
                    "act": regex_dic.get('act',''),
                    "end": regex_dic.get('end',''),
                    "append": regex_dic.get('append',''),
                    "ignore": regex_dic.get('ignore','')
                }
            )

    return config_list

def add_regex_data_h(username,domain,isdir, regex,method,act, end,append,ignore,user_email=''):
    try:

        updateRegexRedis_h(username,domain,isdir, regex,method,act, end,append,ignore)
        md5 = hashlib.md5()
        md5.update(username + domain + str(isdir) + regex + method + act + end + append + ignore)
        regex_id  = md5.hexdigest()
        regexConfig = {
            "_id": regex_id,
            "username": username,
            "domain": domain,
            "isdir": isdir,
            "regex": regex,
            "method": method,
            "act": act,
            "end": end,
            "append": append,
            "ignore": ignore
        }
        operation_record_into_mongo(user_email, 'regular_expression_configuration', 'insert', regexConfig)
        db.regex_config.insert(regexConfig)
        logger.debug("add regex_config success:%s" % (str(regexConfig)))
    except:
        logger.debug("add regex_config failure" )

def del_regex_data_h(username,regexConfigId, user_email=''):
    try:
        delRegexRedis_h(username,regexConfigId)
        regexConfig = q_db.regex_config.find_one({"_id":regexConfigId})
        operation_record_into_mongo(user_email, 'regular_expression_configuration', 'delete', regexConfig)
        db.regex_config.remove(regexConfig)
        logger.debug("del regexconfig:%s" % (str(regexConfig)))
    except Exception:
        logger.debug("delete regexconfig feiled!:%s" % str(e))

def delRegexRedis_h(username,regexId):
    try:
        username='regex_'+username
        userRegex = REGEXCONFIG.get(username)
        userRegex=json.loads(userRegex)
        del userRegex[regexId]
        REGEXCONFIG.set(username,json.dumps(userRegex))
    except Exception:
        logger.info("regex del exception : %s" % str(e))

def updateRegexRedis_h(username,domain,isdir, regex,method,act, end,append,ignore):
    try:

        regexConfig = {
            "username": username,
            "domain": domain,
            "isdir": isdir,
            "regex": regex,
            "method": method,
            "act": act,
            "end": end,
            "append": append,
            "ignore": ignore
        }

        md5 = hashlib.md5()
        md5.update(username+domain+str(isdir)+regex+method+act+end+append+ignore)
        regex_id  = md5.hexdigest()
        username = 'regex_' + username
        user_regex = REGEXCONFIG.get(username)
        if user_regex:
            user_regex=json.loads(user_regex)
            user_regex[regex_id] = regexConfig
        else :
            user_regex = {regex_id:regexConfig}
        REGEXCONFIG.set(username,json.dumps(user_regex))
    except Exception:
        logger.info("regex update exception : %s" % str(e))


def add_regex_data(username,isdir,regex,append,ignore, user_email=''):
    try:
        updateRegexRedis(username,isdir,regex,append,ignore)
        md5 = hashlib.md5()
        md5.update(username+str(isdir)+regex+append+ignore)
        regex_id  = md5.hexdigest()
        regexConfig = {
            "_id" :regex_id,
            "username":username,
            "isdir":isdir,
            "regex":regex,
            "append":append,
            "ignore":ignore
        }
        operation_record_into_mongo(user_email, 'regular_expression_configuration', 'insert', regexConfig)
        db.regex_config.insert(regexConfig)
        logger.debug("add regex_config success:%s" % (str(regexConfig)))
    except:
        logger.debug("add regex_config failure" )

def del_regex_data(username,regexConfigId, user_email=''):
    try:
        delRegexRedis(username,regexConfigId)
        regexConfig = q_db.regex_config.find_one({"_id":regexConfigId})
        operation_record_into_mongo(user_email, 'regular_expression_configuration', 'delete', regexConfig)
        db.regex_config.remove(regexConfig)
        logger.debug("del regexconfig:%s" % (str(regexConfig)))
    except Exception:
        logger.debug("delete regexconfig feiled!:%s" % str(e))


def updateRegexRedis(username,isdir,regex,append,ignore):
    try:
        regexConfig = {
            "username":username,
            "isdir":isdir,
            "regex":regex,
            "append":append,
            "ignore":ignore
        }
        md5 = hashlib.md5()
        md5.update(username+str(isdir)+regex+append+ignore)
        regex_id  = md5.hexdigest()
        user_regex = REGEXCONFIG.get(username)
        if user_regex:
            user_regex=json.loads(user_regex)
            user_regex[regex_id] = regexConfig
        else :
            user_regex = {regex_id:regexConfig}
        REGEXCONFIG.set(username,json.dumps(user_regex))
    except Exception:
        logger.info("regex update exception : %s" % str(e))

def delRegexRedis(username,regexId):
    try:
        userRegex = REGEXCONFIG.get(username)
        userRegex=json.loads(userRegex)
        del userRegex[regexId]
        REGEXCONFIG.set(username,json.dumps(userRegex))
    except Exception:
        logger.info("regex del exception : %s" % str(e))

def get_channelignore_list():
    return [channel for channel in q_db.channel_ignore.find()]

def get_domain_ignore_list():
    return [channel for channel in q_db.domain_ignore.find()]

def add_channelignore_data(CHANNEL_NAME):
    try:
        CHANNEL_CODE = rcmsapi.getChannelCode(CHANNEL_NAME)[0]['channelCode']
        db.channel_ignore.insert({"CHANNEL_NAME":CHANNEL_NAME, "CHANNEL_CODE":CHANNEL_CODE})
        logger.debug("add channel_ignore :%s" % (str({"CHANNEL_NAME":CHANNEL_NAME, "CHANNEL_CODE":CHANNEL_CODE})))
    except:
        logger.debug("add channel_ignore failure :%s" % (str({"CHANNEL_NAME":CHANNEL_NAME, "CHANNEL_CODE":CHANNEL_CODE})))
def add_domain_lignore_data(CHANNEL_NAME,createUser):
    try:
        createtime = datetime.now()
        CHANNEL_CODE = rcmsapi.getChannelCode(CHANNEL_NAME)[0]['channelCode']
        db.domain_ignore.insert({"CHANNEL_NAME":CHANNEL_NAME, "CHANNEL_CODE":CHANNEL_CODE,"creattime":createtime,'createUser':createUser})

        domain_all = DOMAIN_INGNOE.get(DOMAIN_KEY)
        if domain_all:
            domain_dict = json.loads(domain_all)
            domain_dict[CHANNEL_CODE] = CHANNEL_NAME
        else:
            domain_dict = {CHANNEL_CODE: CHANNEL_NAME}

        DOMAIN_INGNOE.set(DOMAIN_KEY,json.dumps(domain_dict))
        logger.debug("add channel_ignore :%s" % (str({"CHANNEL_NAME":CHANNEL_NAME, "CHANNEL_CODE":CHANNEL_CODE})))
    except:
        logger.debug("add channel_ignore failure :%s" % (str({"CHANNEL_NAME":CHANNEL_NAME, "CHANNEL_CODE":CHANNEL_CODE})))

def del_domain_ignore_data(CHANNEL_CODE):
    try:
        db.domain_ignore.remove({"CHANNEL_CODE":CHANNEL_CODE})
        domain_ignore = DOMAIN_INGNOE.get(DOMAIN_KEY)
        domain_ignore = json.loads(domain_ignore)
        del domain_ignore[CHANNEL_CODE]
        DOMAIN_INGNOE.set(DOMAIN_KEY, json.dumps(domain_ignore))

        logger.debug("del channel_ignore:%s" % (str(CHANNEL_CODE)))
    except:
        logger.debug("del channel_ignore failure:%s" % (str(CHANNEL_CODE)))

def del_channelignore_data(CHANNEL_CODE):
    try:
        db.channel_ignore.remove({"CHANNEL_CODE":CHANNEL_CODE})
        logger.debug("del channel_ignore:%s" % (str(CHANNEL_CODE)))
    except:
        logger.debug("del channel_ignore failure:%s" % (str(CHANNEL_CODE)))


def get_dirandurl_list():
    return [channel for channel in q_db.dirandurl.find()]
def add_dirandurl_data(CHANNEL_NAME,createUser):
    try:
        createtime = datetime.now()
        CHANNEL_CODE = rcmsapi.getChannelCode(CHANNEL_NAME)[0]['channelCode']
        db.dirandurl.insert({"CHANNEL_NAME":CHANNEL_NAME, "CHANNEL_CODE":CHANNEL_CODE,"creattime":createtime,'createUser':createUser})

        domain_all = DIRANDURL.get(DIRANDURL_KEY)
        if domain_all:
            domain_dict = json.loads(domain_all)
            domain_dict[CHANNEL_CODE] = CHANNEL_NAME
        else:
            domain_dict = {CHANNEL_CODE: CHANNEL_NAME}

        DIRANDURL.set(DIRANDURL_KEY,json.dumps(domain_dict))
        logger.debug("add dir and url all :%s" % (str({"CHANNEL_NAME":CHANNEL_NAME, "CHANNEL_CODE":CHANNEL_CODE})))
    except:
        logger.debug("add dir and url all failure :%s" % (str({"CHANNEL_NAME":CHANNEL_NAME, "CHANNEL_CODE":CHANNEL_CODE})))
def del_dir_and_url_data(CHANNEL_CODE):
    try:
        db.dirandurl.remove({"CHANNEL_CODE":CHANNEL_CODE})
        domain_ignore = DIRANDURL.get(DIRANDURL_KEY)
        domain_ignore = json.loads(domain_ignore)
        del domain_ignore[CHANNEL_CODE]
        DIRANDURL.set(DIRANDURL_KEY, json.dumps(domain_ignore))

        logger.debug("del dir and url :%s" % (str(CHANNEL_CODE)))
    except:
        logger.debug("del dir and url failure:%s" % (str(CHANNEL_CODE)))


def get_overloads_config_list():
    overloads = [overload for overload in q_db.overloads_config.find()]
    return overloads

def add_overloads_config_data(username,max_url,max_dir, preload, user_email):
    try:
        db.overloads_config.insert({"USERNAME":username, "URL": max_url, "DIR": max_dir, "PRELOAD_URL": preload})
        operation_record_into_mongo(user_email, 'overload', 'insert', {"USERNAME":username, "URL": max_url,
                                                                       "DIR": max_dir, "PRELOAD_URL": preload})
        M_CACHERECORD.set('overload_' + username, json.dumps({"USERNAME": username, "URL": max_url, "DIR": max_dir,
                                                              "PRELOAD_URL": preload}))
        logger.debug("add overloads_config:%s" % (str({"USERNAME":username, "URL":max_url, "DIR":max_dir,
                                                       "PRELOAD_URL": preload})))
    except:
        logger.debug("add overloads_config failure:%s" % (str({"USERNAME":username, "URL":max_url, "DIR":max_dir,
                                                               "PRELOAD_URL": preload})))

def del_overloads_config_data(username, user_email):
    try:
        result = db.overloads_config.find({"USERNAME": username})
        result_t = []
        for res in result:
            logger.debug('del_overloads_config_data res:%s' % res)
            result_t.append(res)
        db.overloads_config.remove({"USERNAME":username})
        operation_record_into_mongo(user_email, 'overload', 'delete', result_t)
        M_CACHERECORD.delete('overload_' + username)
        logger.debug("del overloads_config:%s" % (str(username)))
    except:
        logger.debug("del overloads_config failure:%s" % (str(username)))

def get_keycustomer_list(args):
    if args.get('USERNAME'):
        datas = q_db.key_customers_monitor.find(args)
    else:
        datas = q_db.key_customers_monitor.find()
    logger.warn('key_customers_monitor:%s',datas)
    keycustomer_list = [{'USERNAME':data.get('USERNAME',""),'Monitor_Email':data.get('Monitor_Email',[]), 'id':data.get('_id',''), 'Channel_Code':data.get('Channel_Code','')} for data in datas]
    return keycustomer_list

def add_keycustomer_data(key_customer, channel_code, monitor_email):
    try:
        data = q_db.key_customers_monitor.find_one({"USERNAME":key_customer, 'Channel_Code':channel_code})
        if data:
            data['Monitor_Email'] = monitor_email
            db.key_customers_monitor.save(data)
            logger.debug("update key_customers_monitor:%s" % (str({"USERNAME":key_customer})))
        else:
            db.key_customers_monitor.insert({"USERNAME":key_customer,"Monitor_Email":monitor_email,"update_time":datetime.now(),"Channel_Code":channel_code})
            logger.debug("add key_customers_monitor:%s" % (str({"USERNAME":key_customer})))
    except Exception:
        logger.debug("add key_customers_monitor except:%s" % e)

def del_keycustomer_data(k_id):
    try:
        db.key_customers_monitor.remove({"_id":ObjectId(k_id)})
        logger.debug("del key_customers_monitor:%s" % (str(k_id)))
    except:
        logger.debug("del key_customers_monitor failure:%s" % (str(k_id)))

def get_timer_tasks():
    timer_tasks = []
    try:
        for timer in q_db.timer_task.find():
            for key in list(timer.get("tasks").keys()):
                timer_tasks.append(timer.get("tasks").get(key))
    except Exception:
        logger.debug("get timer_task failure :%s!" % e)
    return timer_tasks

def add_timer_tasks_data(timer):
    try:
        timer_task  = q_db.timer_task.find_one({"run_time":timer.get("run_time")})
        if timer_task:
            timer_task.get("tasks").setdefault(timer.get("username"),timer)
        else:
            timer_task = {"run_time":timer.get("run_time"),"tasks":{timer.get("username"):timer}}
        db.timer_task.save(timer_task)
        logger.debug("add timer_task :%s !" % timer_task )
    except Exception:
        logger.debug("add timer_task failure timer :%s ,except:%s!" % (timer,e))
    return get_timer_tasks()

def del_timer_tasks_data(username,run_time):
    try:
        logger.debug("del timer_tasks start username:%s,run_time:%s" % (username,run_time))
        timer_task  = q_db.timer_task.find_one({"run_time":run_time})
        timer_task.get("tasks").pop(username)
        if timer_task.get("tasks"):
            db.timer_tasks.save(timer_task)
        else:
            db.timer_tasks.remove({"_id":timer_task.get("_id")})
        logger.debug("del timer_tasks ok! timer_task:%s" % timer_task)
    except Exception:
        logger.debug("del timer_tasks failure username:%s,run_time:%s ,except:%s!" % (username,run_time,e))
    return get_timer_tasks()


def retry_api(dev_id):
    hc = httplib.Http(timeout=4)
    try:
        repo, response_body = hc.request("http://r.chinacache.com/internal/retry/%s" % dev_id, method='GET')
        #repo, response_body = hc.request("http://223.202.203.31:8090/internal/retry/%s" % dev_id, method='GET')
        if repo and repo.status == 200:
            message = json.loads(response_body)
            if message.get('code',0) == 200:
                return '重试下发中，请稍后刷新下页面查看重试设备状态！！'
            else:
                return message.get('message')
    except Exception:
        logger.error('retry_api error:%s' % traceback.format_exc())
    return '服务器连接异常!!'


def get_device_monitor_page(page=0, date_str_from=None ,date_str_to=None):
    '''
    获取监控(任务计数信息　成功／失败)
    '''
    if not date_str_from:
        date_str_from = get_current_date_str()
    if not date_str_to:
        date_str_to = get_current_date_str()    

    date_str_from_list = date_str_from.split('/')
    js_date_l_f = datetime(int(date_str_from_list[2]),int(date_str_from_list[0]), int(date_str_from_list[1]))
    date_str_to_list = date_str_to.split('/')
    js_date_l_t = datetime(int(date_str_to_list[2]),int(date_str_to_list[0]), int(date_str_to_list[1]))
    search_days = (js_date_l_t-js_date_l_f).days
    #logger.debug("search_days:%s" %search_days)

    total_page = 0
    all_failed = dict_add.Counter({})

    for i in range(search_days+1):

        searchday = js_date_l_f + timedelta(days=i)
        #logger.debug("searchday:%s" %searchday)
        date_key = searchday.strftime('%Y-%m-%d')
        for _code in MONITOR_DEVICE_STATUS_FAILED:
            _detail = M_CACHERECORD.hgetall(date_key + '_' + str(_code))     
            all_failed += dict_add.Counter(_detail)
         
    #logger.debug('---all failed %s'%(len(all_failed)))
    all_failed = dict(all_failed)
    all_failed_list = sorted(list(all_failed.items()), key=lambda x:x[1], reverse=True)
    per_page = 30
    total_count = len(all_failed_list)

    if not total_count:
        #logger.debug('---no total_count %s'%(all_failed_list))
        return {'devs':[],'total_page':0}

    total_page = int(math.ceil(total_count/(per_page*1.00)))

    if page > 0:
        min_rank = page*per_page - 1
    else:
        min_rank = 0

    max_rank = (page+1)*per_page

    sorted_failed = all_failed_list[min_rank:max_rank]
    sorted_keys = [k[0] for k in sorted_failed]
    sorted_failed = [ {"hostname":i[0], "failed":i[1], "success":0} for i in sorted_failed ]

    #logger.debug('---sorted_failed 111%s'%(sorted_failed))

    for _i in range(search_days+1):

        searchday = js_date_l_f + timedelta(days=_i)
        logger.debug("searchday:%s" %searchday)
        date_key = searchday.strftime('%Y-%m-%d')
        all_values = M_CACHERECORD.hmget(date_key + '_200', sorted_keys)     

        for _n, v in enumerate(all_values):

            if not v:
                v = 0
            else:
                v = int(v)

        sorted_failed[_n]['success'] += v

    #logger.debug('---sorted_failed 222%s'%(sorted_failed))

    return {'devs':sorted_failed, 'total_page':total_page}

def get_device_failed_detail_page(page=0, search_start_date=None, search_end_date=None, hostname=None, channel_name=None):
    #page, search_start_time, search_end_time, hostname, channel_name
    '''
    获取设备失败详情
    times_strs: ['00:00:00', '00:01:01']
    '''
    query = {}
    
    if  not  search_start_date:
        search_start_date = get_current_date_str()
        _year, _month, _day = search_start_date.split('-')
        s_hour, s_minute, s_second = 0, 0, 0
        start_date = datetime(int(_year), int(_month), int(_day), int(s_hour), int(s_minute), int(s_second))
    else:
        logger.debug("search_start_date:%s" %search_start_date)
        search_start_date = search_start_date.strftime('%Y-%m-%d %H:%M:%S')
        start_listt = search_start_date.split(' ')
        start_list1 = start_listt[0].split('-')
        start_list2 = start_listt[1].split(':')
        start_date = datetime(int(start_list1[0]), int(start_list1[1]), int(start_list1[2]), int(start_list2[0]), int(start_list2[1]), int(start_list2[2]))

    if not search_end_date:
        search_end_date = get_current_date_str()
        _year,_month,_day = search_end_date.split('-')
        e_hour, e_minute, e_second = 23 , 59, 59
        end_date = datetime(int(_year), int(_month), int(_day),int(e_hour),int(e_minute),int(e_second))
    else:
        logger.debug("search_end_date:%s" %search_end_date)
        
        search_end_date = search_end_date.strftime('%Y-%m-%d %H:%M:%S')
        end_listt = search_end_date.split(' ')
        end_list1 = end_listt[0].split('-')
        end_list2 = end_listt[1].split(':')
        end_date = datetime(int(end_list1[0]), int(end_list1[1]), int(end_list1[2]), int(end_list2[0]), int(end_list2[1]), int(end_list2[2]))
    logger.debug("search_end_date:%s" %search_end_date)
    logger.debug("start_date:%s,end_date:%s"%(start_date,end_date)) 
    query["datetime"] = {'$lte':end_date,'$gt':start_date}
    query['url.code'] = {'$in':models.MONITOR_DEVICE_STATUS_FAILED}
    if hostname:
        query['hostname'] = hostname
    if channel_name:
        query['url.channel_name'] = channel_name
    per_page = 30
    total_page = int(math.ceil(monitor_db.device_urls_day.find(query).count(True)/(per_page*1.00)))
    all_detail = [u for u in monitor_db.device_urls_day.find(query).sort('datetime', pymongo.DESCENDING).skip(page*per_page).limit(per_page)]
    return {'total_page':total_page, 'details': all_detail}
    
def get_device_failed_url(hostname, start_datetime, end_datetime, channel_name=None, username_list=None):
    '''
    获取该设备失败任务
    '''
    _query = {"datetime":{'$lte':end_datetime,'$gt':start_datetime},"hostname":hostname,"url.code":{'$in':models.MONITOR_DEVICE_STATUS_FAILED}} 
    if channel_name:
        _query['url.channel_name'] = channel_name
    if username_list:
        _query['url.username'] = {'$in':username_list}
    #logger.debug(_query)
   # logger.debug(models.MONITOR_DEVICE_STATUS_FAILED)
    #return monitor_db.device_urls_day.distinct('set_key', _query)
    #return monitor_db.device_urls_day.find(_query).sort('datetime', pymongo.DESCENDING)
    return monitor_db.device_urls_day.find(_query).sort('datetime', pymongo.ASCENDING)



def get_device_monitor(hostname, date_str_from ,date_str_to):
    '''
    获得指定设备任务计数情况
    '''
    date_str_from_list = date_str_from.split('/')
    js_date_l_f = datetime(int(date_str_from_list[2]),int(date_str_from_list[0]), int(date_str_from_list[1]))
    date_str_to_list = date_str_to.split('/')
    js_date_l_t = datetime(int(date_str_to_list[2]),int(date_str_to_list[0]), int(date_str_to_list[1]))
    search_days = (js_date_l_t-js_date_l_f).days
    logger.debug("search_days:%s" %search_days)
     
    dev_info = {'hostname':hostname}
    
    for i in range(search_days+1):
        searchday = js_date_l_f + timedelta(days=i)
        logger.debug("searchday:%s" %searchday)
        sort = searchday.strftime('%Y-%m-%d')
        sort_list = sort.split('-')
        sort_key = '%s-%s-%s' %(sort_list[0],sort_list[1], sort_list[2])
        logger.debug("sort_key:%s" %sort_key)
        for s in MONITOR_DEVICE_STATUS:
            s_key = '%s_%s'%(sort_key, s)
            logger.debug("s_key:%s" %s_key)
            v = M_CACHERECORD.hget(s_key, hostname)
            if not v:
                v = 0
            if s ==204 or s == 503:
                if 'failed' in list(dev_info.keys()):
                    _vv = v
                    ss = dev_info['failed']
                    dev_info['failed'] = ss + int(_vv)
                else:
                    dev_info['failed'] = int(v)
            else:
                if 'success' in list(dev_info.keys()):
                    _vv = v
                    ss = dev_info['success']
                    dev_info['success'] = ss + int(_vv)
                else:
                    dev_info['success'] = int(v)

    logger.debug("dev_info:%s" %dev_info)
    return dev_info


def make_failed_url_res(res):
    '''
    生成边缘脚本执行格式内容
    '''
    writes = []

    #logger.debug(r.count())
    
    for r in res:
        _type = 'url'
        if r['url']['isdir']:
            _type = 'dir'
        strs = '%s,%s,%s,%s' %(r['url']['url'], r['url']['action'],_type, r.get('datetime', ''))
        writes.append(strs)
    return writes


def device_failed_url_to_txt(txt_name, res):
    '''
    设备任务生成txt
    '''
    #dir = '/Application/bermuda3/static/log_txt/%s.txt' %(txt_name)       
    z_dir = '/Application/bermuda3/static/log_txt/%s.txt.gz' %(txt_name)       
    if os.path.exists(z_dir):
        #已经存在
        #logger.debug('%s fail url to txt had exists'% z_dir)
        os.remove(z_dir)

    writes = make_failed_url_res(res)

    with gzip.open(z_dir, 'wb') as f: 
        f.write('\n'.join(writes))

   # with open(dir, 'w') as wr:                                       
   #     for r in res:                                                
   #         logger.debug('-------------abcdef---------')
   #	    logger.debug(r)

   #         _type = 'url'                                            
   #         if r['isdir']:
   #             _type = 'dir'
   #         strs = '%s,%s,%s,\n' %(r['url'], r['action'],_type)
   #         writes.append(strs)
   #         if len(writes) >= 2:
   #             wr.writelines(writes)
   #             writes = []

   #     if writes:
   #         wr.writelines(writes)
   #         writes = []
        

    #with zipfile.ZipFile(z_dir, 'w') as zi:
    #    zi.write(dir,'%s.txt'%(txt_name))
    #zi.close()

   # try:
   # 	#TODO 删除旧文件
   #     os.remove(dir)
   # except:
   #     pass

    return


def init_monitor_data(_date, _id, _type, count=10):
    '''
    _date: "2:48:22"
    初始化 date 前十次间隔的数据
    间隔: 2s
    '''
    interval = 2
    res = []
    now = datetime.now()
    search_hour, search_min, search_seconds = _date.split(':')
    search_date = datetime(now.year,now.month,now.day, now.hour, int(search_min), int(search_seconds))

    for x in range(count):
        search_date = search_date - timedelta(seconds=interval)
        keys = _get_monitor_hour_seconds(search_date, _range=interval)
        all_value = 0
        for _k in keys:
            _k_h = _k[0]
            _k_s = _k[1]
            _key = '%s_%s_%s' %(_id, _k_h, _type)
            value = M_CACHERECORD.hget(_key, _k_s) 
            #logger.debug('_key %s' %(_key))  
            #logger.debug('sub_key %s' %(sub_key))  
            if not value:
                value = 0
            all_value += int(value)
            
        res.insert(0, all_value)

   # logger.debug('_date %s' %(_date))  
   # logger.debug('_id %s' %(_id))  
   # logger.debug('res %s' %(res))  

    return res


def _get_monitor_hour_seconds(date_obj,_range=1):
    '''
    获取指定时间监控的 hour and secods
    '''
    res = []
    for x in range(_range):
        _date = date_obj - timedelta(seconds=x)
        keys =[_date.hour, int(_date.minute)*60 + _date.second]
        res.append(keys)
    return res
        

def get_all_refresh_high_priority_page(username,channel_name, page=0):
    '''
    获取高优先级刷新频道配置
    '''
    query = {}
    if username:
        query['username'] = username
    if channel_name:
        query['channel_name'] = channel_name
    per_page = 30
    total_page = int(math.ceil(db.refresh_high_priority.find(query).count(True)/(per_page*1.00)))
    all_detail = [u for u in db.refresh_high_priority.find(query).sort('created_time', pymongo.DESCENDING).skip(page*per_page).limit(per_page)]
    return {'total_page': total_page, 'details': all_detail}

def get_refresh_high_priority_unopen(username):
    '''
    获取尚且没开通高优先级的频道
    '''
    all_channels = rcmsapi.get_channels(username)
    #logger.debug('all_channels %s' %(all_channels))
    if not all_channels:
        return []
    all_high_channels = [n['channel_name'] for n in db.refresh_high_priority.find({'username':username},{'channel_name':1})]
    #logger.debug('all_high_channels %s' %(all_high_channels))
    return [ i for i in all_channels if i['name'] not in all_high_channels] 


def add_refresh_high_priority(db_map):
    '''
    添加高优先级频道
    '''
    o_db_map = copy.deepcopy(db_map)
    #logger.debug('db_map %s' %(db_map))
    db.refresh_high_priority.insert_many(db_map)
    cache_map = {'h_priority_%s'%(i['channel_code']):json.dumps(i,cls=DatetimeJSONEncoder) for i in o_db_map}
    #logger.debug('cache_map %s' %(cache_map))
    H_PRIORITY_CACHE.mset(cache_map)


def del_refresh_high_priority(channel_code):
    '''
    删除高优先级配置
    '''
    db.refresh_high_priority.remove({'channel_code':channel_code})
    c_key = 'h_priority_%s'%(channel_code)
    H_PRIORITY_CACHE.delete(c_key)


def get_email_management_list(query):
    """
    get detail of email info
    :param query: {'type':'xx', 'email_name': 'xxx'}
    :return:
    """
    type_info = query.get('type', None)
    email_name = query.get('email_name', None)
    result_end = []
    per_page = 15
    if type_info:
        try:
            result = db.email_management.find({'failed_type': type_info})
            logger.debug('get_email_management_list find email_management success type:%s' % type_info)
        except Exception:
            logger.debug('get_email_management_list find email_management error:%s, type:%s' % (e, type_info))
    else:
        try:
            result = db.email_management.find()
            logger.debug('get_email_management_list find email_management success')
        except Exception:
            logger.debufg('get_email_management_list find email_management error:%s' % e)
    if not result:
        query['total_page'] = 0
        return []
    else:
        length = result.count()
        if not email_name:
            query['total_page'] = int(math.ceil(length/(per_page*1.0)))
            return result[per_page*query.get("page"):per_page*(query.get("page") + 1)]
        else:
            for res in result:
                addresses = res.get('email_address', '')
                if addresses:
                    for address in addresses:
                        logger.debug("email_name:%s, address:%s" % (email_name, address))
                        # illegibility matching
                        if str(email_name) in str(address):
                            result_end.append(res)
                            break
            query['total_page'] = int(math.ceil(len(result_end)/(per_page*1.0)))
            return result_end[per_page*query.get("page"):per_page*(query.get("page") + 1)]


def add_email_management(_type, address, devices, threshold):
    """
    add mail configuration
    :param _type: the type of alarm
    :param address: address of email
    :param devices: concerned devices
    :param threshold: threshold
    :return:
    """
    #logger.debug('address_type %s' %(type(address)))
    _type = _type.strip()
    if not isinstance(address, list):
        address = strip_list(address.split(','))
    if not isinstance(devices, list):
        devices = strip_list(devices.split(','))
    try:
        threshold = int(threshold.strip())
    except Exception:
        logger.debug("int threshold error:%s" % e)
        return
    try:
        db.email_management.insert_one({'type': _type, 'address': address, 'created_time': datetime.now(),
                                        'devices': devices, 'threshold': threshold})
    except Exception:
        logger.debug("insert_one email_management error:%s" % e)
        return
    # data = db.email_management.find_one({'type':_type})
    # if data:
    #     db.email_management.update_one({'type':_type},{'$set':{'address':address}})
    # else:
    #     db.email_management.insert_one({'type':_type, 'address':address, 'created_time':datetime.now()})


def del_email_management(_id, user_email):
    '''
    删除配置
    '''
    try:
        result = db.email_management.find_one({'_id': ObjectId(_id)})
        db.email_management.remove({'_id': ObjectId(_id)})
        operation_record_into_mongo(user_email, 'mail_list_config', 'delete', result)
    except Exception:
        logger.debug("del_email_managemet error:%s" % traceback.format_exc())


def find_link_device_hours_result(query_args, times=6):
    """
    according to the content of query_args, query data from mongo
    :param query_args:
    :param times:judge failed dev
    :return:
    """
    per_page = 30
    query_condition = {}
    name = query_args.get('name', '')
    ip = query_args.get('ip', '')
    if name:
        query_condition['name'] = name
    if ip:
        query_condition['ip'] = ip
    time_start_str = query_args.get('time_start', '')
    time_end_str = query_args.get('time_end', '')
    logger.debug("find_link_device_hours_result time_start_str:%s, time_end_str:%s" % (time_start_str, time_end_str))
    start_time = datetime.strptime(time_start_str, "%Y-%m-%d %H")
    # a character string of the current time is accurate to the hour
    now_str = datetime.strftime(datetime.now(), "%Y-%m-%d %H")
    if now_str < time_end_str:
        end_time = datetime.strptime(now_str, "%Y-%m-%d %H")
    else:
        end_time = datetime.strptime(time_end_str, "%Y-%m-%d %H")
    # end_time = start_time + timedelta(days=1)
    logger.debug("find_link_device_hours_result start_time:%s, end_time:%s" % (start_time, end_time))
    query_condition['datetime'] = {"$lte": end_time,
                                   "$gt": start_time}
    logger.debug("find_link_device_hours_result query_conditon: %s" % query_condition)
    try:
        result = db.device_link_hours_result.find(query_condition)
        # logger.debug("find_link_device_hours_result result:%s" % result)
    except Exception:
        logger.debug("device_link_hours_result find error:%s" % e)
        query_args['totalpage'] = 0
        return []
    result = assemble_link_device_hours_result(result)

    # total number of devices
    total_dev = len(result)
    query_args['total_devs'] = total_dev
    # the criterion of judge failed dev number
    diff_seconds = calculate_diff_between_time(start_time, end_time)
    judge_criterion = diff_seconds/3600 * 6
    failed_num = get_failed_dev_number(result, judge_criterion)
    success_num = total_dev - failed_num
    query_args['failed_devs'] = failed_num
    query_args['success_devs'] = success_num
    query_args['start_time_ex'] = datetime.strftime(start_time, '%Y/%m/%d %H:00 ')
    query_args['end_time_ex'] = datetime.strftime(end_time, " %Y/%m/%d %H:00")
    query_args['start_time'] = datetime.strftime(start_time, '%Y-%m-%d %H')
    query_args['end_time'] = datetime.strftime(end_time, '%Y-%m-%d %H')
    query_args['judge_criterion'] = judge_criterion
    # according to the number of failures, in descending order
    result = sorted(result, key=lambda result: result.get('failed'), reverse=True)
    # logger.debug('find_link_device_hours_result:%s' % result)
    query_args["totalpage"] = int(math.ceil(len(result)/(per_page*1.0)))
    return result[per_page*query_args.get("curpage"):per_page*(query_args.get("curpage") + 1)]


def get_failed_dev_number(result, judge_criterion):
    """
    get the all failed dev number
    :param result: [{'ip': '192.168.1.1', 'name':xxx, 'failed': 5}]
    :param judge_criterion: the criterion of failed dev
    :return: number  int
    """
    number = 0
    if result:
        for res in result:
            if res.get('failed', 0) >= judge_criterion:
                number += 1
    return number


def assemble_link_device_hours_result(result):
    """
    re assemble the result of link detection
    :param result: link detection results for one day
    [{'ip': '192.168.1.1', 'name':xxx, 'failed': 2}, {'ip': '192.168.1.1', 'name':xxx, 'failed': 3}]
    :return:[{'ip': '192.168.1.1', 'name':xxx, 'failed': 5}]
    """
    dict_res = {}
    if not result:
        return []
    else:
        for res in result:
            name = res.get('name', None)
            if name not in dict_res:
                dict_res[name] = res
            else:
                dict_res[name]['failed'] += res.get('failed', 0)
        return list(dict_res.values())


def get_device_link_detail(start_time, end_time, ip):
    """
    according end_time,ip  get data from device_link, time range of an hour before end_time
    :param start_time: the date of day   2016-08-15 9
    :param end_time： the end of date  2016-08-16 9
    :param ip: ip of device
    :return: device status information corresponding to IP for a period of time
    """
    if not (start_time and ip):
        return []
    else:
        result = []
        # type datetime   start  time
        start_time_new = datetime.strptime(start_time, "%Y-%m-%d %H")
        # type datetime  end time
        end_time_new = datetime.strptime(end_time, "%Y-%m-%d %H")
        try:
            db_result = db.device_link.find({'detect_time': {'$gte': start_time_new, '$lt': end_time_new}})
        except Exception:
            logger.debug("find device_link error:%s" % e)
            return []
        logger.debug("db_result:%s" % db_result)
        for res in db_result:
            dic_temp = {}
            dic_temp['detect_time'] = res.get('detect_time', '')
            for dev in res.get('devices'):
                # logger.debug("get_device_link_detail dev:%s, ip:%s" % (dev, ip))
                if dev.get('ip') == ip:
                    dic_temp['ip'] = ip
                    dic_temp['name'] = dev.get('name', '--')
                    dic_temp['code'] = int(dev.get('code', 0))
                    result.append(dic_temp)
                    break
        return result


def get_province_control_table():
    """

    :return: {'BJ': '北京'}
    """
    data = {'XJ': '新疆', 'XZ': '西藏', 'QH': '青海', 'GX': '广西', 'WUE': '维吾尔', 'SC': '四川', 'YN': '云南',
            'GZ': '贵州', 'CQ': '重庆', 'SX': '山西', 'SXS': '陕西',  'HN': '海南', 'GS': '甘肃', 'XG': '香港',
            'GD': '广东', 'HUN': '湖南', 'JX': '江西', 'FJ': '福建', 'TW': '台湾', 'ZJ': '浙江', 'HUB': '湖北',
            'AH': '安徽', 'JS': '江苏', 'SH': '上海', 'HEN': '河南', 'SD': '山东', 'HB': '河北', 'BJ': '北京',
            'TJ': '天津', 'NMG': '内蒙古', 'LN': '辽宁', 'JL': '吉林', 'HLJ': '黑龙江', 'NX': '宁夏'}
    return data


def get_province_control_table_reverse():
    """
    :return: reverse pin yin and city name
    """
    data = get_province_control_table()
    return {value.decode(): key for key, value in data.items()}


def get_start_end_time(hour):
    """
    calcultate the current time, and hour hours before the time
    :param hour: integer hour
    :return: start_time   end_time
    """
    now = datetime.now()
    str_now = now.strftime("%Y-%m-%d %H")
    start_time = datetime.strptime(str_now, '%Y-%m-%d %H')
    end_time = start_time + timedelta(hours=hour)
    return start_time, end_time


def init_province_number(data):
    """
    init province info
    :param data: {'XJ': '新疆', 'XZ': '西藏',....}
    :return: {'新疆':0, '西藏':0, ....}
    """
    province_number = {}
    for key in list(data.keys()):
        province_number[data[key]] = 0
    return province_number


def parse_province_data(data):
    """

    :param data: {'新疆':2, '西藏':0, ....}
    :return: [{'name': '新疆', 'value': 2}, {'name': '西藏', 'value': 0}, ...]
    """
    result_list = []
    for key, value in list(data.items()):
        temp = {}
        temp['name'] = key
        temp['value'] = value
        result_list.append(temp)
    return result_list


def get_hour_link_detect_result(times=3, isp_list=[], flag=1):
    """
    :param times: threshold of failure times
    :param isp_list: the list of service providers
    :param flag: 1 init map, 2 update map
    :return:[{'name':xxx, 'value': 3},{'name':xxx, 'value': 2}]
    """
    start_time, end_time = get_start_end_time(1)
    result_start_time = str_time(start_time)
    result_end_time = str_time(end_time)
    logger.debug("get_hour_link_detect_result result_start_time:%s, result_end_time:%s" %
                 (result_start_time, result_end_time))
    try:
        result = db.device_link_hours_result.find({'datetime': {"$gte": start_time, '$lt': end_time}})
    except Exception:
        logger.debug("get_hour_link_detect_result find hour:%s" % e)
        return json.dumps({'msg': 'error', 'result': [], 'content': '查询mongo出现错误！'})
    province_data = get_province_control_table()
    province_number = init_province_number(province_data)
    # list of service providers  set
    isp_set = set()
    if result:
        for res in result:
            province_abbreviation = res.get('provinceName', '')
            if province_abbreviation in province_data and res.get('failed', 0) > 3:
                if flag == 1:
                    province_name = province_data[province_abbreviation]
                    isp_set.add(res.get('ispName', 'NoIsp'))
                    province_number[province_name] += 1
                else:
                    ispName = res.get('ispName', '')
                    if ispName in isp_list:
                        province_name = province_data[province_abbreviation]
                        province_number[province_name] += 1
        return json.dumps({'msg': 'ok', 'result': parse_province_data(province_number),
                           'start_time': result_start_time, 'end_time': result_end_time, 'isp_list': list(isp_set)},
                            ensure_ascii=False)
    else:
        return json.dumps({'msg': 'error', 'result': [], 'content': 'data in empty!'})


def str_time(time):
    """

    :param time:datetime
    :return: str of datetime
    """
    return datetime.strftime(time, "%Y-%m-%d %H点")


def get_hour_link_detect_result_province(city, isp_list, times=3):
    """

    :param city:
    :param isp_list: the list of service providers
    :param times:
    :return:
    """
    logger.debug("get_hour_link_detect_result_province city:%s" % city)
    result_detail = []
    start_time, end_time = get_start_end_time(1)
    province_data = get_province_control_table_reverse()
    logger.debug('get_hour_link_detect_result_province province_data:%s' % province_data)
    province_abbreviation = province_data.get(city, None)
    if not province_abbreviation:
        logger.debug("get_hour_link_detect_result_province  province_abbreviation is null!")
        return result_detail
    try:
        result = db.device_link_hours_result.find({'datetime': {"$gte": start_time, '$lt': end_time},
                                                   'provinceName': province_abbreviation})
    except Exception:
        logger.debug("get_hour_link_detect_result find hour:%s" % e)
        return json.dumps({'msg': 'error', 'result': [], 'content': '查询mongo出现错误！'})
    province_data = get_province_control_table()
    # province_number = init_province_number(province_data)
    if result:
        for res in result:
            province_abbreviation = res.get('provinceName', '')
            if province_abbreviation in province_data and res.get('failed', 0) > times:
                if res.get('ispName', '') in isp_list:
                    result_detail.append(res)
        result_detail = sorted(result_detail, key=lambda k: k.get('failed'), reverse=True)
        return result_detail
    else:
        return result_detail


def get_subcenter_info(args):
    """
    according to the content of args, query data from mongo
    :param args:
    :return:
    """
    per_page = 30
    query_condition = {}
    name = args.get('name', '')
    ip = args.get('ip', '')
    if name:
        query_condition['name'] = name
    if ip:
        query_condition['ip'] = ip
    logger.debug("find_link_device_hours_result query_conditon: %s" % query_condition)
    try:
        result = db.sub_regis_info.find(query_condition).sort('status', pymongo.DESCENDING)
        logger.debug("find_link_device_hours_result result:%s" % result)
    except Exception:
        logger.debug("device_link_hours_result find error:%s" % e)
        args['totalpage'] = 0
        return []
    result_new = []
    for res in result:
        result_new.append(res)
    args["totalpage"] = int(math.ceil(len(result_new)/(per_page*1.0)))
    return result_new[per_page*args.get("curpage"):per_page*(args.get("curpage") + 1)]


def get_devs_opened(args):
    """
    get all dev at channel_code and dev_name
    :param args:
    :return:
    """
    dev_name = args.get("dev_name", '')
    channel_name = args.get('channel_name', '')
    channel = rcmsapi.getChannelCode(channel_name)
    logger.debug("channel  code:%s" % channel)
    if channel and len(channel) >0:
        channel_code = channel[0].get('channelCode', '')
        if channel_code:
            rcms_devs = [dev for dev in rcmsapi.getFirstLayerDevices(channel_code) +
                 rcmsapi.getDevices(channel_code) if dev.get("status") == "OPEN"]
            if dev_name:
                rcms_devs = [ dev for dev in rcms_devs if dev.get("name") == dev_name]
            return rcms_devs
    return []


def insert_email_management(result):
    """
    insert result into mongo
    :param result:
    :return:
    """
    _id = result.get('_id', '')
    if _id == '':
        result.pop("_id")
        try:
            db.email_management.insert_one(result)
            logger.debug("insert email_management success")
            operation_record_into_mongo(result['user_email'], 'mail_list_config', 'insert', result)
        except Exception:
            logger.debug("insert email_managemnet error:%s" % e)
    else:
        result['_id'] = ObjectId(result['_id'])
        logger.debug("result._id:%s, type:%s" % (result['_id'], type(result['_id'])))
        # return
        try:
            db.email_management.update_one({'_id': result['_id']}, {'$set': result})
            logger.debug('update_one email_management success _id:%s' % result['_id'])
            operation_record_into_mongo(result['user_email'], 'mail_list_config', 'update', result)
        except Exception:
            logger.debug('update_one email_management _id:%s, error:%s' % (result['_id'], e))


def operation_log_list(args, query):
    """

    Args:
        args:
        query: query criteria

    Returns:  operation log list

    """
    # user_email = request.get('user_email', '')
    # operation_type = request.get('operation_type', '')
    # # small_operation_type = request.get('small_operation_type', '')
    # time_start = request.get('time_start', '')
    # time_end = request.get('time_end', '')
    # content = request.get('content', '')
    # page = int(request.get('page', 0))
    per_page = 15
    if not query['user']:
        query.pop('user')
    if not query['operation_type']:
        query.pop('operation_type')
    content = query['content']
    query.pop('content')

    # Y-m-d H
    result = []
    time_start =  datetime.strptime(query['time_start'], "%Y-%m-%d %H")
    time_end = datetime.strptime(query['time_end'], '%Y-%m-%d %H')
    query.pop('time_start')
    query.pop('time_end')
    query['operation_time'] = {'$gte': time_start, '$lt': time_end}
    logger.debug('operation_log_list query:%s' % query)
    try:
        result_t = db.operation_record.find(query)
        logger.debug('')
    except Exception:
        logger.debug('operation_log_list error:%s' % traceback.format_exc())

    if result_t:
        if content:
            for res in result_t:
                content_t = res.get('content')

                if content in JSONEncoder().encode(content_t):
                    result.append(res)
        else:
            for res in result_t:
                result.append(res)
    args['total_page'] = int(math.ceil(len(result)/(per_page*1.0)))
    return result[per_page * args.get('page'): per_page*(args.get('page') + 1)]


def callback_email_query(username):
    """
    according username,channel_name, to find the relationship with the channel_name,
    :param username: the name of user
    :param channel_name: the name of url
    :return: the list of collection rewrite_new like [{'_id':xxx, 'username':xxxx, 'channel_list':XXXx},\
          {'_id':xxx, 'username':xxxx, 'channel_list':XXXx}]
    """
    list_callback_email = []

    try:
        if username == '':
            list_rewrite_temp = q_db.callback_email_control.find()
        else:
            list_rewrite_temp = q_db.callback_email_control.find({"username": username})
    except Exception:
        logger.debug("can not get data from collection of rewrite_new, except:%s" % e)

    for channel in list_rewrite_temp:
        list_callback_email.append(channel)
    return list_callback_email


def model_update_callback_email(data):
    """
    according data, insert into rewrite_new and update redis
    :param data: the content of rewrite_new
    :return:
    """
    username = data.get("username", '')


    if username:
        # first insert data into mongodb, then update redis
        try:
            result_t = db.callback_email_control.find_one({"username": username})
            if result_t:
                return json.dumps({"msg": 'error', 'result': 'username:%s already in the database' % username})
            db.callback_email_control.insert(data)
        except Exception:
            logger.debug("update_rewrite_no_id, insert mongo error,username:%s, Exception:%s" % (username, e))
            return json.dumps({'msg': 'error', 'result': 'update_rewrite_no_id  exception:%s' % e})
        try:
            CALLBACK_CACHE.set(prefix_callback_email_username + username, 1)
        except Exception:
            logger.debug("update_callback_email, update redis error, username:%s, Exception:%s" % (username, traceback.format_exc()))
            return json.dumps({'msg': 'error', 'result': 'update_rewrite_no_id  exception:%s' % traceback.format_exc()})
        return json.dumps({'msg': 'ok', 'result': 'update_callback_email success!'})
    return json.dumps({'msg':'error', 'result': 'update_callback_email received data has problem'})


def model_delete_callback_email(data):
    """
    accoding the id of data, to delete info in mongo, udpate the redis info
    step:
    first: get data from mongo
    second: delete data in mongo
    third: update data in redis
    :param data:
    :return:
    """
    id = data.get('id', '')
    username = data.get('username', '')

    try:
        # delete data from mongo, according the id
        db.callback_email_control.remove({"_id": ObjectId(id)})
        # operation_record_into_mongo(data.get('user_email'), 'channel_redirection', 'delete', result)
    except Exception:
        logger.debug("model_delete_callback_email error, delete data error, id:%s, exception:%s" % (id, traceback.format_exc()))
        return json.dumsp({"msg": 'error', 'result': 'del data from mongo error, exception:%s' % traceback.format_exc()})
    try:
        CALLBACK_CACHE.delete(prefix_callback_email_username + username)
    except Exception:
        logger.debug("model_delete_callback_email error, delete redis error, id:%s, exception:%s" % (id, traceback.format_exc()))
        return json.dumps({"msg": 'error', 'result': 'del data from redis error, exception:%s' % traceback.format_exc()})
    return json.dumps({'msg': 'ok', 'result': 'model_delete_callback_email, success!'})

def get_subcent_refresh_dev(uid):
    """
    according retry_branch_id, get data from retry_device_branch
    :param retry_branch_id: the _id of retry_device_branch collection
    :return:
    """
    devices = []
    success_dev_list = []
    count, unprocess = 0 ,0
    try:
        devices_result = monitor_db.subcenter_refresh_result.find({"uid": uid})
    except Exception:
        logger.debug("get_retry_dev_branch_by_id query mongo error:%s" % e)
        return 0,0,devices
    if not devices_result:
        return 0,0,devices
    else:

        for dev in devices_result:
            if count ==0:
                count = dev.get('fail_dev_num')
            if dev.get('edge_result') == 200:
                success_dev_list.append(dev.get('edge_host'))
            devices.append(dev)
        unprocess = count - len(set(success_dev_list))
        return count,unprocess,devices
def get_sub_refreh_result(devs):
    """
    statistic  code number,  have  branch_code, not have branch_code
    :param devs:
    :return: the number of all device,  the number of device not have branch_code
    """
    not_have_code_number = 0
    all_dev = len(devs)
    logger.debug("modes statistic_branch devs:%s" % devs)
    if devs:
        for dev in devs:
            if dev.get('branch_code', 0) == 0:
                not_have_code_number += 1
                dev['branch_code'] = 0
    return all_dev, not_have_code_number
def find_expired_cert():
    return {}