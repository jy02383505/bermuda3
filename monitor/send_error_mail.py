# encoding=utf-8
'''
Created on 2012-9-28

@author: cooler
'''
import sys
import imp
imp.reload(sys)
from core import sendEmail
sys.setdefaultencoding('utf8')
sys.path.append('/Application/bermuda3/')
import simplejson as json


import logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s',filename='/Application/bermuda3/logs/error_mail.log')
logger = logging.getLogger('monitor')
logger.setLevel(logging.DEBUG)

def send(db,tasks):
    logger.debug( "init error_email start ....")
    try:
        for channel_code,tasks in merge(tasks).items():
            logger.debug("send mail begining...")
            #logger.debug("get_addr:%s ,content:%s" % (get_addr(db,channel_code),get_content(tasks)))
            sendEmail.send(get_addr(db,channel_code), "刷新失败任务报警", get_content(tasks))
            logger.debug( "send mail ending...")
    except Exception:
        logger.debug("send mail error:%s!" % e)

def get_content(tasks):
    content = "以下刷新任务，有个别设备经过重试仍未完成。请登录刷新管理平台查询详细信息，地址: http://223.202.45.197 。\n"
    task_dict = {}
    for task in tasks:
        task_dict.setdefault(task.get("host"),[]).append(task)
    for host in list(task_dict.keys()):
        content += "失败设备 IP : %s \n" % host
        tmp_url = []
        for task in task_dict.get(host):
            for url in task.get("urls"):
                if url.get('url') in tmp_url:
                    continue
                content += "该设备失败的刷新任务 : %s ,所属用户 : %s \n" % (url.get('url'),url.get('username'))
                tmp_url.append(url.get('url'))
    return content

def merge(tasks):
    task_dict = {}
    for task in tasks:
        task = json.loads(task)
        task_dict.setdefault(task.get("channel_code"),[]).append(task)
    return task_dict


def get_addr(db,channel_code):
    try:
        name = db.rcms_channel.find_one({"channelCode":channel_code}).get("customerDirector")
        user = db.rcms_user_enabled.find_one({"userName":name})
        return [user.get("loginName")+"@chinacache.com","li.chang@chinacache.com",'likun.mo@chinacache.com']
    except:
        return ["li.chang@chinacache.com",'likun.mo@chinacache.com']

def run(db,bodys):
    try:
        logger.debug(bodys)
        send(db,bodys)
    except Exception:
        logger.debug("run send mail error:%s!" % e)


if __name__ == "__main__":
    pass
