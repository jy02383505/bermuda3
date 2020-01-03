#! /usr/bin/env python
# -*- coding: utf-8 -*-
__author__ = 'vance'
__date__ = '15-12-25'

# import redis
# try:
#     from pymongo import ReplicaSetConnection as MongoClient
# except:
#     from pymongo import MongoClient
import logging
# from collections import Counter, OrderedDict, defaultdict
import datetime
import urllib
import os
import requests
from core import database
import core.redisfactory as redisfactory

import time
import hashlib
import traceback
import urllib.request, urllib.error, urllib.parse
import ssl
import simplejson as json
from core.config import config
import sys

# uri = 'mongodb://bermuda:bermuda_refresh@%s:27017,%s:27017,%s:27017/bermuda?replicaSet=bermuda_db' % (
# '172.16.12.136', '172.16.12.135', '172.16.12.134')
# uri = 'mongodb://bermuda:bermuda_refresh@%s:27017/bermuda' % ('223.202.52.82')
# con = MongoClient(uri)['bermuda']
# REDIS_CLIENT = redis.StrictRedis(host='%s' % '172.16.21.205', port=6379, db=9)
LOG_FILENAME = '/Application/bermuda3/logs/count_device.log'
logging.basicConfig(filename=LOG_FILENAME,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger('count_deivce')
logger.setLevel(logging.DEBUG)

# db = database.db_session()
q_db = database.query_db_session()

DEVICE_TYPE = redisfactory.getDB(12)

#RCMS_API = 'https://rcmsapi.chinacache.com/device/name/{0}/apps'
RCMS_API = 'https://cms3-apir.chinacache.com/device/name/{0}/apps'
#RCMS_DEVICES_LAYER = 'https://rcmsapi.chinacache.com/upperlayer/devices'
RCMS_DEVICES_LAYER = 'https://cms3-apir.chinacache.com/upperlayer/devices'
#RCMS_DEVICES = "https://rcmsapi.chinacache.com/devices"
RCMS_DEVICES = "https://cms3-apir.chinacache.com/devices"
# RCMS_DEVICES = "http://rcmsapi-private.chinacache.net:36000/devices"
#  get node info url
#RCMS_DEVICES_NODEINFO = "https://rcmsapi.chinacache.com/nodes"
RCMS_DEVICES_NODEINFO = "https://cms3-apir.chinacache.com/nodes"
RMS_NODE_INFO = "https://ris.chinacache.com/v3/resource/node/businessnodes"

# def get_redis_data(date_str):
#     try:
#         # connect = conn['ref_err_day']
#         DAY_KEYS = '%s*' % date_str
#         result_from_redis = REDIS_CLIENT.keys(DAY_KEYS)
#     except Exception, ex:
#         logger.error(ex)
#     name_dict = {}  # 记录新设备名字
#     # {'CNC-BZ-3-3u4': {'200': 2, '503': 7}}
#     for devs_key in result_from_redis:
#         dev_dic = REDIS_CLIENT.hgetall(devs_key)
#         code_dic = defaultdict(int)
#         code_dic.update(dev_dic)
#         name_dict['%s' % devs_key.split('_')[1]] = code_dic
#     # delete 3 days ago data
#     try:
#         today = datetime.datetime.today()
#         process_date = today - datetime.timedelta(days=3)
#         del_date_str = process_date.strftime('%Y%m%d')
#         key_from_redis = REDIS_CLIENT.keys(del_date_str)
#         for d_key in key_from_redis:
#             REDIS_CLIENT.delete('%s' % d_key)
#     except Exception, ex:
#         logger.error(ex)
#
#     return name_dict


def get_firstLayer_devices():
    got_data =requests.get(RCMS_DEVICES_LAYER)
    first_dives_list = []
    if got_data.status_code == 200:
        got_list = eval(got_data.text)
        first_dives_list = [dev["devName"] for dev in got_list]
    return first_dives_list


# def assemble_node_info():
#     """
#     according rcms, get device node info, re  assemble info
#     :return: {'CHN-BJ-3':{ "cityCode": "0010", "cityName": "BJ", "countryCode": "0086", "countryName": "CN",
#     "ispCode": "01", "ispName": "CHN", "nodeCode": "0100103", "nodeName": "CHN-BJ-3", "nodeNameZh": "北京CHN3",
#     "nodeStatus": "OPEN", "provinceCode": "100000", "provinceName": "BJ", "regionCode": "3", "regionName": "BJ" },
#      'CHN-HZ-1': { "cityCode": "0571", "cityName": "HZ", "countryCode": "0086", "countryName": "CN", "ispCode": "01",
#      "ispName": "CHN", "nodeCode": "0105711", "nodeName": "CHN-HZ-1", "nodeNameZh": "杭州CHN", "nodeStatus": "SUSPEND",
#       "provinceCode": "310000", "provinceName": "ZJ", "regionCode": "8", "regionName": "SH" }}
#     """
#     got_data = requests.get(RCMS_DEVICES_NODEINFO)
#     node_info = {}
#     if got_data.status_code == 200:
#         got_list = eval(got_data.text)
#         for node in got_list:
#             # assemble node info
#             node_info[node['nodeName']] = node
#     return node_info


def assemble_node_info_new():
    """
    {"status":0,"msg":"Request success","data":{"total":1357,"offset":0,"count":1,
    "list":[{"id":10248614,"id_class":"PreservedNode","description":"CHN-GL-a","region":"大陆",
    "description_cn":"桂林CHNa","node_code":"010773a","node_status":"Enable 正常运行","business_type":null,
    "address":"桂林七星区环城北二路东城小区电信大楼5楼机房","bw_limit":80.0,"department":null,"city":"桂林",
    "city_id":903410,"bw_agreement":80.0,"toptier_nodes":[],
    "location":{
    "city":{"id":903410,"description":"桂林","code":"GL","code_number":"0773",
    "notes":"guilin","parent_id":903202},
    "province":{"id":903202,"description":"广西",
              "code":"GX","code_number":"530000","notes":"GuangXi Zone","parent_id":903145},
    "region":{"id":903145,"description":"广州大区","code":"GZ","code_number":"7",
                    "notes":"GuangZhou Region","parent_id":903128},
    "country":{"id":903128,"description":"中国","code":"CN",
              "code_number":"86","notes":"China","parent_id":null}},"servers":null,
    "switchs":null,
    "ipsubnets":null,
    "isp":{"description":"CHN","description_cn":"中国电信","isp_code":"01"}}]}}
    according rcms, get device node info, re  assemble info
    :return: {'CHN-BJ-3':{ "cityCode": "0010", "cityName": "BJ", "countryCode": "0086", "countryName": "CN",
    "ispCode": "01", "ispName": "CHN", "nodeCode": "0100103", "nodeName": "CHN-BJ-3", "nodeNameZh": "北京CHN3",
    "nodeStatus": "OPEN", "provinceCode": "100000", "provinceName": "BJ", "regionCode": "3", "regionName": "BJ" },
     'CHN-HZ-1': { "cityCode": "0571", "cityName": "HZ", "countryCode": "0086", "countryName": "CN", "ispCode": "01",
     "ispName": "CHN", "nodeCode": "0105711", "nodeName": "CHN-HZ-1", "nodeNameZh": "杭州CHN", "nodeStatus": "SUSPEND",
      "provinceCode": "310000", "provinceName": "ZJ", "regionCode": "8", "regionName": "SH" }}
      http://wiki.dev.chinacache.com/pages/viewpage.action?pageId=29555120#id-节点信息接口-获取二级节点信息接口
    """
    try:
        # RMS_NODE_INFO = "https://ris.chinacache.com/v3/resource/node/businessnodes"
        if sys.version_info >= (2, 7, 9):
            ssl._create_default_https_context = ssl._create_unverified_context
        access_id = config.get('rms', 'access_id')
        timestamp= int(time.time())
        # print "timestamp:%s" % timestamp
        # private_key = "4845bdc3e96eade6319fde7582ebe742"
        private_key = config.get('rms', 'private_key')
        token_str = access_id + private_key + str(timestamp)
        logger.debug("token_str:%s" % token_str)
        token = get_md5(token_str)
        # limit = 0  get all info
        rms_node_info_send = RMS_NODE_INFO + '?access_id=' + access_id + '&timestamp=' + str(timestamp) + '&limit=0' '&token=' + token + '&field=location,isp'
        logger.debug("rms_node_info:%s" % rms_node_info_send)
        # context = ssl._create_unverified_context()
        # req = urllib.request.Request(rms_node_info)
        # print "req:%s" % req
        # ssl._create_default_https_context = ssl._create_unverified_context
        # res_data = urllib.request.urlopen(rms_node_info_send, context=context)
        res_data = urllib.request.urlopen(rms_node_info_send)
        res = res_data.read()
        res = json.loads(res)
        return assemble_original_info(res)
    except Exception:
        logger.debug("assemble_node_info_new error:%s" % traceback.format_exc())
        return {}


def assemble_original_info(res):
    """

    :param res: {"status":0,"msg":"Request success","data":{"total":1357,"offset":0,"count":1,
    "list":[{"id":10248614,"id_class":"PreservedNode","description":"CHN-GL-a","region":"大陆",
    "description_cn":"桂林CHNa","node_code":"010773a","node_status":"Enable 正常运行","business_type":null,
    "address":"桂林七星区环城北二路东城小区电信大楼5楼机房","bw_limit":80.0,"department":null,"city":"桂林",
    "city_id":903410,"bw_agreement":80.0,"toptier_nodes":[],
    "location":{
    "city":{"id":903410,"description":"桂林","code":"GL","code_number":"0773",
    "notes":"guilin","parent_id":903202},
    "province":{"id":903202,"description":"广西",
              "code":"GX","code_number":"530000","notes":"GuangXi Zone","parent_id":903145},
    "region":{"id":903145,"description":"广州大区","code":"GZ","code_number":"7",
                    "notes":"GuangZhou Region","parent_id":903128},
    "country":{"id":903128,"description":"中国","code":"CN",
              "code_number":"86","notes":"China","parent_id":null}},"servers":null,
    "switchs":null,
    "ipsubnets":null,
    "isp":{"description":"CHN","description_cn":"中国电信","isp_code":"01"}}]}}
    :return: {'CHN-BJ-3':{ "cityCode": "0010", "cityName": "BJ", "countryCode": "0086", "countryName": "CN",
    "ispCode": "01", "ispName": "CHN", "nodeCode": "0100103", "nodeName": "CHN-BJ-3", "nodeNameZh": "北京CHN3",
    "nodeStatus": "OPEN", "provinceCode": "100000", "provinceName": "BJ", "regionCode": "3", "regionName": "BJ" },
     'CHN-HZ-1': { "cityCode": "0571", "cityName": "HZ", "countryCode": "0086", "countryName": "CN", "ispCode": "01",
     "ispName": "CHN", "nodeCode": "0105711", "nodeName": "CHN-HZ-1", "nodeNameZh": "杭州CHN", "nodeStatus": "SUSPEND",
      "provinceCode": "310000", "provinceName": "ZJ", "regionCode": "8", "regionName": "SH" }}
    """
    map_re = {}
    try:
        if res:
            data = res.get('data').get('list')
            if data:
                for node_info in data:
                    temp_result = {}
                    temp_result['nodeName'] = node_info.get('description')
                    temp_result['nodeNameZh'] = node_info.get('description_cn')
                    temp_result['nodeCode'] = node_info.get('node_code')
                    temp_result['nodeStatus'] = node_info.get('node_status')
                    temp_result['cityName'] = node_info.get('location').get('city').get('code')
                    temp_result['cityCode'] = node_info.get('location').get('city').get('code_number')
                    temp_result['provinceName'] = node_info.get('location').get('province').get('code')
                    temp_result['provinceCode'] = node_info.get('location').get('province').get('code_number')
                    temp_result['regionName'] = node_info.get('location').get('region').get('code')
                    temp_result['regionCode'] = node_info.get('location').get('region').get('code_number')
                    temp_result['countryName'] = node_info.get('location').get('country').get('code')
                    temp_result['countryCode'] = node_info.get('location').get('country').get('code_number')
                    temp_result['ispName'] = node_info.get('isp').get('description')
                    temp_result['ispCode'] = node_info.get('isp').get('isp_code')
                    map_re[temp_result['nodeName']] = temp_result
        return map_re
    except Exception:
        logger.debug("assemble_original_info error:%s" % traceback.format_exc())
        return map_re


def get_md5(str_1):
    """

    :param str_1:
    :return:
    """
    try:
        m2 = hashlib.md5()
        m2.update(str_1)
        logger.debug("md5:%s" % m2.hexdigest())
        return m2.hexdigest()
    except Exception:
        logger.debug("get_md5 error:%s" % traceback.format_exc())


def get_node_name(device_name):
    """
    according device name, get node name
    :param device_name: CNC-BZ-3-3u4
    :return: CNC-BZ-3
    """
    if device_name:
        arr = device_name.split('-')
        while len(arr) >= 4:
            del arr[3]
        return '-'.join(arr)
    else:
        logger.debug("get_rcms_device_type get_node_name device_name is null")
        return None


def get_device_type():
    dev_type={}
    dev_list=[]
    # for dev in devices:
    #     get_url = RCMS_API.format(dev)
    db = q_db
    for num in range(50):
        try:
            null = None
            # got_data =urllib.urlopen("http://rcmsapi.chinacache.com:36000/devices").read()
            got_data =requests.get(RCMS_DEVICES)
            if got_data.status_code == 200:
                got_list = eval(got_data.text)
                try:
                    db["device_app"].drop()
                except:
                    db.drop_collection("device_app")
                    # con = MongoClient(uri)['bermuda']
                    # con["device_app"].drop()
                break
            else:
                print(got_data.status_code)
                continue
        except Exception:
            print(222, traceback.format_exc())
            logger.debug("get fail")
            continue
    logger.debug("get end")
    first_dives_list = get_firstLayer_devices()
    date = datetime.datetime.now()
    # get node info
    node_info = assemble_node_info_new()
    for dev in got_list:
        devapp={}
        try:
            if "appList" in dev:
                devapp["name"]=dev["devName"]
                devapp["host"]=dev["devAdminIP"]
                devapp["status"]=dev["devStatus"]
                if dev["devName"] in first_dives_list:
                    devapp["firstlayer"] = True
                else:
                    devapp["firstlayer"] = False
                if 'FC' in dev["appList"]:
                    devapp["type"]='FC'
                elif 'HPCC' in dev["appList"]:
                    devapp["type"]='HPCC'
                else:
                    devapp["type"]='unknown'
                devapp["devCode"] = dev["devCode"]
                devapp["date"] = date
                # add node info
                node_name = get_node_name(devapp['name'])
                if node_name in node_info:
                    devapp.update(node_info[node_name])
                try:
                    db["device_app"].insert(devapp)
                    # conn["device_app"].update({'name':devapp["name"],'type':devapp["type"]},{'$set':devapp},
                    #                                 upsert=True)
                except Exception:
                    print(traceback.format_exc())
                    logger.error(traceback.format_exc())
                try:
                    DEVICE_TYPE.hmset("DEVICE_TYPE", {devapp["name"]: devapp["type"]})
                except Exception:
                    logger.error(traceback.format_exc())
        except:pass
    # logger.debug(devapp)
    #
    # return devapp

if __name__ == '__main__':
    get_device_type()
    print("end")
    logger.debug('end')
    os._exit(0)
