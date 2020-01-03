#! /usr/bin/env python
# -*- coding: utf-8 -*-
import logging
from core.database import query_db_session
import hashlib
import time
import http.client
import urllib.request, urllib.parse, urllib.error
import datetime
import simplejson as json


LOG_FILENAME = '/Application/bermuda3/logs/refresh_preload.log'
logging.basicConfig(filename=LOG_FILENAME,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger('refresh_preload')
logger.setLevel(logging.DEBUG)

db = query_db_session()

def check_url(act_time,end_time):
    all_task=db.refresh_preload.find({"refresh_end_time": {"$gte": act_time, "$lt": end_time},"callback":'success',"preload": {"$exists": False}})
    request_dict = {}
    #request_id_list = []
    request_id_list = {}
    #send_dict_reqid = {}
    for task in all_task:
        try:
            request_id = task.pop('r_id')
            if not request_dict.get(request_id):
                task.pop('refresh_end_time')
                request_id_list.setdefault(request_id, []).append(task.pop('_id'))
                task.pop('callback')
                url = task.pop('url')
                url_id = task.pop('id')
                url_dict = {'url': url, 'id': url_id}
                task.setdefault('tasks', []).append(url_dict)
                task.setdefault('is_repeated', True)
                task.setdefault('validationType', 'BASIC')
                request_dict.setdefault(request_id, task)
                pass
            else:
                request_id_list.setdefault(request_id, []).append(task.pop('_id'))
                url = task.pop('url')
                url_id = task.pop('id')
                url_dict = {'url': url, 'id': url_id}
                request_dict.get(request_id).get('tasks',[]).append(url_dict)
                pass
        except Exception:
            logger.debug(e.message)
    return request_id_list,request_dict

def send_url(request_dict):
    url_list = []
    try:
        for request_id,request_dict_one in list(request_dict.items()):
            logger.debug("refresh preload start request id %s"%(request_id))
            #conn = httplib.HTTPConnection("223.202.203.31:80")
            conn = http.client.HTTPConnection("r.chinacache.com")
            headers = {"Content-type": "application/json"}
            params = (request_dict_one)
            conn.request("POST", "/internal/preload", json.JSONEncoder().encode(params), headers)
            #params = urllib.urlencode(request_dict_one)
            print(params)
            #conn.request("POST", "/internal/preload",params , headers)
            response = conn.getresponse()
            print(response.read())
            conn.close()
            url_list.append(request_id)
            logger.debug("refresh preload end request id %s" % (request_id))
    except Exception:
        logger.debug("send url request id %s error %s"%(request_id,e.message))
    return url_list
def delete_url(request_id):
    db.refresh_preload.delete_many({'_id':{'$in':request_id}})
    logger.debug('delete request id list %s'%(request_id))
    pass
def set_preload(url_id_list):
    db.refresh_preload.update_many({'_id':{"$in":url_id_list}},{'$set':{"preload":"sucess"}})
    #db.refresh_preload.update({'_id':{"$in":url_id_list}},{'$set': {"preload":"sucess"}}, multi=True)

    pass
def main(act_time,end_time):
    request_id_dict, request_dict = check_url(act_time,end_time)
    if not  request_dict:
        return
    request_id_list = send_url(request_dict)

    preload_success_id_list = []
    for r_id in request_id_list:
        preload_success_id_list = preload_success_id_list + request_id_dict.get(r_id,[])
    set_preload(preload_success_id_list)
    logger.debug("refresh preload id list %s" % (preload_success_id_list))
    #delete_url(request_id)
def run():
    # now = datetime.datetime.now()
    # start_str = 'start check on {datetime}'.format(datetime=now)
    now = datetime.datetime.now()

    #logger.info(start_str)
    end_time = datetime.datetime.combine(now.date(), now.time().replace(microsecond=0))
    act_time = end_time - datetime.timedelta(seconds=5)
    logger.debug('check refresh start time  {datetime}'.format(datetime=act_time))
    logger.debug('check refresh end  time  {datetime}'.format(datetime=end_time))
    main(act_time,end_time)

if __name__ == '__main__':
    run()
