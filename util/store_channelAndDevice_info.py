#! /usr/bin/env python
# -*- coding: utf-8 -*-

import urllib.request, urllib.error, urllib.parse
import json
import datetime
# from pymongo import MongoClient
import redis
from core import database

# conn = MongoClient('mongodb://superAdmin:admin_refresh@223.202.52.82:27017/')
# db = conn.bermuda
db = database.query_db_session()
docUrl = 'data'  
#insert into table preload_channel   url
#preUrl = 'https://rcmsapi.chinacache.com/customer/'
preUrl = 'https://cms3-apir.chinacache.com/customer/'
userName = 'duowan2'
lastUrl = '/channels'
#tableName = 'test_rubin'
    

#insert into table preload_config_device url
#preCode = 'https://rcmsapi.chinacache.com//channel/'
preCode = 'https://cms3-apir.chinacache.com//channel/'
lastCode = '/flexicache/firstlayer'

#连接redis数据库
REDIS_CLIENT = redis.StrictRedis(host='%s' % '223.202.52.82', port=6379, db=5)

class PraseJson(object):
    def __init__(self,preUrl, userName, lastUrl, db, tableName, preCode,
    lastCode, channel_list):
        #not use tableName
        self.preUrl = preUrl
        self.userName = userName
        self.lastUrl = lastUrl
        self.url = preUrl + userName + lastUrl  #form a new url
        self.db = db                        #connect to mongodb 
        #self.tableName = tableName              #the name to the table in mongodb
        self.preCode = preCode                  #url parameter  for code
        self.lastCode = lastCode                #url patameter  for code last part
        self.channel_list = channel_list        #usr'channel list


    def registerUrl(self):
        try:
            data = urllib.request.urlopen(self.url).read()
            #print data
            self.praserJsonData(data)
            #return data
        except Exception:
            print(e)

    def registerUrl_code(self, username, channel_name, channel_code):
        
        try:
            #print self.preCode+code+self.lastCode
            data = urllib.request.urlopen(self.preCode+channel_code+self.lastCode).read()
            #print data
            self.praserJsonDataFor_code(data, username, channel_name,  channel_code)
        except Exception:
            print(e)
    
    #Parsing json data from the network
    def praserJsonData(self,jsonData):
        value = json.loads(jsonData)
        channel_listT = []
         
        #print value
        for kAndV in value:
            username = kAndV['customerName']
            channel_code = kAndV['code']
            channel_name = kAndV['name']
            #code = kAndV['code']
            channel_listT.append(channel_name)
            #print username
            #print channel_code
            #print channel_name
            if channel_name in self.channel_list:
                #判断channel_name 如果在本地文件的列表中，进行插入数据库操作
                self.insertMongo(username, channel_code, channel_name) #user info   insert into database
                self.registerUrl_code(username, channel_name, channel_code)
            else:
                print('at username:', username,channel_name, 'not in channel_list')

             
    #Parsing json data from the network  code partion
    def praserJsonDataFor_code(self, data, username, channel_name, channel_code):
        value = json.loads(data)
        #print value
        code = value['code']
        #print cod
        print(username)
        deviceList = value['devices']
        if deviceList:
            for deviceInfo in deviceList:
                
                #print deviceInfo
                result = {}
                result['username'] = username
                #print username
                
                result['status'] = deviceInfo['status']
                #print deviceInfo['status']
                result['name'] = deviceInfo['name']
                #print deviceInfo['name']
                result['channel_name'] = channel_name
                #print channel_name
                result['host'] = deviceInfo['host']
                #print deviceInfo['host']
                result['firstLayer'] = deviceInfo['firstLayer']
                #print deviceInfo['firstLayer']
                result['channel_code'] = channel_code
                #print channel_code
                self.db.preload_config_device.update({'name':deviceInfo['name'],'channel_name':channel_name},{'$set':result},
                                                    upsert=True)         
                #device info  insert into database
                #self.db.preload_config_device.update({},{'$set':result}, upsert:True)         
                print('through username  update  table preload_config_device the data is ',result)
                
        else:
            print(code,'the device is empty')
            
                
        

    #insert infomation into the mongodb  database
    def insertMongo(self, username,channel_code,channel_name):
        """
        parameter  username :the name of user
        parameter  channel_code: the code of channel 
        parameter  channel_name: the url of the channel
        insert this info into the database

        return:
        """
        #print "ma"
        result = {}
        result["username"] = username
        result["channel_name"] = channel_name
        result["regin"] = []
        result["callback"] = {"url":"", "email":[]}
        result["is_live"] = 0
        result["create_time"] =  datetime.datetime.now()
        result["config_count"] = 500
        result["type"] = 0
        result["has_callback"] = 0
        result["channel_code"] = channel_code
        #此处连接preload_channel,做一个判断，判断是否在数据库中，如果在数据库，不需要操作，如果不在数据哭库，插入数据库信息
        re = self.db.preload_channel.find_one({'username':username, 'channel_name': channel_name})
        if not re:  #数据库中不存在记录，需要进行插入操作
            self.db.preload_channel.insert(result)
            #把信息插入redis数据库
            REDIS_CLIENT.set(channel_name, 500)
        else:
            print('数据库中已经存在，不需要更改')

class ReadText(object):
    def __init__(self, url):
        self.userNames = [] #user lsit
        self.user_channel_dic = {}  #the list of user'channel
        self.url = url               #the url of document

    def processDocument(self):
        print(self.url)
        # file_object = open(self.url)
        count = 0
        with open(self.url) as file_object:
        # try:
            for line in file_object:
                nameAndChannel = line.split()
                if nameAndChannel[0] not in self.userNames:
                    self.userNames.append(nameAndChannel[0])
                    self.user_channel_dic[nameAndChannel[0]] = [nameAndChannel[1]]
                    # self.user_channel_list[nameAndChannel[0]].append(nameAndChannel[1])
                else:
                    self.user_channel_dic[nameAndChannel[0]].append(nameAndChannel[1])
        # finally:
        #     file_object.close()
        #





def run_main():
    rc = ReadText(docUrl)
    rc.processDocument()
    #print rc.user_channel_list
    if rc.user_channel_dic:
        for k in rc.user_channel_dic:
            """
            for value in rc.user_channel_dic[k]:
                print value,'and',k
            """
            rc1 = PraseJson(preUrl, k, lastUrl, db, "test_rubin", preCode,
            lastCode, rc.user_channel_dic[k])
            rc1.registerUrl()


if __name__ == '__main__':
    run_main()
    exit()
