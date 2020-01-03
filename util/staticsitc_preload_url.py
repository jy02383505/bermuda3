# coding:utf-8
__author__ = 'longjun.zhao'
# 根据表preload_url进行统计
#
# try:
#     from pymongo import Connection as MongoClient
# except:
#     from pymongo import MongoClient
import datetime
import time
import os
import logging
from core import database
from core.generate_id import ObjectId
import traceback
LOG_FILENAME = '/Application/bermuda3/logs/staticsitc_preload.log'
# LOG_FILENAME = '/home/rubin/logs/staticsitc_preload.log'
logging.basicConfig(filename=LOG_FILENAME,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger('staticsitc_preload')
logger.setLevel(logging.DEBUG)

#conn = MongoClient('mongodb://superAdmin:admin_refresh@223.202.52.136:27017/')
# 136变为主
# conn = MongoClient('mongodb://superAdmin:admin_refresh@223.202.52.135:27017/')
# db = conn.bermuda
# uri = 'mongodb://bermuda:bermuda_refresh@%s:27017,%s:27017,%s:27017/bermuda?replicaSet=bermuda_db' % (
#     '172.16.12.136', '172.16.12.135', '172.16.12.134')
# db = MongoClient(uri)['bermuda']
db = database.query_db_session()
s1_db = database.s1_db_session()


class PreloadCount(object):

    def __init__(self, collection, begin_date, end_date):
        self.collection = collection
        self.begin_date = begin_date  # 统计的开始时间
        self.end_date = end_date  # 统计的结束时间
        self.z_time = datetime.timedelta()
        self.avg_time = datetime.timedelta()  # 每天平均时间
        self.total = 0  # 记录每天总数
        self.statistic_finished = 0  # 状态为finished  的总数
        self.statistic_progress = 0  # 状态为progress的总数
        self.statistic_failed = 0  # 状态为failed的总数
        self.statistic_expired = 0  # 状态为expired的总数
        self.statistic_cancel = 0  # 状态为cancel的总数
        self.statistic_invalid = 0  # 状态为invalid的总数
        self.statistic_timer = 0  # 状态为itimer的总数
        self.usernames = []  # 当天用户名称的集合
        self.usernames_count = {}  # 当天用户名称对应预加载数目
        self.find_dic = {}                     #
        self.querys = ''
        self.usernames_failed_count = {}       # 当天用户名称对应的预加载失败的数目列表
        self.usernames_finished_count = {}     # 当天用户名称对应的预加载成功的数目列表
        self.usernames_progress_count = {}     # 当天用户名称对应的预加载正在进行中的列表
        self.send_success = 0                  # the number of successful
        self.send_failed = 0                   # the number of failed
        self.send_invalid = 0                  # the number of send of invalid
        self.send_timer = 0                    # the number of send of timer

    def total_of_day(self):
        """

        :return:返回统计时间段内，刷新的总数
        """
        self.total = self.collection.find(
            {"created_time": {"$gte": self.begin_date, "$lt": self.end_date}}).count()
        #self.total = self.collection.find().count()
        return self.total

    def total_of_finish(self):
        """

        :return:返回当天状态为 finished的总数
        """
        self.statistic_finished = self.collection.find({"created_time": {
                                                       "$gte": self.begin_date, "$lt": self.end_date}, "status": "FINISHED"}).count()
        return self.statistic_finished

    def total_of_progress(self):
        """

        :return: 返回当天状态为progress的总数
        """
        self.statistic_progress = self.collection.find({"created_time": {
                                                       "$gte": self.begin_date, "$lt": self.end_date}, "status": "PROGRESS"}).count()
        return self.statistic_progress

    def total_of_failed(self):
        """

        :return: 返回当天状态为failed的总数
        """
        self.statistic_failed = self.collection.find({"created_time": {
                                                     "$gte": self.begin_date, "$lt": self.end_date}, "status": "FAILED"}).count()
        return self.statistic_failed

    def total_of_expired(self):
        """

        :return: 返回当天状态为expired的总数
        """
        self.statistic_expired = self.collection.find({"created_time": {
                                                      "$gte": self.begin_date, "$lt": self.end_date}, "status": "EXPIRED"}).count()
        return self.statistic_expired

    def total_of_cancel(self):
        """

        :return: 返回当天状态为cancel的总数
        """
        self.statistic_cancel = self.collection.find({"created_time": {
                                                     "$gte": self.begin_date, "$lt": self.end_date}, "status": "CANCEL"}).count()
        return self.statistic_cancel

    def total_of_invalid(self):
        """

        :return:返回当天状态为invalid的总数
        """
        self.statistic_invalid = self.collection.find({"created_time": {
                                                      "$gte": self.begin_date, "$lt": self.end_date}, "status": "INVALID"}).count()
        return self.statistic_invalid

    def total_of_timer(self):
        """
        :return:返回当天状态为timer的总数
        """

        self.statistic_timer = self.collection.find({"created_time": {
                                                    "$gte": self.begin_date, "$lt": self.end_date}, "status": "TIMER"}).count()
        return self.statistic_timer

    def everage_finish(self):
        """
        此函数的作用是用来计算平均完成时间
        """
        ev_content = self.collection.find({"created_time": {
                                          "$gte": self.begin_date, "$lt": self.end_date}, "finish_time": {"$ne": "", "$exists": "true"}})
        ev_count = 0
        for cont in ev_content:
            c_time = cont.get("created_time")
            f_time = cont.get("finish_time")
            t_time = f_time - c_time
            ev_count += 1
            self.z_time += t_time
        try:
            self.avg_time = self.z_time / ev_count
        except:
            self.avg_time = datetime.timedelta()

    def count_names_des(self):
        """
        计算每一个用户每天（在一个时间段内，begin_date and end_date）内用户刷新数量
        """
        self.find_dic = {"created_time": {
            "$gte": self.begin_date, "$lt": self.end_date}}
        self.querys = self.collection.find(self.find_dic)
        for query in self.querys:
            u_name = query.get("username")
            if u_name not in self.usernames:
                self.usernames.append(u_name)
                self.usernames_count[u_name] = 1
            else:
                self.usernames_count[u_name] += 1
        self.usernames_count = sorted(
            list(self.usernames_count.items()), key=lambda t: t[1], reverse=True)

    def count_failed_names(self):
        """
        计算每一个用户每天（在一个时间段内，begin_date and end_date）内用户预加载失败的数量
        :return:
        """
        query_conditions = {"created_time": {
            "$gte": self.begin_date, "$lt": self.end_date}, "status": "FAILED"}
        result = self.collection.find(query_conditions)
        for res in result:
            u_name = res.get("username")
            if u_name not in list(self.usernames_failed_count.keys()):
                self.usernames_failed_count[u_name] = 1
            else:
                self.usernames_failed_count[u_name] += 1
        # 对self.usernames_failed_count  中　　根据用户失败的数量　　从大到小排序
        self.usernames_failed_count = sorted(
            list(self.usernames_failed_count.items()), key=lambda t: t[1], reverse=True)
        return self.usernames_failed_count

    def count_finished_names(self):
        """
        统计每一个用户每天（在一个时间段内，begin_date and end_date）内　　用户预加载成功的数量，　invalid 状态视为成功
        :return:
        """
        # 查询条件
        query_conditions = {"created_time": {"$gte": self.begin_date,
                                             "$lt": self.end_date}, "status": {"$in": ["FINISHED", "INVALID"]}}
        # 查询结果
        result = self.collection.find(query_conditions)
        for res in result:
            u_name = res.get("username")
            if u_name not in list(self.usernames_finished_count.keys()):
                self.usernames_finished_count[u_name] = 1
            else:
                self.usernames_finished_count[u_name] += 1
        # 对self.usernames_finished_count 中　　　根据用户成功的数量　　从大到小排序
        self.usernames_finished_count = sorted(
            list(self.usernames_finished_count.items()), key=lambda t: t[1], reverse=True)
        return self.usernames_finished_count

    def count_progress_names(self):
        """
        统计每一个用户每天（在一个时间段内，begin_date and end_date）内　　用户预加载正在进行中的数量
        :return:
        """
        # 查询条件
        query_conditions = {"created_time": {
            "$gte": self.begin_date, "$lt": self.end_date}, "status": "PROGRESS"}
        # 查询结果
        result = self.collection.find(query_conditions)
        for res in result:
            u_name = res.get("username")
            if u_name not in list(self.usernames_progress_count.keys()):
                self.usernames_progress_count[u_name] = 1
            else:
                self.usernames_progress_count[u_name] += 1

        # 对self.usernames_finished_count 中　　　根据用户成功的数量　　从大到小排序
        self.usernames_progress_count = sorted(
            list(self.usernames_progress_count.items()), key=lambda t: t[1], reverse=True)
        return self.usernames_progress_count

    def parse_preload_data_entrance(self):
        """
        handling tasks
        :return:
        """
        total_data = self.get_all_data()
        self.parse_preload_data(total_data)

    def get_all_data(self):
        """

        :return:
        """
        try:
            total_data = self.collection.find({"created_time": {"$gte": self.begin_date,
                                                                "$lt": self.end_date}}).batch_size(20)

        except Exception:
            logger.debug('get data from db error:%s' % e)
            return None
        return total_data

    def parse_preload_data(self, total_data):
        """

        :param total_data: the coursor  of mongo  preload
        :return:
        """
        if total_data:
            for data_t in total_data:
                status = data_t.get('status')
                if status == 'INVALID':
                    self.send_invalid += 1
                elif status in ['PROGRESS', 'FINISHED', 'CANCEL', 'EXPIRED', 'FAILED']:
                    # pay attention to the timing task  at this place
                    dev_id = data_t.get('dev_id')
                    retry_branch_id = data_t.get('retry_branch_id')
                    logger.debug("parse_preload_data retry_branch_id: %s" % retry_branch_id)
                    judge_result = self.judge_task_success_failed(dev_id, retry_branch_id)
                    if judge_result:
                        self.send_success += 1
                    else:
                        self.send_failed += 1
                elif status == 'TIMER':
                    self.send_timer += 1

    def judge_task_success_failed(self, dev_id, retry_branch_id):
        """

        :param dev_id: the _id of preload_dev
        :param retry_branch_id: the _id of retry_device_branch
        :return:
        """
        retry_branch_dict = self.get_data_from_retry_device_branch(retry_branch_id)
        if dev_id:
            try:
                preload_dev = s1_db.preload_dev.find_one({'_id': ObjectId(dev_id)})
            except Exception:
                logger.debug("get data error:%s" % traceback.format_exc())
                return False
            if not preload_dev:
                return False
            try:
                devices = preload_dev.get('devices')
                if devices:
                    # get content of all device info
                    devices_values = list(devices.values())
                    if devices_values:
                        for dev in devices_values:
                            code = dev.get('code')
                            a_code = dev.get('a_code')
                            r_code = dev.get('r_code')
                            name = dev.get('name')
                            if code == 200 or a_code == 200 or r_code == 200:
                                continue
                            elif name in retry_branch_dict:
                                if retry_branch_dict[name] == 200:
                                    continue
                            else:
                                if dev.get('name') not in ['CHN-JQ-2-3S3', 'CHN-JA-g-3WD']:
                                    d_id = preload_dev.get('_id')
                                    logger.debug("judge_task_success_failed d_id: %s|| devices_values: %s" % (d_id, devices_values))
                                return False
                    return True
            except Exception:
                logger.debug(
                    'judge_tak_success_failed parse data error:%s' % traceback.format_exc())
                return False

        return False

    def get_data_from_retry_device_branch(self, retry_branch_id):
        """
        get device info from retry_branch_id
        :param retry_branch_id: the _id of retry_device_branch
        :return: {'host1': 200, 'hots': 503}  dict
        """
        result_return = {}
        if not retry_branch_id:
            return result_return
        else:
            try:
                result = db.retry_device_branch.find_one(
                    {"_id": ObjectId(retry_branch_id)})
                logger.debug('success get data from retry_device_branch result:%s, retry_branch_id:%s' %
                             (result, retry_branch_id))
            except Exception:
                logger.debug('get data error from retry_device_branch retry_branch_id:%s, error content:%s' %
                             (retry_branch_id, e))
                return result_return
            try:
                if result:
                    devices = result.get('devices')
                    if devices:
                        for dev in devices:
                            name = dev.get('name')
                            branch_code = dev.get('branch_code')
                            if name and branch_code:
                                result_return[name] = branch_code
            except Exception:
                logger.debug(
                    'get_data_from_retry_device_branch parse data error:%s' % traceback.format_exc())

            return result_return


def run_count():
    #conn = MongoClient('mongodb://superAdmin:admin_refresh@223.202.52.135:27017/')
    #db = conn.bermuda
    connection = s1_db.preload_url
    now = datetime.datetime.now()
    today = now.date()
    result = {}

    begin_date = today - datetime.timedelta(days=1)
    #result["today"] = begin_date
    # print begin_date
    begin_date = datetime.datetime.combine(begin_date, datetime.time())
    # print begin_date
    logger.debug("begin_date:%s" % begin_date)
    result["date"] = begin_date.strftime("%Y-%m-%d")

    ret = db.statistical_preload.find({'date': result['date']})

    if ret.count() != 0:
        # if yesterday's data has been inserted into the database, do not carry
        # out the secondary query
        logger.debug("date field already exists, this script will not run")
        return

    end_date = datetime.datetime.combine(today, datetime.time())
    # print end_date
    #rc = PreloadCount( connection, "2014-04-25 00:00:00", "2015-04-29 00:00:00")
    rc = PreloadCount(connection, begin_date, end_date)
    result["total_preload_url"] = rc.total_of_day()  # 每天刷新的总数
    # print(result["total_preload_url"])
    logger.debug("total_preload_url:%s" % result["total_preload_url"])

    result["statistic_finished"] = rc.total_of_finish()  # finish  数量
    # print(result["statistic_finished"])
    logger.debug("statistic_finished:%s" % result["statistic_finished"])

    result["statistic_progress"] = rc.total_of_progress()  # progress  数量
    # print(result["statistic_progress"])\
    logger.debug("statistic_progress:%s" % result["statistic_progress"])

    result["statistic_failed"] = rc.total_of_failed()  # failed   数量
    # print(result["statistic_failed"])
    logger.debug("statistic_field:%s" % result["statistic_failed"])

    result["statistic_expired"] = rc.total_of_expired()  # expired 数量
    # print(result["statistic_expired"])
    logger.debug('statistic_expired:%s' % result["statistic_expired"])

    result["statistic_cancel"] = rc.total_of_cancel()  # cancel 数量
    # print(result["statistic_cancel"])
    logger.debug("statistic_cancel:%s" % result["statistic_cancel"])

    result["statistic_invalid"] = rc.total_of_invalid()  # invalid 数量
    # print(result["statistic_invalid"])
    logger.debug("statistic_invalid:%s" % result["statistic_invalid"])

    result["statistic_timer"] = rc.total_of_timer()  # timer 数量
    # print(result["statistic_timer"])
    logger.debug("statistic_timer:%s" % result['statistic_timer'])

    rc.everage_finish()
    result["everage_finish"] = (rc.avg_time.microseconds + (rc.avg_time.seconds + rc.avg_time.days *
                                                            24 * 3600) * 10 ** 6) / 10 ** 6  # average finish time   #平均finish时间转化为秒，然后保存
    rc.count_names_des()
    result["username_count_list"] = rc.usernames_count  #
    # 用户预加载失败列表
    result["username_failed_list"] = rc.count_failed_names()
    # 用户预加载成功列表
    result["username_finished_list"] = rc.count_finished_names()
    # 用户预加载正在进行中的列表
    result["username_progress_list"] = rc.count_progress_names()

    # add pre loading task statistics
    rc.parse_preload_data_entrance()
    result['send_success'] = rc.send_success
    result['send_failed'] = rc.send_failed
    result['send_invalid'] = rc.send_invalid
    result['send_timer'] = rc.send_timer
    try:
        # increased the index in the date field    insert result into mongo
        db.statistical_preload.insert(result)
    except Exception:
        logger.debug("insert into mongo error:%s" % e)

if __name__ == '__main__':
    run_count()
    os._exit(0)
