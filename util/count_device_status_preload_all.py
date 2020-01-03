#! /usr/bin/env python
# -*- coding: utf-8 -*-

'''
    统计前一日的刷新任务，收到的任务量，下发的任务量及503的分析
    @author: rubin
    Created on 2016-4-25
    完成目标，对预加载信息进行统计，然后把信息邮件发送给相应的人员
    １．预加载系统每日统计，刷新总量，刷新成功数，刷新失败数，失败率
    ２．失败设备top10 列表，
    ３．客户刷新量top10, 刷新失败用户top10
    4.预加载系统每日下发任务统计表（数量／占比）
    ５．预加载系统５０３分析（设备数及５０３分布占比）
    ６．从任务维度统计，导致任务失败的状态码及占比
    ７．导出一天设备信息详细情况
'''

import datetime
import sys
import os
import logging
import time
import imp
# 解决python2.6 collection 不含有OrderedDict问题
try:
    from collections import OrderedDict
except ImportError:
    try:
        from ordereddict import OrderedDict
    except ImportError:
        raise

import urllib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import xlwt
from core.database import query_db_session, s1_db_session
# 解决编码问题
imp.reload(sys)
sys.setdefaultencoding('utf8')

import ssl
ssl._create_default_https_context = ssl._create_unverified_context

from util.emailSender import EmailSender

# try:
#     from pymongo import ReplicaSetConnection as MongoClient
# except:
#     from pymongo import MongoClient
# # 136变为主
# conn = MongoClient('mongodb://bermuda:bermuda_refresh@223.202.52.136:27017/bermuda')
# conn = conn.bermuda


# LOG_FILENAME = '/Application/bermuda3/logs/preload_count_device.log'
# LOG_FILENAME = '/home/rubin/logs/preload_count_device.log'

# 测试本地log
# LOG_FILENAME = '/home/rubin/logs/preload_count_device.log'
# logging.basicConfig(filename=LOG_FILENAME,
#                     format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s',
#                     level=logging.INFO)


# logger = logging.getLogger('preload_count_deivce')
# logger.setLevel(logging.DEBUG)
from util import log_utils


logger = log_utils.get_rtime_Logger()
# uri = 'mongodb://bermuda:bermuda_refresh@%s:27017,%s:27017,%s:27017/bermuda?replicaSet=bermuda_db' % (
#     '172.16.12.136', '172.16.12.135', '172.16.12.134')
# conn = MongoClient(uri)['bermuda']

# conn = MongoClient('mongodb://superAdmin:admin_refresh@223.202.52.136:27017/').bermuda

# online info
conn = query_db_session()
s1_db = s1_db_session()


# 获取上层设备的url
#RCMS_DEVICES_LAYER = 'https://rcmsapi.chinacache.com/upperlayer/devices'
RCMS_DEVICES_LAYER = 'https://cms3-apir.chinacache.com/upperlayer/devices'
# 获取设备类型的url
# RCMS_API = 'http://rcmsapi.chinacache.com:36000/device/name/{0}/apps'

RCMS_API = 'http://j.hope.chinacache.com:8082/api/device/name/{0}/apps'
# 查询设备的mrtg
# RCMS_MRTG = 'http://rcmsapi.chinacache.com:36000/device/{0}/mrtgnotes'

HOPE_MRTG = 'http://j.hope.chinacache.com:8082/api/device/{0}/mrtgnotes'

STATUS_LIST = ['0', '404', '408', '503', '501', '502']

# 生成的预加载信息xml文件存储路径
LOG_DIR = '/Application/bermuda3/logs/outputxls/preload/'

# test in self field
# LOG_DIR = '/home/rubin/outputxls/preload/'

# 发送邮件的发件人地址
email_from = 'nocalert@chinacache.com'
# 接收邮件的收件人邮箱
email_to = ['huan.ma@chinacache.com', 'yanming.liang@chinacache.com', 'pengfei.hao@chinacache.com',
            'feng.qiu@chinacache.com', 'zhida.piao@chinacache.com'
            ]
# email_to = ['yanming.liang@chinacache.com']

send_headers = {'X-HOPE-Authn': 'refresh'}
#  获取前n天时间的字符串　　


def get_n_day_before_str(n):
    """
    根据n和当前时间，计算当前时间前n天的时间字符串，如2015-02-01
    :param n:一个数字，
    :return:返回前n天的一个字符串
    """
    before_n = datetime.datetime.now() - datetime.timedelta(days=1)
    # 截取日期前面的部分，得到2015-02-01　这种格式的日期形式
    day = before_n.date().strftime("%Y-%m-%d")
    return day


def get_begin_end_time(n):
    """
    根据n,和当前时间，获取前n天的开始时间和结束时间
    :param n: 数字
    :return: 返回前n天的开始时间和结束时间
    """
    begin = datetime.datetime.now() - datetime.timedelta(days=n)
    # 生成开始时间　当天的０点
    begin_time = datetime.datetime.combine(begin, datetime.time())
    # 第二天的开始时间，当天的０点
    end_time = begin_time + datetime.timedelta(days=1)
    # 返回开始时间和结束时间
    return begin_time, end_time


def preload_statistical_everyday(date_str):
    """
    根据日期字符串，查找statistical_preload, 查找到相应的当天预加载信息
    :param date_str:
    :return:
    """
    try:
        connect = conn['statistical_preload']
    except Exception:
        logger.error(traceback.format_exc())
        return

    # theader = '<th>%s</th>'.format('</th><th>'.join(['Date','404','408','503','0']))
    # 表格的第一行信息
    header_list = ['Date', '预加载量', '成功', '进行中', 'INVALID', '失败', '失败率']

    theader = '<th>{0}</th>'.format('</th><th>'.join(header_list))
    # preload_statical = connect.find({'date': date_str})
    trs = []
    print(date_str)
    for record in connect.find({'date': date_str}).limit(1):
        print(record)
        tr = [record["date"]]
        # 预加载的总数
        tr.append('{0}'.format(group(int(record['total_preload_url']))))
        # 预加载完成的数量
        tr.append('{0}'.format(group(int(record["statistic_finished"]))))
        # 预加载正在进行中的数量
        tr.append('{0}'.format(group(int(record["statistic_progress"]))))
        # # 预加载删除的数量
        # tr.append('{0:,}'.format(int(record["statistic_cancel"])))
        # # 预加载无效的数量
        tr.append('{0:,}'.format(int(record["statistic_invalid"])))
        # # 预加载过期的数量
        # tr.append('{0:,}'.format(int(record["statistic_expired"])))
        # 预加载失败的数量
        tr.append('{0}'.format(group(int(record["statistic_failed"]) + int(record["statistic_cancel"]) +
                                     int(record["statistic_expired"]) + int(record["statistic_progress"]))))

        # 所有不成功的都归结为失败　
        fail_count = int(record["statistic_progress"]) + int(record["statistic_cancel"]) \
            + int(record["statistic_expired"]) + \
            int(record["statistic_failed"])
        # 预加载失败率
        try:
            tr.append('{0:.2%}'.format((round(fail_count / float(record["total_preload_url"]), 4))))
        except ZeroDivisionError:
            tr.append('0.00')

        trs.append('<td>{0}</td>'.format('</td><td>'.join(tr)))
    table = '<table border="1">\n<thead><tr>{0}</tr></thead>\n<tbody>\n<tr>{1}</tr></tbody></table>'.format(theader,
                                                                                                            '</tr>\n<tr>'.join(
                                                                                                                trs))
    return table


def preload_statistical_everyday_new(date_str):
    """
    根据日期字符串，查找statistical_preload, 查找到相应的当天预加载信息, 下发成功情况
    :param date_str:
    :return:
    """
    try:
        connect = conn['statistical_preload']
    except Exception:
        logger.error(traceback.format_exc())
        return

    # theader = '<th>%s</th>'.format('</th><th>'.join(['Date','404','408','503','0']))
    # 表格的第一行信息
    header_list = ['Date', '预加载量', '成功', '失败', '失败率']

    theader = '<th>{0}</th>'.format('</th><th>'.join(header_list))
    # preload_statical = connect.find({'date': date_str})
    trs = []
    print(date_str)
    for record in connect.find({'date': date_str}).limit(1):
        print(record)
        tr = [record["date"]]
        # 预加载的总数
        tr.append('{0}'.format(group(int(record['total_preload_url']))))
        # 预加载完成的数量
        tr.append('{0}'.format(
            group(int(record['total_preload_url']) - int(record["send_failed"]))))
        # 预加载下发失败的数量
        tr.append('{0}'.format(group(int(record["send_failed"]))))

        # 预加载失败率
        try:
            tr.append('{0:.2%}'.format((round(int(record['send_failed']) / float(record["total_preload_url"]), 4))))
        except ZeroDivisionError:
            tr.append('0.0')

        trs.append('<td>{0}</td>'.format('</td><td>'.join(tr)))
    table = '<table border="1">\n<thead><tr>{0}</tr></thead>\n<tbody>\n<tr>{1}</tr></tbody></table>'.format(theader,
                                                                                                            '</tr>\n<tr>'.join(
                                                                                                                trs))
    return table


class StatisticPreloadDevicesInfo(object):
    """
    此类的目标完成，预加载设备完成信息的一个统计，包括HC, HPCC, unknown 设备，包括每一个设备自己的统计信息，最终生成的数据格式如下：
    all_info:{
     FC:{"200":NumberInt(123), "404":NumberInt(123)}
     HPCC:{}
     unknown:{}
     data:{ "GWB-GZ-2-303":{"hostname":"GWB-GZ-2-303","200":NumberInt(255)},{}
                }
    }
    """

    def __init__(self, collection, s1_conn, start_time, end_time):
        # 连接数据库句柄
        self.collection = collection
        self.s1_conn = s1_conn
        # 开始时间
        self.start_time = start_time
        # 结束时间
        self.end_time = end_time
        # 记录设备信息情况的一个列表
        self.devices_info_list = {}
        # 需要返回的一个所有信息　　结构
        self.all_info = {}

    def get_preload_url_info(self):
        """
        查询preload_url 表中，满足条件的所有信息
        :return:
        """
        # 查询条件
        # query_conditions = {{"created_time": {"$gte": self.start_time, "$lt": self.end_time},\
        #                     "status": {"$in": ["FINISHED", "PROGRESS", "FAILED"]}, "dev_id": {"$exists": True}}, {"dev_id": 1}}
        # 查询结果　　　batch_size  每次从数据库中取　３０个结果
        result = self.s1_conn.preload_url.find({"created_time": {"$gte": self.start_time, "$lt": self.end_time},
                                                "status": {"$in": ["FINISHED", "PROGRESS", "FAILED"]}, "dev_id": {"$exists": True}}, {"dev_id": 1}).batch_size(30)
        return result

    def get_preload_dev_info(self, dev_id):
        """
        根据dev_id,即为_id, 查找preload_dev 信息
        :param dev_id:
        :return:
        """
        result = self.s1_conn.preload_dev.find_one({"_id": dev_id})
        data = result.get("devices", None)
        return data

    def get_firstLayerDevices(self):
        """
        从RCMS获取一个上层设备列表
        :return: 返回一个上层设备信息列表
        """
        got_list = eval(urllib.request.urlopen(RCMS_DEVICES_LAYER, timeout=100).read())
        dev_info = {}
        FIRSTLAYER_DEVICES = [str(dev['devName'])
                              for dev in got_list if dev['devStatus'] == "OPEN"]
        return FIRSTLAYER_DEVICES

    def get_devices_type(self, devices):
        """
        根据设备名称列表，返回所有设备的信息列表，设备和设备类型的对应列表，如{设备１：HPCC, 设备２：FC} ,暂时没有使用此方法
        :param devices:
        :return:
        """
        devices_type = {}
        for dev in devices:
            try:
                dd = self.collection["device_app"].find_one({"name": dev})
                devices_type[dev] = dd["type"]
            except Exception:
                print(e)
                logger.error(e)
                get_url = RCMS_API.format(dev)
                # add header
                req = urllib.Request(get_url, headers=send_headers)
                got_list = eval(urllib.request.urlopen(req, timeout=100).read())
                try:
                    got_list = got_list.get('data')
                    devices_type[dev] = [dic['appName'] for dic in got_list if dic[
                        'appName'] in ['FC', 'HPCC']][0]
                except Exception:
                    logger.error(traceback.format_exc())
                    devices_type[dev] = 'unknown'
        return devices_type

    def get_device_type(self, device_name):
        """
        根据设备名称，返回设备的类型，主要有三种类型HPCC, FC ,unknown
        :param device_name: 设备的名称
        :return: 设备的类型，HPCC 或　FC　或　　unknown
        """
        try:
            dd = self.collection["device_app"].find_one({"name": device_name})
            return dd["type"]
        except Exception:
            logger.error(e)
            # get_url = RCMS_API.format(device_name)
            # got_list = eval(urllib.urlopen(get_url, timeout=100).read())
            # try:
            #     device_type = [dic['appName'] for dic in got_list if dic['appName'] in ['FC', 'HPCC']][0]
            # except Exception, ex:
            #     logger.error(traceback.format_exc())
            #     device_type = 'unknown'
            if not device_name or device_name == 'null':
                return 'unknown'
            get_url = RCMS_API.format(device_name)
            # add header
            req = urllib.Request(get_url, headers=send_headers)
            got_list = eval(urllib.request.urlopen(req, timeout=100).read())
            try:
                got_list = got_list.get('data')
                device_type = [dic['appName'] for dic in got_list if dic[
                    'appName'] in ['FC', 'HPCC']][0]
            except Exception:
                logger.error(traceback.format_exc())
                device_type = 'unknown'
        return device_type

    def get_device_isp(self, device_name):
        """
        根据设备的名称，返回设备的ISP
        :param device_name: 设备的名称
        :return: 返回设备的ISP
        """
        return device_name.split("-")[0]

    def build_data_structure(self):
        """
        实现数据结构的主函数
        :return:
        """
        # 获取预加载信息（preload_url）
        # 保存hpcc 设备的名称
        hpcc_set = set()
        # 保存fc 设备的名称
        fc_set = set()
        # 保存unknown 设备的名称
        unknown_set = set()
        # 上层设备的一个列表
        FIRSTLAYER_DEVICES = self.get_firstLayerDevices()
        # 状态码的一个列表，不包含２００
        code_list_not_contain_200 = [
            '0', '404', '408', '503', '501', '502', '500']
        # 所有状态码的一个列表，
        code_list = ['0', '404', '408', '503', '501', '502', '500', '200']
        for ty in ["HPCC", "FC", "unknown"]:
            self.all_info[ty] = {}
        preload_url_info = self.get_preload_url_info()
        for preload_url in preload_url_info:
            # 获取一个预加载信息的所有处理设备的信息
            devices = self.get_preload_dev_info(preload_url["dev_id"])
            # 对每一个设备做一个轮询
            for dev in devices:
                # 临时存储code 编号
                code = str(devices[dev]['code'])
                # print "kkkkkkkkkkkk"
                # print "dev:%s" % dev
                if devices[dev]['name'] not in list(self.devices_info_list.keys()):
                    self.devices_info_list[dev] = {}

                    # self.devices_info_list 做处理
                    self.devices_info_list[dev][code] = 1
                    # 存储设备的名称
                    self.devices_info_list[dev]["hostname"] = dev
                    # 存储设备的ISP编号
                    self.devices_info_list[dev][
                        "ISP"] = self.get_device_isp(dev)
                    # 获取设备的类型
                    self.devices_info_list[dev][
                        'type'] = self.get_device_type(dev)
                    # 是否是上层设备
                    self.devices_info_list[dev][
                        'firstLayer'] = True if dev in FIRSTLAYER_DEVICES else False

                    # 临时存储设备的类型
                    type = self.devices_info_list[dev]['type']
                    # 对self.all_info 整体数据做处理　　不同的设备类型
                    if 'num' not in self.all_info[type]:

                        self.all_info[type]['num'] = 0
                    self.all_info[type]['num'] += 1
                    # 处理设备类型相应的code 　计数信息
                    if code not in self.all_info[type]:
                        self.all_info[type][code] = 0
                    self.all_info[type][code] += 1
                    # 初始化total
                    if 'failed_total' not in self.devices_info_list[dev]:
                        self.devices_info_list[dev]['failed_total'] = 0
                    if code in code_list_not_contain_200:
                        # if code not in ['200']:
                        self.devices_info_list[dev]['failed_total'] += 1
                    if type == 'HPCC':
                        hpcc_set.add(dev)
                    elif type == 'FC':
                        fc_set.add(dev)
                    else:
                        unknown_set.add(dev)
                else:
                    if code not in self.devices_info_list[dev]:
                        self.devices_info_list[dev][code] = 0
                    self.devices_info_list[dev][code] += 1
                    # 获取设备的类型　直接从list获得
                    type = self.devices_info_list[dev]['type']

                    # 对self.all_info 整体数据做处理　　不同的设备类型
                    if 'num' not in self.all_info[type]:
                        self.all_info[type]['num'] = 0
                    self.all_info[type]['num'] += 1
                    # 处理设备类型相应的code 　计数信息
                    if code not in self.all_info[type]:
                        self.all_info[type][code] = 0
                    self.all_info[type][code] += 1
                    if code in code_list_not_contain_200:
                        # if code not in ['200']:
                        self.devices_info_list[dev]['failed_total'] += 1
                    if type == 'HPCC':
                        hpcc_set.add(dev)
                    elif type == 'FC':
                        fc_set.add(dev)
                    else:
                        unknown_set.add(dev)
        # 设置HPCC FC unknown 对应的num 值
        self.all_info['HPCC']['num'] = len(hpcc_set)
        self.all_info['FC']['num'] = len(fc_set)
        self.all_info['unknown']['num'] = len(unknown_set)
        # 对devices_info_list 内容进行排序　根据失败数量　　有多到少排序
        self.devices_info_list = OrderedDict(sorted(
            list(self.devices_info_list.items()), key=lambda t: t[1]['failed_total'], reverse=True))
        self.all_info['data'] = self.devices_info_list
        print(self.devices_info_list)
        # 返回信息列表
        return self.all_info


def write_devices_failed_top(data):
    """
    写入设备失败前１０的设备
    :param data:
    :return:
    """
    theader = '<th>NO.</th><th>hostname</th><th>ISP</th><th>type</th><th>firstLayer</th><th>500</th><th>501</th><th>502</th><th>503</th><th>FAIL</th><th>mrtg</th>'
    trs = []
    mrtg = ""
    for i, device in enumerate(list(data['data'].values())[:10]):
        try:
            dev = conn.device_app.find_one({"name": device['hostname']})
            url = HOPE_MRTG.format(dev["devCode"])
            logger.debug("write_devices_failed_top url: %s" % (url, ))
            # add header
            req = urllib.Request(url, headers=send_headers)
            mrtg_info = eval(urllib.request.urlopen(req, timeout=100).read())
            mrtg = ','.join(mrtg_info['data']['mrtgs'])
            # mrtg = mrtg.decode("utf-8")
        except Exception:
            logger.error(traceback.format_exc())
        tr = [str(i + 1), device['hostname'], device['ISP'], device['type'], str(device['firstLayer']), str(device.get('500', 0)),
              str(device.get('501', 0)), str(device.get('502', 0)), str(
                  device.get('503', 0)), str(device.get('failed_total', 0)),
              mrtg]  # unicode.encode(mrtg,"utf-8")
        trs.append('<td>{0}</td>'.format('</td><td>'.join(tr)))

    table = '<table border="1">\n<thead><tr>{0}</tr></thead>\n<tbody>\n<tr>{1}</tr></tbody></table>'.format(theader,
                                                                                                            '</tr>\n<tr>'.join(
                                                                                                                trs))
    return table


def write_user_top_for_count(date_str):
    try:
        connect = conn['statistical_preload']
    except Exception:
        logger.error(traceback.format_exc())
        return

    data_list = []

    # theader = '<th>%s</th>'.format('</th><th>'.join(['Date','404','408','503','0']))
    header_list = ['NO.', '用户名', '数量']

    theader = '<th>{0}</th>'.format('</th><th>'.join(header_list))

    table = ""
    data = connect.find_one({'date': date_str})
    #  暂时注掉　　以后用时加上
    # for tab in ["username_count_list", "username_failed_list"]:
    for tab in ["username_count_list"]:
        if tab in list(data.keys()) and (len(data[tab]) > 0):
            data_list = data[tab][:10]
        else:
            continue
        i = 0
        trs = []
        for key, value in data_list:
            tr = [str(i + 1)]
            tr.append(key)
            tr.append('{0}'.format(group(int(value))))
            trs.append('<td>{0}</td>'.format('</td><td>'.join(tr)))
            i += 1
        if tab == "username_count_list":
            table += '<table width="33%" border="1" align=left>\n<thead><tr>{0}</tr></thead>\n<tbody>\n<tr>{1}</tr></tbody></table>'.format(
                theader,
                '</tr>\n<tr>'.join(
                    trs))
        else:
            table += '<table width="33%" border="1" align=center>\n<thead><tr>{0}</tr></thead>\n<tbody>\n<tr>{1}</tr></tbody></table>'.format(
                theader,
                '</tr>\n<tr>'.join(
                    trs))
    return table


def write_code(total_dic):
    """
    预加载系统每日下发任务统计表(数量/占比)
    :param total_dic:
    :return:
    """
    # today = datetime.datetime.today()
    # process_date = today - datetime.timedelta(days=1)
    # date_str = process_date.strftime('%Y-%m-%d')
    theader = '<th>设备类型</th><th>设备数</th>' + '<th colspan="2">{0}</th>'.format(
        '</th><th colspan="2">'.join(['503(%)', '500(%)', '0(%)', '200(%)'])) + '<th>总数</th>'

    trs = []
    tre = []

    t_dic = {}
    device_num = 0
    type_list = ['HPCC', 'FC', 'unknown']
    title_list = ["503", "500", "0", "200"]
    ttotal = 0
    for type in type_list:
        if total_dic[type]:
            for ti in title_list:
                if ti not in t_dic:
                    t_dic[ti] = 0
                if type not in t_dic:
                    t_dic[type] = 0
                t_dic[ti] += int(total_dic[type].get(ti, 0))
                t_dic[type] += int(total_dic[type].get(ti, 0))
                ttotal += int(total_dic[type].get(ti, 0))
            device_num += int(total_dic[type].get('num', 0))
            tr = ['<td>%s</td><td>%s</td>' %
                  (type, int(total_dic[type].get('num', 0)))]
            for tt in title_list:
                try:
                    per_c = round(int(total_dic[type].get(
                        tt, 0)) / float(t_dic[type]), 4)
                except:
                    per_c = 0
                tr.append(
                    '<td>{0}</td><td style="background-color:#999966";>{1:.2%}</td>'.format(group(int(total_dic[type].get(tt, 0))),
                                                                                            per_c))

            tr.append('<td>{0}</td>'.format(group(t_dic[type])))
            trs.append(''.join(tr))
    tre = ['{0}'.format(group(t_dic[tt])) for tt in title_list]
    trs.append('<td>TOTAL</td><td>{0}</td>'.format(group(device_num)) + '<td colspan="2">{0}</td>'.format(
        '</td><td colspan="2">'.join(tre)) + '<td>{0}</td>'.format(group(ttotal)))
    table = '<table border="1">\n<thead><tr>{0}</tr></thead>\n<tbody>\n<tr>{1}</tr></tbody></table>'.format(theader,
                                                                                                            '</tr>\n<tr>'.join(
                                                                                                                trs))
    return table


# def write_503_per(total_dic):
#     """
#     预加载系统503分析(设备数及503分布占比)
#     :param total_dic:
#     :return:
#     """
#     theader = '<th>设备类型</th><th>503总数</th><th>设备数</th>' + '<th colspan="2">{0}</th>'.format(
#         '</th><th colspan="2">'.join(['>10000(%)', '>1000(%)', '>100(%)', '10(%)', '>1(%)']))
#     type_list = ['HPCC', 'FC', 'unknown']
#     num_list = [10000, 1000, 100, 10, 1]
#     code = '503'
#     trs = []
#     devs_num = 0
#     r_dic = {}
#     for ty in type_list:
#         if total_dic[ty]:
#             devs_num += total_dic[ty]['num']
#             for nn in num_list:
#                 if ty not in r_dic:
#                     r_dic[ty] = {}
#                 r_dic[ty][nn] = 0
#
#     for item in total_dic['data'].values():
#         num = int(item.get('503', 0))
#         dev_type = item['type']
#         if num >= 10000:
#             r_dic[dev_type][10000] += 1
#         elif num >= 1000:
#             r_dic[dev_type][1000] += 1
#         elif num >= 100:
#             r_dic[dev_type][100] += 1
#         elif num >= 10:
#             r_dic[dev_type][10] += 1
#         elif num >= 1:
#             r_dic[dev_type][1] += 1
#     nn = 1
#     for type in type_list:
#         if total_dic[type]:
#             total = total_dic[type].get(code, 0)
#             tr = ['<td>%s</td>' % type]
#             tr.append('<td>%s</td>' % total)
#             tr.append('<td>{0:,}</td>'.format(total_dic[type]['num']))
#
#             for n in num_list:
#                 cur_num = r_dic[type][n]
#                 try:
#                     per = round(int(cur_num) / float(total_dic[type]['num']), 4)
#                 except:
#                     per = 0
#                 tr.append('<td>{0:,}</td><td style="background-color:#FFA500";>{1:.2%}</td>'.format(cur_num, per))
#             # else:
#             #         tr.append('<td>{0:,}</td><td style="background-color:#FFFF00";>{1:.2%}</td>'.format(cur_num,per))
#             # nn+=1
#             trs.append(''.join(tr))
#
#     table = '<table border="1">\n<thead><tr>{0}</tr></thead>\n<tbody>\n<tr>{1}</tr></tbody></table>'.format(theader,
#                                                                                                             '</tr>\n<tr>'.join(
#                                                                                                                 trs))
#     return table


def write_excel(connect_time, date_str, data_list):
    # 创建excel
    '''
    data_list = [{'200': 1, 'hostname': 'CNC-TI-9-3SI', 'a_0': 0, 'r_0': 0, 'ISP': 'CNC', 'a_501': 0, 'a_502': 0, 'a_503': 0, '0': 0, '404': 0, 'r_503': 0, 'r_502': 0, 'r_501': 0, 'total': 5, 'type': 'FC', '503': 0, '408': 0},
    {'200': 1, 'hostname': 'CNC-TI-9-3SK', 'a_0': 0, 'r_0': 0, 'ISP': 'CNC', 'a_501': 0, 'a_502': 0, 'a_503': 0, '0': 0, '404': 0, 'r_503': 0, 'r_502': 0, 'r_501': 0, 'total': 5, 'type': 'FC', '503': 0, '408': 0}]
    name_dict, name_of_devices, starttime, devices_type
    '''
    wbk = xlwt.Workbook()
    # styleBlueBkg = xlwt.easyxf('pattern: pattern solid, fore_colour
    # ocean_blue; font: bold on;'); # 80% like
    style_red = xlwt.easyxf('font: color-index red, bold on')
    style_italic = xlwt.easyxf('font: color-index red, italic on')
    sheet = wbk.add_sheet('sheet 1')
    sheet.write(0, 0, 'device \ ISP, status')
    sheet.write(0, 1, 'ISP')
    sheet.write(0, 2, 'Type')
    sheet.write(0, 3, 'FirstLayer')
    EX_STATUS_LIST = ['0', '500', '501', '502', '503', '200']
    sheet.write(0, len(EX_STATUS_LIST) + 4, 'FAIL')
    sheet.write(0, len(EX_STATUS_LIST) + 5, 'TOTAL')
    sheet.write(0, len(EX_STATUS_LIST) + 6, 'PER')
    for j, v in enumerate(EX_STATUS_LIST):
        if v in ['500', '501', '502', '503']:
            sheet.write(0, j + 4, v, style_red)
        else:
            sheet.write(0, j + 4, v)

    # for i, device in enumerate(name_of_devices):
    for i, device in enumerate(data_list.values()):
        sheet.write(i + 1, 0, device['hostname'])
        sheet.write(i + 1, 1, device['ISP'])
        sheet.write(i + 1, 2, device['type'])
        sheet.write(i + 1, 3, device['firstLayer'])
        # total = 0
        for jj in range(0, len(EX_STATUS_LIST)):
            # if EX_STATUS_LIST[jj] in ['503']:
            # #     num = device[EX_STATUS_LIST[jj]] + device['r_0']
            # # else:
            #num = device[EX_STATUS_LIST[jj]]
            num = device.get(EX_STATUS_LIST[jj], 0)

            if EX_STATUS_LIST[jj] not in ['500', '501', '502', '503']:
                # total += num
                sheet.write(i + 1, jj + 4, num)
            else:
                sheet.write(i + 1, jj + 4, num, style_italic)
        # total = int(device['failed_total'] + device['200'])
        total = int(device.get('failed_total', 0) + device.get('200', 0))
        print("failed_total:%s" % device.get('failed_total', 0))
        print("200: %s" % device.get('200', 0))
        try:
            per = '{0:.2%}'.format(
                round(device.get('failed_total', 0) / float(total), 4))
        except:
            per = '{0:.2%}'.format(0)
        sheet.write(i + 1, len(EX_STATUS_LIST) + 4, device['failed_total'])
        sheet.write(i + 1, len(EX_STATUS_LIST) + 5, total)
        sheet.write(i + 1, len(EX_STATUS_LIST) + 6, per)

    # total_dic['TOTAL']['num'] = len(devices_type)
    wbk.save('%scount_preload_device_status_output%s.xls' %
             (LOG_DIR, date_str))
    endtime = time.time()
    logger.debug("process xls time:%s " % (endtime - connect_time))
    return endtime - connect_time


# 发邮件
def send(from_addr, to_addrs, subject, content, date_str):
    # msg = MIMEText(content)
    msg = MIMEMultipart()
    att1 = MIMEText(open('%scount_preload_device_status_output%s.xls' % (LOG_DIR, date_str), 'rb').read(),
                    'base64', 'utf-8')
    att1['Content-Type'] = 'application/octet-stream'
    att1['Content-Disposition'] = 'attachment;filename="count_preload_device_status_output%s.xls"' % (date_str)
    msg.attach(att1)
    # from_addr = 'nocalert@chinacache.com'
    msg['Subject'] = subject
    msg['From'] = from_addr
    msgText = MIMEText(content, 'html', 'utf-8')
    msg.attach(msgText)
    if type(to_addrs) == str:
        msg['To'] = to_addrs
    elif type(to_addrs) == list:
        msg['To'] = ','.join(to_addrs)

    logger.info('send msg: %s' % (msg, ))
    e_s = EmailSender(from_addr, to_addrs, msg)
    r_send = e_s.sendIt()
    if r_send != {}:
        logger.info('email sent through elder way!')
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


def group(n, sep=','):
    """
    把一个数字，按每隔３位一个逗号的情况输出，如１２３４５　　变为１２，３４５　
    :param n: 一个整数
    :param sep:
    :return:
    """
    # 变位字符串　　然后逆置
    s = str(abs(n))[::-1]
    groups = []
    i = 0
    while i < len(s):
        groups.append(s[i:i + 3])
        i += 3
    retval = sep.join(groups)[::-1]
    if n < 0:
        return '-%s' % retval
    else:
        return retval


def script_run():
    if len(sys.argv) > 2:
        if sys.argv[1] == 'help':
            print('python <filename> <8-digit-date>')
            exit(0)
        elif len(sys.argv) > 2:
            date_str = sys.argv[1]
    else:
        # 获取前一天的日期字符串　　如2016-04-26
        date_str = get_n_day_before_str(1)
    # try:
    #     old_date = datetime.datetime.now() - datetime.timedelta(days=2)
    #     old_date_str = old_date.strftime('%Y-%m-%d')
    #     old_file = '{0}{1}.txt'.format(LOG_DIR, old_date_str)
    #     # 删除前一日志信息
    #     os.remove(old_file)
    # except Exception, ex:
    #     logger.debug()
    # log_file = '{0}/{1}.txt'.format(LOG_DIR, date_str)
    # if os.path.isfile(log_file):
    #     os._exit(0)
    # 获取前n天开始时间和结束时间　统计的
    start_time, end_time = get_begin_end_time(1)

    content = 'Hi,ALL:<br/><br/>预加载系统每日下发任务情况统计表:<br/><br/>'
    # pre load daily task status statistics
    content += preload_statistical_everyday_new(date_str)

    content += '<br/>预加载系统每日预加载最终结果统计表:<br/><br/>'
    # 预加载系统每日信息
    content += preload_statistical_everyday(date_str)

    # print get_redis_data('2016-04-25')
    # 获取设备预加载的信息
    total_dic = StatisticPreloadDevicesInfo(
        conn, s1_db, start_time, end_time).build_data_structure()
    logger.debug("total_dic设备信息统计:%s" % total_dic)
    # print total_dic
    # print "total_dic:%s" % total_dic
    write_begin_time = time.time()
    write_excel(write_begin_time, date_str, total_dic['data'])
    content += '<br/><br/>失败设备TOP 10:<br/>'
    # 写入失败前１０的设备
    content += write_devices_failed_top(total_dic)
    # content += '<br/><br/>客户预加载量及预加载失败TOP 10:<br/>'
    content += '<br/><br/>客户预加载量TOP 10:<br/>'
    content += write_user_top_for_count(date_str)
    content += '<br/><br/><br/><br/><br/><br/><br/><br/><br/><br/><br/><br/><br/><br/><br/><br/>'
    content += '<br/><br/>预加载系统每日下发任务统计表(数量/占比):<br/>'
    content += write_code(total_dic)
    # content += '<br/><br/>预加载系统503分析(设备数及503分布占比):'
    # content += write_503_per(total_dic)

    content += '''<br/><br/> unknown:表示从RCMS中未获取到此设备的类型
                             0:执行完刷新,FC返回结果异常,解析失败,没有正常更新状态;<br/>
                             500:内部服务器错误<br/>
                             501: the preload response too slow  <br/>
                             502: The network is OK,But the preload does not work <br/>
                             503 can not reach the server <br/>
                             200 成功数量 <br/>
                             TOTAL 发送任务总数 <br/>
                             FAIL 失败数量 <br/>
                             PER 失败率 <br/>
                             具体信息请查看附件!'''

    send(email_from, email_to, '预加载任务统计及设备状态日报', content, date_str)
    logger.debug("send email end")
    # os.mknod(log_file)
    os._exit(0)
