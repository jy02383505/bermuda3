# -*- coding:utf-8 -*-
'''
Created on 2013-9-28

@author: cl
'''
import sys
import  threading , time, traceback
from datetime import datetime, timedelta
from core import database,postal,sendEmail

try:
    threading.stack_size(409600)
except:
    pass

import logging
logging.basicConfig(format='%(asctime)s %(levelname)s - %(message)s', filename='/Application/bermuda3/logs/icbc_monitor.log')
logger = logging.getLogger('monitor')
logger.setLevel(logging.DEBUG)
adminAdd = ['huan.ma@chinacache.com', 'zehao.ma@chinacache.com','nan.zhou@chinacache.com','xiaobing.sun@chinacache.com','jiansan.qi@chinacache.com','feifei.yang@chinacache.com','lingyun.tang@chinacache.com','cc.icbc@chinacache.com']

class Monitor(threading.Thread):
    def __init__(self , db,customerName='icbc'):
        self.db = db
        self.customerName = customerName
        threading.Thread.__init__(self)

    def run(self):
        while True:
            logger.debug("monitor begining.....")
            urls = self.getCustomerUrl(self.customerName)
            logger.debug("%s has %s urls"%(self.customerName,len(urls)))
            toaddrs = adminAdd + ["huan.ma@chinacache.com"]
            logger.debug("%s Monitor_Email: %s "% (self.customerName,str(toaddrs)))
            self.send_mail(urls,toaddrs)
            logger.debug("monitor ending.....")
            time.sleep(60)

    def send_mail(self,urls,toaddrs):
        devs_dict = self.get_error_devs(urls)
        logger.debug("%s devs_dict: %s , urlList_len:%s "% (self.customerName,len(devs_dict),len(urls)))
        if devs_dict:
            mailContent = self.initMailContent(urls,devs_dict)
            subject = "**"+self.customerName+"刷新失败列表**"
            try:
                sendEmail.send(toaddrs, subject, mailContent.encode('utf8'))
                logger.debug("%s send email! " %(self.customerName))
            except Exception:
                logger.error(traceback.format_exc())

    def get_error_devs(self,urls):
        devs_dict = {}
        tmp = {}
        for url in urls:
            tmp.setdefault(url.get("dev_id"),[]).append(url)
            self.updateUrl(url)
        for dev_id in list(tmp.keys()):
            devices = self.db.device.find_one({"_id": dev_id }).get('devices')
            for dev in list(devices.keys()):
                if devices.get(dev).get("code") > 204 :
                    devs_dict.update(self.retry(devices.get(dev),tmp.get(dev_id)))
        return devs_dict

    def retry(self,dev,urls):
        logger.debug("do retry dev: %s , urlList_len:%s "% (dev.get("host"),len(urls)))
        for i in range(3):
            if urls[0].get("'isdir"):
                session_id,command = postal.getDirCommand(urls)
            else:
                command = postal.getUrlCommand(urls)
            results, wrongRet = postal.doSend_HTTP([{"host": dev.get("host")}],command)
            if results:
                logger.debug("%s retry finished! , urlList_len:%s "% (dev.get("host"),len(urls)))
                return  {}
        return {dev.get("name"):urls}

    def initMailContent(self,urls,devs_dict):
        mailContent = "失败设备 : \n"
        for device in list(devs_dict.keys()):
            mailContent += device + ":\n"
            for url in devs_dict.get(device):
                mailContent += url.get("url")+"\n"
            mailContent += "\n"
        logger.debug(mailContent)
        return mailContent

    def getCustomerUrl(self,username):
        return [url for url in self.db.url.find({"username":username,"status":'FINISHED', "isMonitor":None,'created_time': {'$gte': datetime.now() - timedelta(minutes=20)}})]

    def updateUrl(self, url):
        url["isMonitor"] = 0
        self.db.url.save(url)

if __name__ == "__main__":
    monitor = Monitor(database.db_session())
    monitor.setName('customer_monitor')
    monitor.setDaemon(True)
    monitor.run()
