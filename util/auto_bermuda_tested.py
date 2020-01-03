# -*- coding:utf-8 -*-
'''
Created on 2011-6-7

@author: wenwen
'''
import urllib.request, urllib.parse, urllib.error
from random import Random
from multiprocessing import Process
import http.client
import datetime
from core.database import query_db_session
import time
from bson import ObjectId
import sys,os
import logging
from tests.auto_bermuda_test import do_post


if __name__ == '__main__':
    helpstr  = '-----------------------------\n'
    helpstr += 'TEST ORDER\n'
    helpstr += '\t exit          press exit \n'
    helpstr += '\t help          press 0 \n'
    helpstr += '\t url_single    press 1 \n'
    helpstr += '\t url_double    press 2 \n'
    helpstr += '\t url_duplicat  press 3 \n'
    helpstr += '\t url_rewrite   press 4 \n'
    helpstr += '-----------------------------\n'
    print(helpstr)
    server = "127.0.0.1"
    while True:
    #params = urllib.urlencode({'username': 'sina_t', 'password': 'MTE3YjU2ZTlhNmNl', 'task': '{"dirs":["http://ww1.sinaimg.cn/bmiddle/test/cooler/"]}'})
    #params = urllib.urlencode({'username': 'geili', 'password': '!WPR)ymL', 'task': '{"dirs":["http://imgcc01.geilicdn.com/taobao21422880516*"],"callback":{"email":["peng.zhou@chinacache.com","418435432@qq.com"],"acptNotice":true}}'})
    #params = urllib.urlencode({'username': 'snda', 'password': 'ptyy@snda.com', 'task': '{"urls":["http://dl.autopatch.ccgslb.net/test/a.jpg","http://dl.autopatch.ccgslb.net/test/b.jpg"]}'})
    #Process(target = do_post,args=(params,server,)).start()
        str_input =  input()
        print("----------------------------------")
        if str_input == "exit":
            print("test over !")
            break
        elif str_input == "help" or str_input == "0":
            print(helpstr)
        elif str_input == "1":
            params = urllib.parse.urlencode({'username': 'duowan', 'password': '5VGO3LB62O', 'task': '{"urls":["http://web.duowan.com/51seer/jingling/img/1361.jpg"]}'})
            Process(target = do_post,args=(params,server,"url_single")).start()
        elif str_input == "2":
            params = urllib.parse.urlencode({'username': 'duowan', 'password': '5VGO3LB62O', 'task': '{"urls":["http://web.duowan.com/51seer/jingling/img/cooler1.jpg","http://web.duowan.com/51seer/jingling/img/cooler2.jpg"]}'})
            Process(target = do_post,args=(params,server,"url_double")).start()
        elif str_input == "3":
            params = urllib.parse.urlencode({'username': 'duowan', 'password': '5VGO3LB62O', 'task': '{"urls":["http://web.duowan.com/51seer/jingling/img/1361.jpg","http://web.duowan.com/51seer/jingling/img/1361.jpg"]}'})
            Process(target = do_post,args=(params,server,"url_duplicat")).start()
        elif str_input == "4":
            params = urllib.parse.urlencode({'username': 'chinabroadcast', 'password': 'wt6hj8', 'task': '{"urls":["http://iphone.cri.cn/aFFDD.jpg"]}'})
            Process(target = do_post,args=(params,server,"url_rewrite")).start()
        else:
            print(helpstr)


