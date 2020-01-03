# -*- coding:utf-8 -*-
"""
Created on 2013-2-28

@author: li.chang peng.zhou
"""
import sys, traceback, logging
from datetime import datetime
# from bson.objectid import ObjectId
from core.generate_id import ObjectId
# log
import logging.handlers
from core import rcmsapi, postal, database, verify
from core.update import db_update
from celery.task import task
from .models import STATUS_RETRY_SUCCESS,STATUS_CONNECT_FAILED
from util import log_utils
from .config import config
import time
import codecs
from core import link_detection_all
import copy
from util import tools
import socket

# logger = logging.getLogger('dir_refresh')
# logger.setLevel(logging.DEBUG)
logger = log_utils.get_celery_Logger()
db = database.db_session()
db_s1 = database.s1_db_session()
REFRESH_WORKER_HOST = socket.gethostname()
@task(ignore_result=True)
def work(url):
    try:
        robot = RefreshRobotDIR()
        robot.dispatch(url.get('layer_type'), url)
    except Exception:
        logger.warning('dir_robot work error! do retry. error:%s' % traceback.format_exc())


class RefreshRobotDIR():
    def __init__(self):
        self.dev_id = ObjectId()
        self.db_dev = {}
        self.basic_info = {}
        self.last_basic_info_reload_time = 0
        self.use_old = config.getboolean("success_definition_strategy","use_old")
        self.basic_info_file_path = config.get('success_definition_strategy', 'basic_info_file')
        self.basic_info_reload_interval = config.get('success_definition_strategy', 'basic_info_reload_interval')
        self.isp_priority_list = config.get('success_definition_strategy','isp_priority').split(',')
        self.isp_priority_list = [item.strip().upper() for item in self.isp_priority_list]
        self.region_priority_list = config.get('success_definition_strategy','region_priority').split(',')
        self.region_priority_list = [item.strip().upper() for item in self.region_priority_list]
        self.fail_device_list = []

    def load_basic_info(self,file_path):
        basic_info = {}
        fp = codecs.open(file_path,'r',encoding='utf-8')
        for line in fp:
            line = line.strip()
            tmp_list = line.split('\t')
            if len(tmp_list) < 6:
                continue
            name = tmp_list[0].strip()
            name_list = name.split('-')
            use_name = '-'.join([name_list[0].strip(), name_list[1].strip()])
            #name isp city province region country,using the \t to seperate from each other
            basic_info[use_name.upper()] = [tmp_list[1].strip(),tmp_list[2].strip(),tmp_list[3].strip(),tmp_list[4].strip(),tmp_list[5].strip()]
        return basic_info

    def get_basic_info(self):
        # every basic_info_reload_interval, reload the self.basic_info from the basic_info.txt
        now = time.time()
        if self.last_basic_info_reload_time == 0 or now - self.last_basic_info_reload_time > self.basic_info_reload_interval:
            self.last_basic_info_reload_time = now
            self.basic_info = self.load_basic_info(self.basic_info_file_path)
        return self.basic_info

    def dispatch(self, layer_type, url):
        try:
            if not url.get('devices'):
                self.db_dev = self.init_db_device(url)
            else:
                self.db_dev = self.init_db_device_refresh_devices(url)

           # try:
           #     self.insert_refresh_result([url], self.db_dev.get('devices').values())
           # except Exception, e:
           #     logger.info('insert_refresh_result error urls:%s, error:%s' % ([url], traceback.format_exc()))
           #     logger.debug('init refresh_result end...')
            #TODO 测试
            # self.db_dev['devices']['BGP-SM-3-3go'] = {'status': 'OPEN', 'code': 0, 'name': 'BGP-SM-3-3go', 'type':'HPCC', 'serviceIp': None,\
            #    'serialNumber': '060120b3g7', 'host': '223.202.201.204', 'deviceId': None, 'firstLayer': False,\
            #         'port': 21108}

            # get max refresh level
            try:
                max_level = max([layerNum.get('layerNum') for layerNum in list(self.db_dev.get('devices').values())])
            except Exception:
                logger.debug("dir  dispatch get max level error:%s, work reqeust id:%s" % (traceback.format_exc(),
                                                                                          self.get_id_in_requestofwork()))
                max_level = 1
            logger.debug("dir dispatch work request id:%s, max_level:%s" % (self.get_id_in_requestofwork(), max_level))
            is_first_layer = True
            while max_level >= 0:
                try:
                    self.layer_refresh(url, max_level)
                except Exception:
                    logger.debug('dir refresh dispatch work request id:%s  layer:%s, is_first_layer:%s, error:%s' %
                                 (self.get_id_in_requestofwork(), max_level, is_first_layer, traceback.format_exc()))
                max_level -= 1
            # the bottom level refresh
            # try:
            #     self.layer_refresh(url, 1, False)
            # except Exception, e:
            #     logger.debug('dir refresh dispatch work request id:%s  layer:1 , is_first_layer: false, error:%s' %
            #                  (self.get_id_in_requestofwork(), traceback.format_exc()))
            # logger.debug("dir dispatch init_db_device successed ! worker_id: %s ,urls_id:  %s !" % (
            #     self.get_id_in_requestofwork(), url.get("id")))

            self.db_dev["finish_time"] = datetime.now()

            # dispatch = {
            #     'one': lambda: self.one_layer_refresh(url),
            #     'two': lambda: self.two_layer_refresh(url),
            #     'three': lambda: self.three_layer_refresh(url),
            # }
            # return dispatch.get(layer_type)()
        except Exception:
            logger.debug("dir dispatch error=%s" % traceback.format_exc())
        finally:
            self.save_device_results(url)

    def init_db_device(self, url):
        worker_hostname = REFRESH_WORKER_HOST
        devs = rcmsapi.getDevices(url.get("channel_code"))
        if url.get("layer_type") != "one":
            devs += rcmsapi.getFirstLayerDevices(url.get("channel_code"))
        db_device = {"devices": verify.create_dev_dict(devs), "unprocess": len(devs), "created_time": datetime.now(),
                     "_id": self.dev_id}
        # dev_id = db.device.insert(db_device)
        url["dev_id"] = self.dev_id
        #db_update(db.url, {"_id": ObjectId(url.get("id"))}, {"$set": {"dev_id": self.dev_id}})
        db_update(db.url, {"_id": ObjectId(url.get("id"))}, {"$set": {"dev_id": self.dev_id,"worker_host": worker_hostname,"recev_host": url.get("recev_host","")}})
        logger.debug("dir_init_db_device successed ,url_id : %s ,dev_id = %s " % (url.get("id"), self.dev_id))
        return db_device

    def init_db_device_refresh_devices(self, url):
        """

        Args:
            url:

        Returns:

        """
        worker_hostname = REFRESH_WORKER_HOST
        devs = url.get('devices')

        db_device = {"devices": verify.create_dev_dict(devs), "unprocess": len(devs), "created_time": datetime.now(),
                     "_id": self.dev_id}
        # dev_id = db.device.insert(db_device)
        url["dev_id"] = self.dev_id
        #db_update(db.url, {"_id": ObjectId(url.get("id"))}, {"$set": {"dev_id": self.dev_id}})
        db_update(db.url, {"_id": ObjectId(url.get("id"))}, {"$set": {"dev_id": self.dev_id,"worker_host": worker_hostname,"recev_host": url.get("recev_host","")}})
        logger.debug("dir_init_db_device successed ,url_id : %s ,dev_id = %s " % (url.get("id"), self.dev_id))
        return db_device

    # def three_layer_refresh(self, url):
    #     devs = [dev for dev in self.db_dev.get("devices").values() if dev.get("firstLayer")]
    #     postal.do_send_dir(url, devs)
    #     logger.debug("dir_three_layer_refresh successed url_id = %s ,dev_id = %s , dev_count = %d" % (
    #         url.get("id"), url.get("dev_id"), len(devs)))
    #     self.two_layer_refresh(url)
    #
    # def two_layer_refresh(self, url):
    #     dev_dict = self.db_dev.get("devices")
    #     devs = [dev for dev in dev_dict.values() if dev.get("firstLayer")]
    #     self.db_dev["unprocess"] = self.db_dev.get("unprocess") - len(devs)
    #     results = postal.do_send_dir(url, devs)
    #     self.get_refresh_results(results)
    #     logger.debug("dir_two_layer_refresh succeed url_id = %s ,dev_id = %s , dev_count = %d response_count = %d" % (
    #         url.get("id"), url.get("dev_id"), len(devs), len(results)))
    #     self.one_layer_refresh(url)
    #
    # def one_layer_refresh(self, url):
    #     devs = [dev for dev in self.db_dev.get("devices").values() if not dev.get("firstLayer")]
    #     self.db_dev["unprocess"] = 0
    #     results = postal.do_send_dir(url, devs)
    #     self.db_dev["finish_time"] = datetime.now()
    #     self.get_refresh_results(results)
    #     logger.debug("dir_one_layer_refresh succeed url_id = %s ,dev_id = %s , dev_count = %d response_count = %d" % (
    #         url.get("id"), url.get("dev_id"), len(devs), len(results)))

    def layer_refresh(self, url, layer_level):

        logger.debug(' dir layer_refresh starting ... worker_id:%s, dev_id:%s, layer_level:%s'
                     % (self.get_id_in_requestofwork(), url.get('dev_id'), layer_level))
        devs = [dev for dev in list(self.db_dev.get("devices").values()) if dev.get('layerNum')==layer_level]


        self.db_dev["unprocess"] -= len(devs)
        results = postal.do_send_dir(url, devs)


        self.get_refresh_results(results)
        logger.debug(
            "dir layer_refresh successed worker_id: %s ,dev_id: %s, layer_level:%s, "
                   "dev_count = %d response_count = %d" % (self.get_id_in_requestofwork(), url.get("dev_id"),
                                                           layer_level, len(devs), len(results)))
    def get_id_in_requestofwork(self):
        print(type(work))
        print(type(work.request))

        return work.request.id

    def is_priority_device(self,device):
        """
        judge the device is priority or not
        :param device:
        :return:
        """
        self.basic_info = self.get_basic_info()
        dev_name = device.get('name', '')
        if not dev_name.strip():
            return False
        name_list = dev_name.split('-')
        # we don not know whether is an important one, for caution
        if len(name_list) < 2:
            logger.warning('device:%s name is wrong' % (dev_name))
            return True
        use_dev_name = '-'.join([name_list[0].strip(), name_list[1].strip()])
        if use_dev_name.upper() in self.basic_info:
            isp, city, province, region, country = self.basic_info.get(use_dev_name)
            if isp.upper() not in self.isp_priority_list:
                return False
            if region.upper() not in self.region_priority_list:
                return False
            return True
        else:
            logger.warning('device:%s is not in basic info,maybe basic info need to be refresh' % (use_dev_name))
            # if the device_name not in our basic info,we keep is a important one,because we do not know whether it is, for caution
            return True

    def save_device_results(self, url):
        tt1 = time.time()
        db.device.insert(self.db_dev)
        tt2 = time.time()
        logger.debug('save_device_results devices insert over by %s s ,dev_id %s' %(tt2-tt1,self.db_dev.get('_id')))
        logger.debug('init refresh_result start...')
        # try:
        #     self.insert_refresh_result([url], self.db_dev.get('devices').values())
        # except Exception, e:
        #     logger.info('insert_refresh_result error urls:%s, error:%s' % ([url], traceback.format_exc()))
        # logger.debug('init refresh_result end...')


        # if devices is null, we think is a successful one, we can get the info from db.device to know that the devices is empty.
        
        
        # devices_list_failed_test = []
        # dev_failed_test = {}
        # dev_failed_test['host'] = '58.67.207.6'
        # dev_failed_test['name'] = 'BGP-GZ-5-3g3'
        # dev_failed_test['firstLayer'] = False
        # devices_list_failed_test.append(dev_failed_test)


        if not self.db_dev.get("devices"):
            #  url refresh at this place, which is finished by default
            verify.verify([url], db)
            # verify.verify([url], db, 'FAILED')
        else:
            # test
            #link_detection.link_detection.delay([url], devices_list_failed_test, "ret")
            if self.fail_device_list:
            # if devices_list_failed_test:
                verify.verify([url], db, 'FAILED', self.db_dev)
                try:
                    # link_detection.link_detection.delay(rid, failed_dev_list)

                    link_detection_all.link_detection_refresh.delay([url], self.fail_device_list, "ret")

                    # link_detection.link_detection.delay([url], self.fail_device_list,"ret")

                    # test
                    # link_detection.link_detection.delay([url], devices_list_failed_test, "ret")
                except Exception:
                    logger.error('save_device_results [error]: %s' % (traceback.format_exc()))
                #verify.verify([url], db, 'FAILED', self.db_dev)
            else:
                # if self.conflict:
                #     verify.verify(urls, db, 'CONFLICT', self.db_dev)
                # else:
                verify.verify([url], db, devs=self.db_dev)
        tt3 = time.time()
        logger.debug('save_device_results dir update over by %s s ,dev_id %s' %(tt3-tt2,self.db_dev.get('_id')))


    def get_refresh_results(self, results):
        for ret in results:
            self.db_dev.get("devices").get(ret.get("name"))["code"] = ret.get("code")
            self.db_dev.get("devices").get(ret.get("name"))["total_cost"] = ret.get("total_cost")
            self.db_dev.get("devices").get(ret.get("name"))["connect_cost"] = ret.get("connect_cost")
            self.db_dev.get("devices").get(ret.get("name"))["response_cost"] = ret.get("response_cost")
            self.db_dev.get("devices").get(ret.get("name"))["a_code"] = ret.get("a_code")
            self.db_dev.get("devices").get(ret.get("name"))["r_code"] = ret.get("r_code")
            if ret.get("code") > STATUS_RETRY_SUCCESS:
                self.fail_device_list.append(self.db_dev.get("devices").get(ret.get("name")))


    def insert_refresh_result(self, urls, devices):
        """
        according urls and devices, insert refresh_result
        Args:
            urls:
            devices:

        Returns:

        """
        devices_copy = copy.deepcopy(devices)
        hpcc_dev = []
        try:
            if urls:
                for url in urls:
                    _id = str(url.get('id'))
                    for dev in devices_copy:
                        dev['session_id'] = _id
                        dev['result'] = '0'
                        dev['result_gzip'] = '0'
                        if dev.get('type') == 'HPCC' and dev.get('status') == 'OPEN':
                            hpcc_dev.append(dev)
                    logger.debug('refresh session_id:%s' % _id)
                    str_num = ''
                    try:
                        num_str =config.get('refresh_result', 'num')
                        str_num = tools.get_mongo_str(str(_id), num_str)
                    except Exception:
                        logger.debug('get number of refresh_result error:%s' % traceback.format_exc())
                    db_s1['refresh_result' + str_num].insert(hpcc_dev)
                    hpcc_dev = []
                    for dev in devices_copy:
                        if '_id' in dev:
                            dev.pop("_id")
                logger.debug('insert_refresh_result insert refresh_result success data')
        except Exception:
            logger.info('insert_refresh_result error:%s' % traceback.format_exc())
            return
