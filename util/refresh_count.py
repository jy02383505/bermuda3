#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Created by vance on 6/19/14.

__author__ = 'vance'
__doc__ = """每日刷新任务统计脚本"""
__ver__ = '1.0'

import datetime
import logging
# import sys
import string
from core import database
import collections
import os

try:
    from cache import rediscache
except:
    pass

# reload(sys)
#sys.setdefaultencoding('utf8')

LOG_FILENAME = '/Application/bermuda3/logs/refresh_count.log'
logging.basicConfig(filename=LOG_FILENAME,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger('refresh_count')
logger.setLevel(logging.DEBUG)

db = database.db_session()
q_db = database.query_db_session()
STRLEN = 18


class RefreshCount(object):
    def __init__(self, collection, begin_date, end_date):
        self.collection = collection
        self.begin_date = begin_date
        self.end_date = end_date
        self.total = 0
        self.total_finish = 0
        self.total_dir = 0
        self.total_no_finish = 0
        self.z_time = datetime.timedelta()
        self.fastest_time = self.z_time
        self.slowest_time = self.z_time
        self.total_time = self.z_time
        self.querys = ''
        self.find_dic = {}
        self.finish_num = 0
        self.fail_num = 0
        self.usernames = []
        self.user_channels = {}
        self.one_minute = 0
        self.two_minute = 0
        self.three_minute = 0
        self.four_minute = 0
        self.five_minute = 0
        self.ten_minute = 0
        self.after_ten_minute = 0
        self.usernames_count = {}
        self.usernames_fail_count = {}

    def write_log(self, content):
        file_name = self.begin_date.strftime("%Y%m%d.log")
        log_dir = '/Application/bermuda3/logs/refresh_count'
        if not os.path.exists(log_dir):
            os.mkdir(log_dir)
        log_file = '{0}/refresh_count_{1}'.format(log_dir, file_name)
        f = file("%s" % log_file, "a")
        f.write(content + "\r\n")
        f.flush()
        f.close()

    def total_of_day(self):
        """
        一天的总量

        """
        # db.url.count( { "created_time": { "$gte": new Date('2014-06-17'), $lt: new Date('2014-06-18')}})
        self.total = self.collection.find({"created_time": {"$gte": self.begin_date, "$lt": self.end_date}}).count()
        return self.total

    def total_of_day_finish(self):
        """
       一天内完成的量

        """

        self.total_finish = self.collection.find({"created_time": {"$gte": self.begin_date, "$lt": self.end_date},
                                                  "finish_time": {"$exists": "true"}}).count()
        return self.total_finish

    def total_of_day_dir(self):
        """
       一天内完成的目录量

        """

        self.total_dir = self.collection.find({"created_time": {"$gte": self.begin_date, "$lt": self.end_date},
                                                  "finish_time": {"$exists": "true"}, "isdir": True}).count()
        return self.total_dir

    def total_of_day_no_finish(self):
        """

        一天内没有结束时间的数量
        """
        self.total_no_finish = self.total - self.total_finish
        return self.total_no_finish

    def count_query_min(self):
        self.find_dic = {"created_time": {"$gte": self.begin_date, "$lt": self.end_date},
                         "finish_time": {"$exists": "true"}}
        self.querys = self.collection.find(self.find_dic)
        total = 0
        dic_m = collections.defaultdict(int)
        dic = collections.defaultdict(int)
        for query in self.querys:
            total += 1
            c_time = query.get("created_time")
            dic[c_time.minute] += 1
        r_l = sorted(dic.values())
        max_data = r_l[-1] if r_l else 0
        # dor = collections.OrderedDict(sorted(dic.items(), key=lambda t: t[1]))

        dic_m['{0}-{1}'.format(self.begin_date.hour, self.end_date.hour)] = {'total': total, 'max': max_data}

        r_str = '{0} - {1}: {2} {3}'.format(self.begin_date, self.end_date, total, max_data)
        print(r_str)
        print(dic_m)
        return r_str, dic_m

    def count_query_des(self):
        self.find_dic = {"created_time": {"$gte": self.begin_date, "$lt": self.end_date},
                         "finish_time": {"$exists": "true"}}
        self.querys = self.collection.find(self.find_dic)
        for query in self.querys:
            f_time = query.get("finish_time")
            c_time = query.get("created_time")
            t_time = f_time - c_time
            # print t_time,self.fastest_time
            if t_time < self.fastest_time or self.fastest_time == self.z_time:
                self.fastest_time = t_time
            if t_time > self.slowest_time or self.slowest_time == self.z_time:
                self.slowest_time = t_time
            if t_time <= datetime.timedelta(seconds=60):
                self.one_minute += 1
            if datetime.timedelta(seconds=60) <= t_time < datetime.timedelta(seconds=120):
                self.two_minute += 1
            if datetime.timedelta(seconds=120) <= t_time < datetime.timedelta(seconds=180):
                self.three_minute += 1
            if datetime.timedelta(seconds=180) <= t_time < datetime.timedelta(seconds=240):
                self.four_minute += 1
            if datetime.timedelta(seconds=240) <= t_time < datetime.timedelta(seconds=300):
                self.five_minute += 1
            if datetime.timedelta(seconds=300) <= t_time < datetime.timedelta(seconds=600):
                self.ten_minute += 1
            if t_time >= datetime.timedelta(seconds=600):
                self.after_ten_minute += 1

            self.total_time += t_time
            u_name = query.get("username")
            status = query.get("status")
            if u_name not in self.usernames:
                self.usernames.append(u_name)
                self.user_channels[u_name] = []
                self.usernames_count[u_name] = 1
            else:
                self.usernames_count[u_name] += 1
            if status  in ["FAILED"]:
                if u_name not in list(self.usernames_fail_count.keys()):
                    self.usernames_fail_count[u_name] = 1
                else:
                    self.usernames_fail_count[u_name] += 1

            u_channel = query.get("channel_code")

            if u_channel not in self.user_channels[u_name]:
                self.user_channels[u_name].append(u_channel)
        # self.usernames_count = collections.OrderedDict(sorted(self.usernames_count.items(), key=lambda t: t[1]))#python2.6没有OrderedDict
        self.usernames_count = sorted(list(self.usernames_count.items()), key=lambda t: t[1], reverse=True)
        self.usernames_fail_count = sorted(list(self.usernames_fail_count.items()), key=lambda t: t[1], reverse=True)

    def finish_fail(self):

        """
        统计成功与失败的数量

        """
        finish_dic = {"status": "FINISHED"}
        failed_dic = {"status": "FAILED"}
        finish_dic.update(self.find_dic)
        failed_dic.update(self.find_dic)
        self.finish_num = self.collection.find(finish_dic).count()
        self.fail_num = self.collection.find(failed_dic).count()

    def avg_time(self):
        """
        平均一条实行时间

        """
        if self.total_finish:
            return self.total_time / self.total_finish
        else:
            return 0

    def count_username(self):
        return len(self.usernames)

    def count_user_channels(self):
        user_num_dic = {}
        channels_num = 0
        for username, channels in list(self.user_channels.items()):
            if username not in list(user_num_dic.keys()):
                user_num_dic[username] = 0
            user_num_dic[username] = len(channels)
            channels_num += len(channels)
        user_num_dic_g = {'Total': channels_num}
        user_num_dic_g.update(user_num_dic)
        return user_num_dic_g


def format_string(strs):
    return string.ljust(strs, STRLEN)


def count_every_hour(begin_date):
    """
    按小时统计总量及最高峰值
    :param begin_date:
    :return:
    """
    st = datetime.datetime.combine(begin_date, datetime.time.min)
    et = datetime.datetime.combine(begin_date, datetime.time.max)
    d_add = datetime.timedelta(hours=1)
    r_list = []

    while st < et:
        tmp_et = st + d_add
        # print st, tmp_et
        rc = RefreshCount(q_db.url, st, tmp_et)
        r_s, r_d = rc.count_query_min()
        # rc.write_log("%s : %s" % (format_string('Total time '), rc.total_time))
        r_list.append(r_d)
        rc.write_log("%s" % r_s)
        st = tmp_et
    return r_list


def write_log(begin_date, rc, result):
    """
     write log
    :param begin_date:
    :param rc:
    :param result:
    """
    rc.write_log("%s : %s" % (format_string('Date '), begin_date.strftime("%Y-%m-%d")))
    rc.write_log("%s : %s" % (format_string('Total refresh '), result["total_refresh"]))
    rc.write_log("%s : %s" % (format_string('Finish refresh'), result["finish_refresh"]))
    rc.write_log("%s : %s" % (format_string('No finish'), result["progress_refresh"]))
    rc.write_log("%s : %s" % (format_string('Total dir'), result["total_dir"]))
    rc.write_log("%s : %s" % (format_string('Fastest time'), result["fastest_time"]))
    rc.write_log("%s : %s" % (format_string('Slowest time'), result["slowest_time"]))
    rc.write_log("%s : %s" % (format_string('Avg time'), result["avg_time"]))
    rc.write_log("%s : %s" % (format_string('Success num '), result["success_num"]))
    rc.write_log("%s : %s" % (format_string('Failed num'), result["failed_num"]))
    rc.write_log("%s : %s" % (format_string('one minutes num '), result["one_minutes_num"]))
    rc.write_log("%s : %s" % (format_string('two minutes num'), result["two_minutes_num"]))
    rc.write_log("%s : %s" % (format_string('three minutes num'), result["three_minutes_num"]))
    rc.write_log("%s : %s" % (format_string('four minutes num'), result["four_minutes_num"]))
    rc.write_log("%s : %s" % (format_string('five minutes num'), result["five_minutes_num"]))
    rc.write_log("%s : %s" % (format_string('ten minutes num'), result["ten_minutes_num"]))
    rc.write_log("%s : %s" % (format_string('after ten minutes num'), result["more_than_ten_minutes_num"]))
    rc.write_log("%s : %s" % (format_string('Username num'), result["username_num"]))
    rc.write_log("%s : %s" % (format_string('Username list'), result["username_list"]))
    rc.write_log("%s : %s" % (format_string('Username count list'), result["username_count_list"]))
    rc.write_log("%s : %s" % (format_string('Username faild count list'), result["username_fail_count_list"]))
    rc.write_log("HOUR       TOTAL      MAX:")


# def del_redis():
#     """
#     删除存放redis的用户列表
#
#     """
#     try:
#         print "start del redis"
#         #rediscache.del_redis()
#         print "del redis ok"
#     except Exception, e:
#         print e


def run_count():
    now = datetime.datetime.now()
    today = now.date()
    begin_date = today - datetime.timedelta(days=1)
    begin_date = datetime.datetime.combine(begin_date, datetime.time())
    end_date = datetime.datetime.combine(today, datetime.time())
    result = {}
    rc = RefreshCount(q_db.url, begin_date, end_date)
    rc.write_log("The daily statistics :")

    result["date"] = begin_date.strftime("%Y-%m-%d")  # 日期
    result["total_refresh"] = rc.total_of_day()  # 刷新总量
    result["finish_refresh"] = rc.total_of_day_finish()  # 完成数量
    result["progress_refresh"] = rc.total_of_day_no_finish()  # 执行中数量
    result["total_dir"] = rc.total_of_day_dir()  # 完成的目录的数量

    rc.count_query_des()

    # result["fastest_time"] = rc.fastest_time.total_seconds()#python2.6 不支持
    result["fastest_time"] = (rc.fastest_time.microseconds + (
        rc.fastest_time.seconds + rc.fastest_time.days * 24 * 3600) * 10 ** 6) / 10 ** 6  # 最快完成（单位秒）
    # result["slowest_time"] = rc.slowest_time.total_seconds()
    result["slowest_time"] = (rc.slowest_time.microseconds + (
        rc.slowest_time.seconds + rc.slowest_time.days * 24 * 3600) * 10 ** 6) / 10 ** 6  # 最慢完成（秒）
    # result["avg_time"] = rc.avg_time().total_seconds()
    result["avg_time"] = (rc.avg_time().microseconds + (
        rc.avg_time().seconds + rc.avg_time().days * 24 * 3600) * 10 ** 6) / 10 ** 6  # 平均完成（秒）
    # rc.write_log("%s : %s" % (format_string('Total time '), rc.total_time))

    rc.finish_fail()
    result["success_num"] = rc.finish_num  # 成功数
    result["failed_num"] = rc.fail_num  # 失败数
    result["one_minutes_num"] = rc.one_minute  # 一分钟内完成数
    result["two_minutes_num"] = rc.two_minute  # 两分钟内完成数
    result["three_minutes_num"] = rc.three_minute  # 三分钟内完成数
    result["four_minutes_num"] = rc.four_minute  # 四分钟内完成数
    result["five_minutes_num"] = rc.five_minute  # 五分钟内完成数
    result["ten_minutes_num"] = rc.ten_minute  # 十分钟内完成数
    result["more_than_ten_minutes_num"] = rc.after_ten_minute  # 超过十分钟完成的数

    result["username_num"] = rc.count_username()  # 用户数
    result["username_list"] = rc.usernames  # 用户列表
    result["username_count_list"] = rc.usernames_count  # 用户任务数
    result["username_fail_count_list"] = rc.usernames_fail_count #用户失败任务数

    # rc.write_log("%s : %s" % (format_string('Channels num list'),rc.count_user_channels()))
    # rc.write_log("%s : %s" % (format_string('Channels list'),rc.user_channels))

    write_log(begin_date, rc, result)

    hour_list = count_every_hour(begin_date)
    # print hour_list
    result["every_hour_tasks"] = hour_list  # 统计每小时的任务数及最高峰值（分钟）
    # print result
    db.statistical.insert(result)
    print((datetime.datetime.now() - now))
    os._exit(0)
    #del_redis()


if __name__ == '__main__':
    run_count()
    # del_redis()
    os._exit(0)
