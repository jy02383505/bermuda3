#! /usr/bin/env python
# -*- coding: utf-8 -*-
__author__ = 'vance'
__date__ = '6/15/15'

import codecs
from core.config import config
# try:
#     from pymongo import ReplicaSetConnection as MongoClient
# except:
#     from pymongo import MongoClient as MongoClient
import logging
import traceback
from core.database import db_session
import os

file_path = config.get('success_definition_strategy', 'basic_info_file')

# uri ='mongodb://bermuda:bermuda_refresh@%s:27017,%s:27017,%s:27017/bermuda?replicaSet=bermuda_db' % ('172.16.12.136', '172.16.12.135', '172.16.12.134')
# uri = 'mongodb://bermuda:bermuda_refresh@%s:29017/bermuda' %('172.16.21.205')
# conn_url = MongoClient(uri)['bermuda']
conn_url =db_session()

LOG_FILENAME = '/Application/bermuda3/logs/basic_info.log'
logging.basicConfig(filename=LOG_FILENAME,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger('basic_info')
logger.setLevel(logging.DEBUG)

def get_basic_info():
    fp = codecs.open(file_path,'r',encoding='utf-8')
    basic_info=[]
    key_list = ['Province','City','Zone','Provinc']
    for line in fp:
        info_dic ={}
        line = line.strip()
        tmp_list = line.split('\t')
        if len(tmp_list) < 6: continue
        name = tmp_list[0].strip()
        name_list = name.split('-')
        use_name = '-'.join([name_list[0].strip(),name_list[1].strip()])
        #name isp city province region country,using the \t to seperate from each other
        province = tmp_list[3].strip()
        s=province.replace(" ", "")
        try:
            province = [s.split(k)[0]  for k in key_list  if k in s ][0]
        except:
           # print s
            province = s
        if province in ['ShanXi']:
            reg = tmp_list[4].strip()
            province = '{0}_{1}'.format(province,reg.split(' ')[0])
        info_dic = {'name': use_name, 'isp': tmp_list[1].strip(), 'city': tmp_list[2].strip(),
                    'province': province, 'region': tmp_list[4].strip(), 'country': tmp_list[5].strip()}
        basic_info.append(info_dic)
    return basic_info

def insert_basic_info(data):
    try:
        collection_basic = conn_url['device_basic_info']
        collection_basic.drop()
    except Exception:
        logger.error(traceback.format_exc())
    # logger.debug('process {0}'.format(data['uid']))
    # self.collection_err.insert(data)
    result = collection_basic.insert(data)


def get_all_province():
    print(conn_url.device_basic_info.distinct('province'))

if __name__ == '__main__':
    basic_info = get_basic_info()
    insert_basic_info(basic_info)
    # get_all_province()
    os._exit(0)