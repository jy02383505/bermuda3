#! /usr/bin/env python
# -*- coding: utf-8 -*-
__author__ = 'vance'
__date__ = '15-11-5'

import datetime
import logging
import os
import simplejson as json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from core import redisfactory
from bson import ObjectId
from core import database
from util.emailSender import EmailSender
import traceback

# try:
#     from pymongo import Connection as MongoClient
# except:
#     from pymongo import MongoClient

LOG_FILENAME = '/Application/bermuda3/logs/monitor_region_devs.log'
# logging.basicConfig(filename=LOG_FILENAME,
#                     format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s',
#                     level=logging.INFO)
# db = MongoClient("mongodb://bermuda:bermuda_refresh@223.202.52.135/bermuda", 27017)['bermuda']
db = database.query_db_session()
formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s")
fh = logging.FileHandler(LOG_FILENAME)
fh.setFormatter(formatter)

logger = logging.getLogger('monitor_region_devs')
logger.addHandler(fh)
logger.setLevel(logging.DEBUG)
preload_cache = redisfactory.getDB(1)
PRELOAD_DEVS = redisfactory.getDB(5)
MONITOR_CHANNEL = ["18684"]
# ads_to = ['di.huang@chinacache.com','wanghui@chinacache.com','chunjing.li@chinacache.com','shuai.zhang@chinacache.com','jiansan.qi@chinacache.com','huan.ma@chinacache.com','hongan.zhang@chinacache.com']
ads_to = ['huan.ma@chinacache.com']
ads_from = 'nocalert@chinacache.com'


def get_result_by_id(url_id):
    try:
        result = preload_cache.get(url_id)
        if result:
            return json.loads(result)
        else:
            return db.preload_result.find_one({"_id": ObjectId(url_id)})
    except Exception:
        logger.error(e)
        return {}


def calRegionDevicePer(reg_count, fail_count):
    try:
        logger.debug("%d-%d" % (reg_count, fail_count))
        if round(float(fail_count) / float(reg_count), 2) > 0.2:
            return True
        else:
            return False
    except:
        return False


def process_url(url):
    # global REG_CHAN_MAP
    try:
        get_data = get_result_by_id(str(url["_id"]))["devices"]
    except Exception:
        logger.error(traceback.format_exc())
        logger.error(url["_id"])
        return "", []
    channel_code = str(url["channel_code"])
    region_devs = PRELOAD_DEVS.get(channel_code)
    fail_devs = []
    dev_list = []
    for k, v in list(get_data.items()):
        if v["preload_status"] != 200:
            dev = {"host": v.get('host')}
            dev_list.append(v.get('host'))
            fail_devs.append(dev)
    reg_name_list = []
    reg_host_list = []

    try:
        [(reg_name_list.append(dd['name']), reg_host_list.append(dd['host'])) for dd in
         json.loads(region_devs)]
        fail_region_devs = list(set(reg_host_list).intersection(set(dev_list)))
        if fail_region_devs and calRegionDevicePer(len(reg_name_list), len(fail_region_devs)):
            # report_task(channel_code, region_channel_map, url)
            logger.debug(fail_region_devs)
            return url["url"], fail_region_devs
        return "", []
    except Exception:
        logger.error(traceback.format_exc())
        logger.error("error code:%s" % url["channel_code"])


def getCallbackData(start_time, end_time):
    count = db.callback.find({"reponse": {"$ne": "ok"}, "create_time": {"$gte": start_time, "$lte": end_time}}).count()
    return count


# 发邮件
def send(from_addr, to_addrs, subject, content):
    # msg = MIMEText(content)
    msg = MIMEMultipart()
    # att1 = MIMEText(open('%scount_device_status_output%s.xls' % (LOG_DIR, date_str), 'rb').read(), \
    #                 'base64', 'utf-8')
    # att1['Content-Type'] = 'application/octet-stream'
    # att1['Content-Disposition'] = 'attachment;filename="%scount_device_status_output%s.xls"' % (LOG_DIR, date_str)
    # msg.attach(att1)
    # from_addr = 'nocalert@chinacache.com'
    msg['Subject'] = subject
    msg['From'] = from_addr
    msgText = MIMEText(content, 'html', 'utf-8')
    msg.attach(msgText)
    if type(to_addrs) == str:
        msg['To'] = to_addrs
    elif type(to_addrs) == list:
        msg['To'] = ','.join(to_addrs)

    e_s = EmailSender(from_addr, to_addrs, msg)
    r_send = e_s.sendIt()
    if r_send != {}:
        # s = smtplib.SMTP('corp.chinacache.com')
        s = smtplib.SMTP('anonymousrelay.chinacache.com')
        try:
            s.ehlo()
            s.starttls()
            s.ehlo()
        except Exception:
            pass
        # s.login('noreply', 'SnP123!@#')
        s.sendmail(from_addr, to_addrs, msg.as_string())
        s.quit()


def process_data(now):
    theader = '<th>时间</th><th>失败任务</th><th>接收任务</th><th>回调任务</th><th>失败重点设备</th>'
    trs = []
    fail_dev_list = []
    failTotal = 0
    receiverTotal = 0
    callbackTotal = 0
    failDevTotal = 0
    cur_time = datetime.datetime.combine(now.date(), now.time().replace(hour=0, minute=0, second=0, microsecond=0))
    if now.hour == 0:
        cur_time = cur_time - datetime.timedelta(days=1)
    for h in range(24):
        tr = []
        if h >= now.hour and now.hour != 0:
            break
        timeStr = "%d-%d" % (h, h + 1)
        pre_time = cur_time + datetime.timedelta(hours=h)
        last_time = cur_time + datetime.timedelta(hours=h + 1)
        # logger.info('begin_date:%s  end_date:%s' % (pre_time, last_time))
        call_num, faild_num, need_num, fail_dev_list = getDataCount(last_time, pre_time)
        fail_devs = ""
        if fail_dev_list:
            fail_devs = ','.join(fail_dev_list)
        logger.debug("%s-%s-%s-%s" % (h, call_num, faild_num, need_num))
        tr.append('<td>{0}</td><td>{1}</td><td>{2}</td><td>{3}</td><td>{4}</td>'.format(timeStr, faild_num, need_num,
                                                                                        call_num, fail_devs))
        trs.append(''.join(tr))
        failTotal += faild_num
        receiverTotal += need_num
        callbackTotal += call_num

    trs.append(
        '<th>总计:</th><th>{0}</th><th>{1}</th><th>{2}</th><th></th>'.format(failTotal, receiverTotal, callbackTotal))
    table = '<table border="1">\n<thead><tr>{0}</tr></thead>\n<tbody>\n<tr>{1}</tr></tbody></table>'.format(theader,
                                                                                                            '</tr>\n<tr>'.join(
                                                                                                                trs))
    return table, fail_dev_list


def run():
    now = datetime.datetime.now()
    start_str = 'start script on {datetime}'.format(datetime=now)
    logger.info(start_str)
    # # cur_time = datetime.datetime.combine(now.date(), now.time().replace(minute=0, second=0, microsecond=0))
    # cur_time = now
    # pre_time = cur_time - datetime.timedelta(hours=2)
    # last_time = cur_time - datetime.timedelta(hours=1)
    # # last_time = cur_time + datetime.timedelta(hours=0)
    table, fail_dev_list = process_data(now)
    content = 'Hi,ALL:<br/><br/>cztv每日任务统计表:<br/><br/>' \
              '日期:%s<br/><br/>' % now.strftime('%Y-%m-%d')
    content += table

    # content += '<br/><br/>重点区域失败设备:<br/>'
    # content += '{0}'.format(','.join(fail_dev_list))
    # content = 'Hi,ALL:<br/><br/>时间:{0}-{1}<br/>接收任务:{2}<br/>失败任务:{3}<br/>回调数量:{4}，<br/>'.format(pre_time.strftime('%Y-%m-%d %H:%M:%S'),last_time.strftime('%Y-%m-%d %H:%M:%S'),need_count,len(faild_url_list),call_num)
    send(ads_from, ads_to, 'cztv 每小时监控邮件', content)
    exit()


def getDataCount(last_time, pre_time):
    logger.info('begin_date:%s  end_date:%s' % (pre_time, last_time))
    ind_url_dic = {"channel_code": {"$in": MONITOR_CHANNEL}, "created_time": {"$gte": pre_time, "$lt": last_time}
                   }  # "finish_time": {"$exists": "true"}
    channel_urls = db.preload_url.find(ind_url_dic, no_cursor_timeout=True)
    need_count = channel_urls.count()
    logger.debug("url count:%d" % need_count)
    if need_count == 0:
        return 0, 0, 0, []
    faild_url_list = []
    fail_dev_list = []
    for url in channel_urls:
        u, fail_devs = process_url(url)
        if u:
            faild_url_list.append(u)
            fail_dev_list = list(set(fail_dev_list).union(set(fail_devs)))
    call_num = getCallbackData(pre_time, last_time)
    return call_num, len(faild_url_list), need_count, fail_dev_list


if __name__ == '__main__':
    run()
    os._exit(0)
