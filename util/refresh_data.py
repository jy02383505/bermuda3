#encoding=utf-8

#from pymongo import ReplicaSetConnection, ReadPreference, Connection
from datetime import datetime, timedelta
from core.database import query_db_session
import threading
import sys, os, subprocess, shutil
import imp
imp.reload(sys) 
sys.setdefaultencoding('utf8')

# Try and reduce the stack size.
try:
    threading.stack_size(409600)
except:
    pass


class RefreshData(threading.Thread):
    def __init__(self,dir_root,dir_name,strDate):
        self.dir_root = dir_root
        self.dir_name = dir_name
        self.strDate = strDate
        threading.Thread.__init__(self)

    def run(self):
        make_refresh_dir(self.dir_root,self.dir_name)
        global  mutex
        threads = []
        # 创建一个锁
        mutex = threading.Lock()
        # 先创建线程对象
        for x in range(0, 24):
            threads.append(threading.Thread(target=saveData, args=(x,self.dir_root,self.dir_name,self.strDate,)))
        # 启动所有线程
        for t in threads:
            t.start()
        # 主线程中等待所有子线程退出
        for t in threads:
            t.join()  
        tar_refresh_dir(self.dir_root,self.dir_name)
        print("all task retry over!")


def getRConnection():
    return query_db_session()
    # return ReplicaSetConnection('%s:27017,%s:27017' % ('172.16.21.28','172.16.21.29'), replicaSet = 'bermuda_db')['bermuda']
    #return Connection("127.0.0.1",27017)['bermuda']

def saveFile(dir_root,dir_name,file_name,list_of_text_strings):
    file_object = open(dir_root+dir_name+"/"+file_name, 'wb')
    file_object.writelines(list_of_text_strings)
    file_object.close()

def saveData(num,dir_root,dir_name,strDate):
    c = threading.RLock()
    with c:
        dt = datetime.strptime(strDate, "%Y-%m-%d")
    file_name = strDate + "_" + str(num)+".log"
    print("log begin " + file_name)
    query = {'created_time':{"$gte":(dt + timedelta(hours=num)), "$lt":(dt + timedelta(hours=num+1))}}
    rd = getRConnection()
    flag = 0
    url_list_text = ""
    for url in rd.url.find(query):
        try:
            flag +=1
            url_list_text += (str(url.get('username',"")).encode('utf8') + "\t" + str(url.get("channel_code","")).encode('utf8') +"\t" + str(url.get("url","")).encode('utf8') + "\t" + str(url.get("isdir","")).encode('utf8') + "\t" + str(url.get("is_multilayer","")).encode('utf8') + "\t" + str(url.get("created_time","")).encode('utf8') + "\t" + str(url.get("finish_time","")).encode('utf8') +"\n")
            if flag%2000 == 0:
                    saveFile(dir_root,dir_name,file_name,url_list_text)
        except Exception:
            print(e)
    try:
        saveFile(dir_root,dir_name,file_name,url_list_text)
    except Exception:
        print(e)

def make_refresh_dir(dir_root,dir_name):
    try:
        os.mkdir(dir_root+dir_name)
    except Exception:
        shutil.rmtree(dir_root+dir_name)
        os.mkdir(dir_root+dir_name) 

def tar_refresh_dir(dir_root,dir_name):
    handle = subprocess.Popen('cd %s && tar -zcvf %s.tar.gz %s'%(dir_root,dir_name,dir_name), stdout=subprocess.PIPE, shell=True) 
    #if len(handle.stdout.readlines())==25:
    #    remove_refresh_dir(dir_root,dir_name)

def remove_refresh_dir(dir_root,dir_name):
    try:
        shutil.rmtree(dir_root+dir_name) 
        print(datetime.now())
    except Exception:
        print(e)

if __name__ == '__main__':
    print(datetime.now())
    dt = datetime.now()-timedelta(days=1)
    dir_root = "/Application/refresh/"
    dir_name ="refresh"+dt.strftime("%m%d") 
    strDate = dt.strftime("%Y-%m-%d")
    print(strDate)
    refresh = RefreshData(dir_root,dir_name,strDate)
    refresh.setName('refresh')
    refresh.setDaemon(True)
    refresh.run()
