#!-*- coding=utf-8 -*-
"""
@author: rubin
@create time: 2016/6/22  16:25
scanning device_link Collection, during a certain period of time,
"""

import os
# import sys
# from pymongo import MongoClient
import datetime
import logging
import urllib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from core import database
from util.tools import get_email_list_by_type
from util.emailSender import EmailSender
# # 解决编码问题
# reload(sys)
# sys.setdefaultencoding('utf8')

LOG_FILENAME = '/Application/bermuda3/logs/device_link.log'
# LOG_FILENAME = '/home/rubin/logs/device_link.log'

# logging.basicConfig(filename=LOG_FILENAME,
#                     format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s',
#                     level=logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s")
fh = logging.FileHandler(LOG_FILENAME)
fh.setFormatter(formatter)
logger = logging.getLogger('device_link')
logger.addHandler(fh)
logger.setLevel(logging.DEBUG)


# connect 82 server
# con83 = MongoClient('mongodb://superAdmin:admin_refresh@223.202.52.82:27017/')
# con83 = MongoClient('mongodb://bermuda:bermuda_refresh@223.202.52.82:27018/bermuda')
# db = con83.bermuda


# 链接mongo 句柄
db = database.query_db_session()

# the email come from
email_from = 'nocalert@chinacache.com'

# mail recipient list
# email_to = get_email_list_by_type('alarm_link_failed_devices')
# if not email_to:
#     email_to = ['huan.ma@chinacache.com', 'junyu.guo@chinacache.com', 'longjun.zhao@chinacache.com']
# test
# email_to = ['huan.ma@chinacache.com', 'longjun.zhao@chinacache.com']
# email_to = ['huan.ma@chinacache.com', 'junyu.guo@chinacache.com', 'bingli.li@chinacache.com', 'bin.liu@chinacache.com',
#             'longjun.zhao@chinacache.com']


def create_begin_end_time(hours=1):
    """
    accroding hours, create time before hours time, time now
    :param hours: period
    :return: begin_time, end_time
    """
    end_time = get_time()
    begin_time = end_time - datetime.timedelta(hours=hours)
    return begin_time, end_time

# # test
# def create_begin_end_time(hours=1):
#     """
#     accroding hours, create time before hours time, time now
#     :param hours: period
#     :return: begin_time, end_time
#     """
#     begin_time = get_time()
#     end_time = begin_time + datetime.timedelta(hours=hours)
#     return begin_time, end_time


def format_time(datetime_time):
    """
    datetime.datetime.strftime(datetime.d atetime.now(), '%Y-%m-%d %H:%M:%S')
    format time
    :param datetime_time: 2016-06-22 14:56:26.682584
    :return: 2016-06-22 14:56:26
    """
    try:
        return datetime.datetime.strftime(datetime_time, "%Y-%m-%d %H:%M:%S")
    except Exception:
        logger.debug("format time error:%s" % e)


def get_data_mongo(begin_time, end_time):
    """
    according begin_time, end_time, get data info from mongo device_link
    :param begin_time:
    :param end_time:
    :return:
    """
    result = []
    try:
        result = db.device_link.find({"detect_time": {"$gte": begin_time, "$lt": end_time}})
    except Exception:
        logger.debug("device_link  find error:%s" % e)
    return result


def statistic_date(result):
    """
    according result of device_link, statistic device info

    the format data of data insert into mongo:
     { 'datetime': xxxx,
        'name': xxxx,
        'ip': xxxx,
        'failed_count':xxx,
        'codes': { '503':xxx, '501': xxx, '200': xxx}
    }

    :param result:[{"_id" : ObjectId("576926a51d41c8536670d607"),
    "detect_time" : ISODate("2016-06-21T19:36:05.356+0000"),
    "devices" : [
        {
            "code" : "503",
            "name" : "ksd-sdf-dd1",
            "total_cost" : "2.03",
            "ip" : "218.205.76.172",
            "connect_cost" : "2.03",
            "response_cost" : "0.00"
        },
        {
            "code" : "503",
            "name" : "ksd-sdf-dd2",
            "total_cost" : "2.03",
            "ip" : "119.84.69.208",
            "connect_cost" : "2.03",
            "response_cost" : "0.00"
        }
    ],
    "detect_date" : "2016-06-21"}]
    :return: {"name1":{"200":xx,"503":xx, "501":xx}}
    """
    result_map = {}
    result_map_new = {}
    # insert mongo time, integer time
    result_time = get_time()
    if result:
        for res in result:
            devices = res.get("devices", None)
            if devices:
                for dev in devices:
                    name = dev.get("name", None)
                    code = dev.get("code", None)
                    ip = dev.get('ip', None)
                    provinceName = dev.get('provinceName', None)
                    ispName = dev.get('ispName', None)
                    # name is not None or blank
                    if name and code:
                        # judge is not in result_map
                        if name not in list(result_map.keys()):
                            code_temp = {}
                            code_temp[code] = 1
                            result_map[name] = code_temp

                            # insert mongo data
                            code_temp_new = {}
                            code_temp_new['codes'] = {}
                            code_temp_new['codes'][code] = 1
                            code_temp_new['name'] = name
                            code_temp_new['ip'] = ip
                            code_temp_new['provinceName'] = provinceName
                            code_temp_new['ispName'] = ispName
                            code_temp_new['datetime'] = result_time
                            if code != '200':
                                code_temp_new['failed'] = 1
                            else:
                                code_temp_new['failed'] = 0
                            result_map_new[name] = code_temp_new

                        else:
                            code_temp = result_map[name]
                            # judge code is not in code_temp
                            if code in code_temp:
                                code_temp[code] += 1
                            else:
                                code_temp[code] = 1

                            # insert mongo data
                            code_temp_new = result_map_new[name]
                            # judge code is not in code_temp
                            if code in code_temp_new['codes']:
                                code_temp_new['codes'][code] += 1
                            else:
                                code_temp_new['codes'][code] = 1
                            if code != '200':
                                code_temp_new['failed'] += 1
    if result_map_new:
        try:
            db.device_link_hours_result.insert(list(result_map_new.values()))
            logger.debug('link_hours_result insert success')
        except Exception:
            logger.debug("link_hours_result  insert error:%s" % e)
    else:
        logger.debug("link detection data is empty")

    return result_map


def statistic_date_new(result):
    """
    according result of device_link, statistic device info
    not insert into mongo
    the format data of data insert into mongo:
     { 'datetime': xxxx,
        'name': xxxx,
        'ip': xxxx,
        'failed_count':xxx,
        'codes': { '503':xxx, '501': xxx, '200': xxx}
    }

    :param result:[{"_id" : ObjectId("576926a51d41c8536670d607"),
    "detect_time" : ISODate("2016-06-21T19:36:05.356+0000"),
    "devices" : [
        {
            "code" : "503",
            "name" : "ksd-sdf-dd1",
            "total_cost" : "2.03",
            "ip" : "218.205.76.172",
            "connect_cost" : "2.03",
            "response_cost" : "0.00"
        },
        {
            "code" : "503",
            "name" : "ksd-sdf-dd2",
            "total_cost" : "2.03",
            "ip" : "119.84.69.208",
            "connect_cost" : "2.03",
            "response_cost" : "0.00"
        }
    ],
    "detect_date" : "2016-06-21"}]
    :return: {"name1":{"200":xx,"503":xx, "501":xx}}
    """
    result_map = {}
    result_map_new = {}
    # insert mongo time, integer time
    result_time = get_time()
    if result:
        for res in result:
            devices = res.get("devices", None)
            if devices:
                for dev in devices:
                    name = dev.get("name", None)
                    code = dev.get("code", None)
                    ip = dev.get('ip', None)
                    provinceName = dev.get('provinceName', None)
                    ispName = dev.get('ispName', None)
                    # name is not None or blank
                    if name and code:
                        # judge is not in result_map
                        if name not in list(result_map.keys()):
                            code_temp = {}
                            code_temp[code] = 1
                            result_map[name] = code_temp
                        else:
                            code_temp = result_map[name]
                            # judge code is not in code_temp
                            if code in code_temp:
                                code_temp[code] += 1
                            else:
                                code_temp[code] = 1
    return result_map


def get_time():
    """
    according now time
    :return: 2016-8-3 15:00:00
    """
    now = datetime.datetime.now()
    str_now = now.strftime("%Y-%m-%d %H")
    datetime_now = datetime.datetime.strptime(str_now, '%Y-%m-%d %H')
    return datetime_now


def parse_result_map(result_map, count=3):
    """
    the data need to parse, if not code eq 200 , alarm the this device
    :param result_map: {"name1":{"200":xx,"503":xx, "501":xx}}
    :param count: threshold
    :return: {"name1":{"200":xx, "503":xxx, "501":xx}, "name2": {"200":xx, "503":xx, "501":xx}}
    """
    result_list = {}
    if result_map:
        for key_name, val in list(result_map.items()):
            count_all = count_map_number(val)
            code_200_count = val.get("200", 0)
            if count_all - code_200_count > count:
                result_list[key_name] = val
    dev_all_number = len(result_map)
    dev_failed_number = len(result_list)
    return result_list, dev_all_number, dev_failed_number


def count_map_number(map_temp):
    """
    count all number of map_temp
    :param map_temp: {"200":xx,"503":xx, "501":xx}
    :return: xx+xx+xx
    """
    count = 0
    if map_temp:
        for val in list(map_temp.values()):
            count += int(val)
    return count


# assemble  mail content
def assemble_mail_content_send(result_dict, begin_time, end_time, dev_all_number, dev_failed_number, threshold, email_to):
    """
    according result_dict, assemble mail content, and send to somebody
    :param result_dict: [{"name1":{"200":xx,"503":xx, "501":xx}},{"name2":{"200":xx,"503":xx, "501":xx}}]
    :param begin_time:
    :param end_time:
    :param dev_all_number: a total link dev of one hour ago
    :param dev_failed_number: failed dev number of one hour ago
    :param threshold:
    :param email_to: the list of email address
    :return:
    """
    content = 'Hi,ALL:<br/>下面是出现问题的设备:<br/>'
    content += '''<br/><br/>状态码为:<br/>501: 表示连接上了设备，没有接收到设备信息<br/>
    503: 无法连接上设备，连接超时，无法建联<br/>
    502: The network is OK,But the preload does not work<br/>
    200: 设备正常<br/><br/><br/>
    '''
    content += '探测开始时间:' + str(format_time(begin_time)) + ',' + '探测结束时间:' + str(format_time(end_time)) + \
               '<br/><br/><br/>'
    content += '探测的设备总数：' + str(dev_all_number) + "&nbsp&nbsp" + '探测失败的设备数：' + str(dev_failed_number) + "<br/>"
    content += '下面是出现问题的设备(目前认为失败次数超过'+ str(threshold) +'次为失败)，包括设备的名称，一定时间' \
               '内连接的次数，每个状态码出现的次数<br/><br/>'

    print("result_list:%s" % result_dict)
    print('email_to:%s' % email_to)
    print('threshold:%s' % threshold)
    print('begin_time:%s, end_time:%s' % (begin_time, end_time))
    print('dev_all_number:%s' % dev_all_number)
    if result_dict:
        for key, values in list(result_dict.items()):
            print("flag:%s" % key)
            print("flag values:%s" % values)
            content += str(key) + '\b探测' + str(count_map_number(values)) + "次&nbsp&nbsp"
            if values:
                for key_code, value_count in list(values.items()):
                    if key_code != '200':
                        content += '&nbsp&nbsp' + str(key_code) + '出现' + str(value_count) + '次' + '&nbsp&nbsp'
            content += '<br/><br/>'
        logger.debug("send email start.....")
        send(email_from, email_to, '链路探测报警信息', content)
        logger.debug("send email end")



# 发邮件
def send(from_addr, to_addrs, subject, content):
    msg = MIMEMultipart()
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


def get_email_management():
    """
    get failed_type (failed_device)  data
    :return:
    """
    result = []
    try:
        result = db.email_management.find({'failed_type': 'failed_device'})
        logger.debug('get email_management data success')
    except Exception:
        logger.debug("get email_management data error:%s" % e)
    return result


def get_data(hour):
    """

    :param hour:
    :return:
    """
    logger.debug('send email start....')
    begin_time, end_time = create_begin_end_time(hours=hour)
    logger.debug("begin_time:%s, end_time:%s" % (begin_time, end_time))
    # get data from mongo
    result = get_data_mongo(begin_time, end_time)
    # statistic number of code  every device
    result_map = statistic_date_new(result)
    logger.debug("warning message  result_map:%s" % result_map)
    return begin_time, end_time, result_map


def get_requeired_info(requir_list, all_dict):
    """
    obtail required equipment information
    :param requir_list: the name of dev,  type  list
    :param all_list: all dev info    {"name1":{"200":xx,"503":xx, "501":xx}}
    :return: {"name1":{"200":xx,"503":xx, "501":xx}}
    """
    result = {}
    if not all_dict:
        return result
    if not requir_list:
        return result
    else:
        for re in requir_list:
            if re in all_dict:
                result[re] = all_dict[re]
        return result


def email_entrance():
    """
    the entrance of send email
    :return:
    """
    email_managements = get_email_management()
    now = datetime.datetime.now()
    int_hour = int(datetime.datetime.strftime(now, '%H'))
    # get data one hour
    begin_time_1, end_time_1, result_map_1 = get_data(1)
    # get data 24 hour before
    begin_time_24, end_time_24, result_map_24 = get_data(24)
    for email_management in email_managements:
        rate = email_management.get('rate', '')
        if rate:
            if int_hour % rate == 0:
                begin_time_temp = eval('begin_time_' + str(rate))
                end_time_temp = eval('end_time_' + str(rate))
                result_map_temp = eval('result_map_' + str(rate))
                devices = email_management.get('devices', [])
                print('devices:%s' % devices)
                print('result_map_temp:%s' % result_map_temp)
                result_map_temp = get_requeired_info(devices, result_map_temp)
                # print "result_map_temp:%s" % result_map_temp
                # filter the information of result_map
                result_dict, dev_all_number, dev_failed_number = parse_result_map(result_map_temp, count=email_management.get('threshold'))
                assemble_mail_content_send(result_dict, begin_time_temp, end_time_temp, dev_all_number,
                                           dev_failed_number, email_management.get('threshold'), email_management.get('email_address', []))


def program_entry():
    """
    program  entrance
    :return:
    """
    # get start time   get end time
    begin_time, end_time = create_begin_end_time()
    # print "k1" + str(begin_time) + "   " + str(end_time)
    logger.debug("begin_time:%s, end_time:%s" % (begin_time, end_time))
    # get data from mongo
    result = get_data_mongo(begin_time, end_time)
    # statistic number of code  every device
    result_map = statistic_date(result)
    # insert data into link_hours_result
    # parse_data_insert(result)
    logger.debug("warning message  result_map:%s" % result_map)
    # original
    # # filter the information of result_map
    # result_dict, dev_all_number, dev_failed_number = parse_result_map(result_map)
    # # assemble and send email
    # # print begin_time
    # # print format_time(begin_time)
    # assemble_mail_content_send(result_dict, begin_time, end_time, dev_all_number, dev_failed_number)
    # original

    # new
    try:
        email_entrance()
        logger.debug("send email success!")
    except Exception:
        logger.debug("send email error:%s" % e)


if __name__ == '__main__':
    program_entry()
    os._exit(0)



