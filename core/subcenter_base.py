#! -*- encoding=utf-8 -*-
"""
@version: python2.7
@author: rubin
@license: Apache Licence
@contact: longjun.zhao@chinacache.com
@site:
@software: PyCharm
@file: subcenter_base.py
@time: 9/19/17 8:13 PM
"""
from .command_factory import get_command_json as get_command_preload
from core.link_detection_all import getDirCommand
from core.cert_trans_postal import get_command
from core.cert_query_postal import get_command as get_cert_query_command
from core.transfer_cert_postal import get_command as get_transfer_cert_command
import simplejson as json
import traceback
import asyncio
from .asyncpostal import AioClient, doTheLoop
from bson.objectid import ObjectId
import core.redisfactory as redisfactory
from util import log_utils
import time
import datetime
import zlib
from copy import deepcopy
import uuid
from xml.dom.minidom import parseString
from core import database
db_db = database.db_session()

subcenter_factory = redisfactory.getDB(7)
EXPIRETIME = 600
EXPIRETIME_BEST = 10
logger = log_utils.get_cert_query_worker_Logger()

FIRST_HOST = 3

class SubBase(object):
    def __init__(self, dict_sub, **kwargs):

        self.failed_dev_list = dict_sub.get('failed_dev_list')
        self.branch_center_list = dict_sub.get('branch_center_list')
        self.subcenter_port = dict_sub.get('subcenter_port')
        self.subcenter_task_mq = dict_sub.get('subcenter_task_mq')
        self.subcenter_result_mq = dict_sub.get('subcenter_result_mq')
        self.task_mq = dict_sub.get('task_mq')
        self.is_compressed = dict_sub.get('is_compressed',False)
        self.edge_port = dict_sub.get('edge_port')
        self.edge_path = dict_sub.get('edge_path')
        # if failed dev have relation with branch_center, send to relation sub center, else send all
        self.relation_sub_failed_dev = self.get_best_road()
        # the connection to mongo
        self.db = dict_sub.get('db')
        self.tasks = dict_sub.get('tasks')
        self.connect_timeout = dict_sub.get('connect_timeout', 3)
        self.response_timeout = dict_sub.get('response_timeout', 5)
        self.command = self.generate_command()
        self.return_path = dict_sub.get('return_path')

        self.sub_task_id = None
        self.orgin_ids = None
        self.body = None

        # self.get_best_road_dev_dic = self.get_best_road_dev()
    def generate_command(self):
        pass
    def init_mongo(self):

        try:
            res = {}
            # worker_branch_list = list(set(self.branch_center_list).intersection(set(self.relation_sub_failed_dev.keys())))
            for k, v in list(self.relation_sub_failed_dev.items()):
                res[k.replace('.', '#')] = [sub_center.split(':')[0] for sub_center in v]

            sub_task_id = self.db[self.subcenter_task_mq].insert(
                {'ralation_faildev_subcenter': res, 'origin_ids': self.orgin_ids, 'command': self.command,
                 'created_time': datetime.datetime.now()})
            list_id = []
            for task in self.tasks:
                list_id.append(ObjectId(task.get("_id")))
                #self.db[self.cert_task].update({"_id": ObjectId(task.get("_id"))},{"$set": {'retry_branch_id': ObjectId(sub_task_id)}})
            self.db[self.task_mq].update_many({"_id": {"$in":list_id}},{"$set": {'retry_branch_id': ObjectId(sub_task_id)}})

            return str(sub_task_id)
            # s_id = self.db[self.subcenter_task].insert({"ralation_dev_subcenter":res,"command":self.command})

        except Exception:
            logger.debug("link_detection_refresh error:%s" % traceback.format_exc())

    def generate_orgin_ids(self):

        try:
            origin_task_ids = []
            for task in self.tasks:
                # rid = ObjectId()
                origin_task_ids.append(task["_id"])
            return origin_task_ids

        except Exception:
            logger.debug("get task id error:%s" % traceback.format_exc())

    def generate_body(self):
        """
        generate the body
        :param failed_dev_list: [{'host': 'xxxxx', 'name': 'xxxx'}]
        :param edge_port:
        :param command:
        :return:
        """
        try:
            result = {}
            for dev, subcent_list in list(self.relation_sub_failed_dev.items()):
                for subcent in subcent_list:
                    if subcent not in result:
                        result[subcent] = [dev]
                    else:
                        result[subcent].append(dev)
            send_body_all = {}
            for subcenter_host_port in result:

                send_body = {}
                #send_body['edge_list'] = []
                # data['target_url'] = ["http://"+dev+":"+str(self.edge_port)+"/" for dev in self.relation_sub_failed_dev[subcenter_host_port]]
                for dev in result[subcenter_host_port]:
                    logger.debug("edge_path is %s"% self.edge_path)
                    if self.edge_path:
                        target_url = "http://" + dev + ":" + str(self.edge_port) + "/" + str(self.edge_path)
                    else:
                        target_url = "http://" + dev + ":" + str(self.edge_port) + "/"
                    #data['target_url'] = "http://" + dev + ":" + str(self.edge_port) + "/"
                    send_body.setdefault('edge_list',[]).append({'target_url':target_url})
                send_body['command'] = self.command
                send_body['is_compressed'] = self.is_compressed
                send_body['callback'] = self.return_path
                send_body['callback_params'] = [self.sub_task_id]
                send_body_t = deepcopy(send_body)
                send_body_all[subcenter_host_port] = send_body_t
            # self.body = json.dumps(send_body)
            return send_body_all
        except Exception:
            logger.debug("generate_body error:%s" % traceback.format_exc())
            return {}

    def send_result(self):
        """
        send data to branch_center_list, get result
        :param branch_center_list:
        :param body:
        :param path:
        :param connect_timeout:
        :param response_timeout:
        :return:
        """
        result_list = []
        clients = []
        my_map = {}
        # path = "/probetask"
        for dev in self.body:
            logger.debug("dev is %s" % dev)
            try:
                dev_temp = dev.split(":")
                subcenter_host = dev_temp[0]
                subcenter_port = int(dev_temp[1])
                if self.is_compressed == True:
                    body_send = zlib.compress(json.dumps(self.body[dev]))
                else:
                    body_send = json.dumps(self.body.get(dev))
                if body_send:
                    clients.append(
                        AioClient(subcenter_host, subcenter_port, '', body_send, self.connect_timeout, self.response_timeout))
            except Exception:
                logger.debug("send content error: %s" % traceback.format_exc())

        results = doTheLoop(clients, logger)
        
        for r in results:
            dict_t = {}
            dict_t['host'] = r.get('host')
            dict_t['code'] = r.get('response_code')
            result_list.append(dict_t)
        return result_list

    def get_best_road(self):
        """
        according host, get best road, from redis,  if not have, send all branch_center_list
        :param host:  the host of edge dev
        :param branch_center_list:  all branch center host:21109
        :return: [branch_center_ip1, branch_center_ip2,xxx, xxx]
        """

        map_t = {}
        try:
            for failed_dev in self.failed_dev_list:
                branch_list = []
                host = failed_dev.get('host')
                branch_center = subcenter_factory.get('central_best_road' + host)
                # branch_center is exits
                if branch_center:
                    branch_redi_list = eval(branch_center)
                    if branch_redi_list and len(branch_redi_list):
                        for branch in branch_redi_list:
                            branch_list.extend(branch + ":"+str(self.subcenter_port))
                    else:
                        subcenter_factory.delete("central_best_road_" + host)
                        #subcenter_factory.delete("central_link_" + host + "_" + branch_center)
                        branch_list.extend(self.branch_center_list)
                else:
                    keys = subcenter_factory.keys("central_link_" + host + "*")
                    # have keys
                    logger.debug('get best road keys  %s'%(keys))
                    k_v = {}
                    if keys and len(keys) > 0:
                        for key in keys:
                            k_v[key] = subcenter_factory.get(key)#int(subcenter_factory.get(key))
                        # 取时间最小的key

                        sub_min_list = sorted(k_v, key=lambda x: k_v[x])
                        flag = False
                        # if len(sub_min_list) >= FIRST_HOST:
                        #     send_dev = sub_min_list[:FIRST_HOST]
                        # else:
                        #     send_dev = sub_min_list
                        #logger.debug('get best road send_dev %s'%(send_dev))
                        best_road_sor_list = []
                        for key in sub_min_list:
                            if len(best_road_sor_list) >=FIRST_HOST:
                                break
                            else:
                                logger.debug('get best road key is %s'%(key.rsplit('_', 1)[1] + ":"+str(self.subcenter_port)))
                                logger.debug('get best road branch_center_list %s'%(self.branch_center_list))
                                if key.rsplit('_', 1)[1] + ":"+str(self.subcenter_port) in self.branch_center_list:
                                    branch_list.append(key.rsplit('_', 1)[1] + ":"+str(self.subcenter_port))
                                    best_road_sor_list.append(key.rsplit('_', 1)[1])
                                    flag = True
                        if not flag:
                            branch_list.extend(self.branch_center_list)
                        else:
                            logger.debug(' set host: %s best road is %s' % (host, best_road_sor_list))
                            subcenter_factory.set('central_best_road_' + host, best_road_sor_list)
                            logger.debug('best road is %s' % subcenter_factory.get('central_best_road_' + host))
                            subcenter_factory.expire('central_best_road_' + host, EXPIRETIME_BEST)
                            #branch_list.extend(best_road_sor_list)
                    else:
                        branch_list.extend(self.branch_center_list)

                map_t[host] = branch_list
            logger.info('-------best_road------map_t-------------------%s'%(map_t))
            return map_t
        except Exception:
            logger.debug('get_best_road_v error:%s, host:%s' % (traceback.format_exc(), host))

    def get_best_road_hello(self):
        """
        according host, get best road, from redis,  if not have, send all branch_center_list
        :param host:  the host of edge dev
        :param branch_center_list:  all branch center host:21109
        :return: [branch_center_ip1, branch_center_ip2,xxx, xxx]
        """
        branch_list = []
        map_t = {}

        best_road = {}
        try:
            for failed_dev in self.failed_dev_list:
                host = failed_dev.get('host')
                branch_center = subcenter_factory.get('central_best_road' + host)
                # branch_center is exits

                if branch_center:
                    if branch_center + ":"+str(self.subcenter_port) in self.branch_center_list:
                        best_road.setdefault(branch_center + ":"+str(self.subcenter_port),[]).append(host)
                    else:
                        subcenter_factory.delete("central_best_road_" + host)
                        subcenter_factory.delete("central_link_" + host + "_" + branch_center)
                        for sub_dev in self.branch_center_list:
                            best_road.setdefault(sub_dev, []).append(host)
                else:
                    keys = subcenter_factory.keys("central_link_" + host + "*")
                    # have keys
                    k_v = {}
                    if keys and len(keys) > 0:
                        for key in keys:
                            k_v[key] = int(subcenter_factory.get(key))
                        # 取时间最小的key

                        #key = heapq.nsmallest(1, k_v.items(), key=lambda x: x[1])[0][0]
                        sub_min_list = sorted(k_v, key=lambda x: k_v[x])
                        flag = False
                        if len(sub_min_list) >= FIRST_HOST:
                            send_dev = sub_min_list[:FIRST_HOST]
                        else:
                            send_dev = sub_min_list

                        for key in send_dev:
                            if key.rsplit('_', 1)[1] + ":"+str(self.subcenter_port) in self.branch_center_list:
                                best_road.setdefault(key.rsplit('_', 1)[1] + ":"+str(self.subcenter_port), []).append(host)
                                subcenter_factory.set('central_best_road_' + host, key.rsplit('_', 1)[1])
                                subcenter_factory.expire('central_best_road_' + host, EXPIRETIME_BEST)
                                flag = True
                        if not flag:
                            for sub_dev in self.branch_center_list:
                                best_road.setdefault(sub_dev, []).append(host)
                    else:
                        for sub_dev in self.branch_center_list:
                            best_road.setdefault(sub_dev, []).append(host)

                return best_road
        except Exception:
            logger.debug('get_best_road_v error:%s, host:%s' % (traceback.format_exc(), host))

    def insert_mongo(self):
        """
        :param list_uid: [ObjectId('1234234'), ObjectId('123423434234')]
        :param send_result:[{'host': xxxx, 'code': 200}]
        :return:
        """
        try:
            result = {}
            for dev, subcent_list in list(self.relation_sub_failed_dev.items()):
                for subcent in subcent_list:
                    if subcent not in result:
                        result[subcent] = [dev]
                    else:
                        result[subcent].append(dev)
            for sub_center_host,failed_list in list(result.items()):
                for edge_host in failed_list:
                    # edge_host_res[edge_host.replace('.','#')] = 0
                    self.db[self.subcenter_result_mq].insert({'t_id': self.sub_task_id,
                                                           'edge_result': 0,
                                                           'subcenter_host': sub_center_host.split(":")[0],
                                                           'edge_host': edge_host,
                                                           'created_time': datetime.datetime.now()})
            for result_t in self.send_result():
                logger.debug('send result ---  --- %s'%(result_t))
                sub_center_host_r = result_t.get('host')
                cent_link_sub = result_t.get('code')
                self.db[self.subcenter_result_mq].update({'t_id': self.sub_task_id,'subcenter_host': sub_center_host_r}
                                                         ,{'$set':{'cent_link_sub': cent_link_sub}},multi=True)
        except Exception:
            logger.debug(e.message)
            logger.debug('subcenter_base insert_mongo erro')

    @classmethod
    def update_subcenter_result(cls, subcenter_result_mq, db, param, sub_center_host, edge_host, ack_content, branch_code,
                                date_time_now):
        """
	according retry_device_branch, update device info
        :param retry_branch_id:major key
	:param branch_code: device refresh result status code
	:return:{ 'True'or 'False'}

        """
        try:

            # date_time_now = datetime.datetime.now()
            result = db[subcenter_result_mq].update(
                {"t_id": param, "edge_host": edge_host, "subcenter_host": sub_center_host},
                {"$set": {"edge_result": branch_code, 'edge_return_time': date_time_now, 'ack_content': ack_content}})
        except Exception:
            logger.debug("subcenter_update_result error:%s" % traceback.format_exc())

            return False

        return True

    @classmethod
    def subcenter_udate_redis(cls, subcenter_result_mq, param, db, sub_center_host, edge_host, edge_code,
                              edge_return_time):
        """
        according uid, sub_center_host, edge_code , update retry_device_branch, add consume_time
        :param sub_center_host: the sub_center_host of retry_device_branch
        :param edge_host: the host of retry_device_branch
        :param edge_code: the edge_code of retry_device_branch
        :param edge_return_time: the return time of subcenter of edge_return_time
        """
        try:
            result = db[subcenter_result_mq].find_one({"t_id": param,
                                                    "subcenter_host": sub_center_host, 'edge_host': edge_host})
            if result:
                create_time = result.get('created_time')
                if not create_time:
                    logger.debug("subcenter_update_redis cann't get create_time, sub_center_host:%s, edge_host:%s"
                                 % (sub_center_host, edge_host))
                    return
                else:
                    if edge_code != 200:
                        logger.debug(
                            "subcenter_udpate_redis central link error uid:%s, sub_center_host:%s, edge_host:%s" %
                            (param, sub_center_host, edge_host))
                        # the link from subcenter to edge is error
                        #subcenter_factory.delete("central_best_road_" + edge_host)
                        subcenter_factory.delete("central_link_" + edge_host + "_" + sub_center_host)
                    else:
                        consume_time = (edge_return_time - create_time).total_seconds()
                        subcenter_factory.set("central_link_" + edge_host + "_" + sub_center_host, consume_time)
                        subcenter_factory.expire("central_link_" + edge_host + "_" + sub_center_host, EXPIRETIME)
        except Exception:
            logger.debug("subcenter_update_redis error:%s, uid:%s, sub_center_host:%s, edge_host:%s" %
                         (traceback.format_exc(), param, sub_center_host, edge_host))

class Subcenter_Refresh_Url(SubBase):
    def __init__(self, dict_sub, **kw):
        SubBase.__init__(self, dict_sub, **kw)
        self.tasks = dict_sub.get('tasks')
        self.request_id = str(ObjectId())#dict_sub.get('tasks')[0].get('r_id')
        self.fail_dev_map = self.get_dev_name()
        #self.body = self.generate_body()
        self.body = None
        self.task_id = 0
        #self.sub_task_id = self.init_mongo()
        #self.header = {"Content-type":"text/xml"}
        logger.debug('------------dict_sub_tasks-----%s' % (dict_sub.get('tasks')))
        logger.debug('------------dict_sub_tasks-----%s'%(dict_sub.get('tasks')))
        logger.debug('------------dict_sub_tasks--[0]---type%s' % (type(dict_sub.get('tasks')[0])))
        logger.debug('------------dict_sub_tasks--[0]---value%s' % (dict_sub.get('tasks')[0]))
        # self.command = self.generate_command()
    def get_dev_name(self):
        fail_dev_map_name ={}
        for dev in self.failed_dev_list:
            fail_dev_map_name.setdefault(dev.get('host','127.0.0.1'),{'name':dev.get('name','UNKNOW'),'type':dev.get('type','UNKNOW'),'firstLayer':dev.get('firstLayer',False),'status':dev.get('status','UNKNOW')})
        return fail_dev_map_name

    def get_callback_params(self):
        callback_params_list = []
        request_id = self.tasks[0].get("r_id")
        callback_params_list.append(self.task_id)
        callback_params_list.append(request_id)

        for task in self.tasks:
            callback_params_list.append(task.get("id"))

        return callback_params_list
    def insert_mongo(self):
        """
        :param list_uid: [ObjectId('1234234'), ObjectId('123423434234')]
        :param send_result:[{'host': xxxx, 'code': 200}]
        :return:
        """
        insert_time = datetime.datetime.now()
        try:
            res = {}
            # worker_branch_list = list(set(self.branch_center_list).intersection(set(self.relation_sub_failed_dev.keys())))
            for k, v in list(self.relation_sub_failed_dev.items()):
                res[k.replace('.', '#')] = [sub_center.split(':')[0] for sub_center in v]

            sub_task_id = self.db[self.subcenter_task_mq].insert(
                {'r_id':self.request_id,'ralation_faildev_subcenter': res,'command': self.command,
                 'created_time':insert_time})
            self.task_id = str(sub_task_id)
            #'_id':ObjectId(self.request_id),
            #'fail_edge_list':[dev.get("host") for dev in self.failed_dev_list],'fail_dev_num':len(res),
            #return str(sub_task_id)
            # s_id = self.db[self.subcenter_task].insert({"ralation_dev_subcenter":res,"command":self.command})

            rety_list = []
            for task in self.tasks:
                rety_list.append(ObjectId(task.get('id')))
            logger.info('-----------rety_list ----%s'%(rety_list))
            db_db['url'].update_many({"_id": {"$in":rety_list}},{"$set": {'retry_branch_id': ObjectId(self.request_id)}})

        except Exception:
            logger.debug(e.message)
            logger.debug("link_detection_refresh error:%s" % traceback.format_exc())

        self.body = self.generate_body()#20180126
        try:
            result = {}
            for dev, subcent_list in list(self.relation_sub_failed_dev.items()):
                for subcent in subcent_list:
                    if subcent not in result:
                        result[subcent] = [dev]
                    else:
                        result[subcent].append(dev)

            for sub_center_host_te,failed_list in list(result.items()):
                sub_center_host = sub_center_host_te.split(":")[0]
                # edge_host_res = {}
                for edge_host in failed_list:
                    # edge_host_res[edge_host.replace('.','#')] = 0
                    #for uid in self.get_callback_params()[1:]:
                    for uid in self.get_callback_params()[2:]:
                        if self.fail_dev_map.get(edge_host, None):
                            name = self.fail_dev_map.get(edge_host).get('name', 'UNKONW')
                            dev_type = self.fail_dev_map.get(edge_host).get('type', 'UNKONW')
                            dev_status = self.fail_dev_map.get(edge_host).get('status', 'UNKONW')
                            firstLayer = self.fail_dev_map.get(edge_host).get('firstLayer', False)
                        else:
                            name, dev_type, dev_status, firstLayer = 'UNKONW', 'UNKONW', 'UNKONW', False
                        self.db[self.subcenter_result_mq].insert({'r_id': self.request_id,
                                                                  'uid': uid,
                                                                  'name': name,
                                                                  'type': dev_type,
                                                                  'status': dev_status,
                                                                  'fail_dev_num': len(self.failed_dev_list),
                                                                  'firstLayer': firstLayer,
                                                                  'unique_id': uid + "_" + sub_center_host + "_" + edge_host,
                                                                  'edge_result': 0,
                                                                  #'cent_link_sub': result_t.get('code'),
                                                                  'subcenter_host': sub_center_host,
                                                                  'edge_host': edge_host,
                                                                  'created_time': insert_time})
                        logger.debug("----------id---%s--------------" % (uid))

            for result_t in self.send_result():
                logger.debug('send result ---  --- %s'%(result_t))
                sub_center_host_r = result_t.get('host')
                cent_link_sub = result_t.get('code')
                self.db[self.subcenter_result_mq].update({'r_id': self.request_id,'subcenter_host': sub_center_host_r}
                                                         ,{'$set':{'cent_link_sub': cent_link_sub}},multi=True)

            #
            # for result_t in self.send_result():
            #     logger.debug('send result ---  --- %s'%(result_t))
            #     sub_center_host = result_t.get('host')
            #     sub_center_host_port = sub_center_host + ':'+str(self.subcenter_port)
            #     failed_list = [dev['target_url'].split(":")[1].strip("//") for dev in
            #                    self.body[sub_center_host_port].get('edge_list')]
            #     # edge_host_res = {}
            #     for edge_host in failed_list:
            #         # edge_host_res[edge_host.replace('.','#')] = 0
            #         for uid in self.get_callback_params()[1:]:
            #             if self.fail_dev_map.get(edge_host,None):
            #                 name = self.fail_dev_map.get(edge_host).get('name','UNKONW')
            #                 dev_type = self.fail_dev_map.get(edge_host).get('type','UNKONW')
            #                 dev_status = self.fail_dev_map.get(edge_host).get('status','UNKONW')
            #                 firstLayer = self.fail_dev_map.get(edge_host).get('firstLayer',False)
            #             else:
            #                 name,dev_type,dev_status,firstLayer = 'UNKONW','UNKONW','UNKONW',False
            #             self.db[self.subcenter_result_mq].insert({'r_id': self.request_id,
            #                                                     'uid':uid,
            #                                                       'name':name,
            #                                                       'type':dev_type,
            #                                                       'status':dev_status,
            #                                                       'fail_dev_num':len(self.failed_dev_list),
            #                                                       'firstLayer':firstLayer,
            #                                                       'unique_id':uid+"_"+sub_center_host+"_"+edge_host,
            #                                                    'edge_result': 0,
            #                                                    'cent_link_sub': result_t.get('code'),
            #                                                    'subcenter_host': sub_center_host,
            #                                                    'edge_host': edge_host,
            #                                                    'created_time': insert_time})
            #             logger.debug("----------id---%s--------------"%(uid))
        except Exception:
            logger.debug(e.message)
            logger.debug('subcenter_base insert_mongo erro')


    def generate_command(self):
        """
        according urls, generate xml
        :param urls:
        :return:
        """
        try:

            sid,command = getUrlCommand(self.tasks)
            #self.request_id = sid
            return command
        except Exception:
            logger.debug('subcenter_refresh_url generate_command error:%s' % traceback.format_exc())
            return None
    def generate_body(self):
        """
        generate the body
        :param failed_dev_list: [{'host': 'xxxxx', 'name': 'xxxx'}]
        :param edge_port:
        :param command:
        :return:
        """
        try:
            result = {}
            for dev, subcent_list in list(self.relation_sub_failed_dev.items()):
                for subcent in subcent_list:
                    if subcent not in result:
                        result[subcent] = [dev]
                    else:
                        result[subcent].append(dev)

            send_body_all = {}
            for subcenter_host_port in result:

                send_body = {}
                #send_body['edge_list'] = []
                #data = {}
                # data['target_url'] = ["http://"+dev+":"+str(self.edge_port)+"/" for dev in self.relation_sub_failed_dev[subcenter_host_port]]
                for dev in result[subcenter_host_port]:
                    #data['target_url'] = "http://" + dev + ":" + str(self.edge_port) + "/"
                    #send_body.setdefault('edge_list',[]).append(data)
                    send_body.setdefault('edge_list', []).append({'target_url':"http://" + dev + ":" + str(self.edge_port) + "/"})
                send_body['command'] = self.command
                send_body['is_compressed'] = self.is_compressed
                send_body['callback'] = self.return_path#callback_params
                send_body['callback_params'] = self.get_callback_params()
                send_body['sender_header'] = {"Content-type":"text/xml"}# self.header
                send_body_t = deepcopy(send_body)
                send_body_all[subcenter_host_port] = send_body_t
                # self.body = json.dumps(send_body)
                logger.info('------------command-----%s' % (send_body['command']))
            #logger.info('------------send_body_all-----%s'%(send_body_all))
            return send_body_all
        except Exception:
            logger.debug("generate_body error:%s" % traceback.format_exc())
            return {}
class Subcenter_Refresh_Dir(Subcenter_Refresh_Url):
    def __init__(self, dict_sub, **kw):
        #SubBase.__init__(self, dict_sub, **kw)
        Subcenter_Refresh_Url.__init__(self, dict_sub, **kw)
        self.tasks = dict_sub.get('tasks')
        #self.request_id = dict_sub.get('tasks')[0].get('r_id')
        # self.command = self.generate_command()

    def generate_command(self):
        """
        according urls, generate xml
        :param urls:
        :return:
        """
        try:

            sid, command = getDirCommand(self.tasks)
            #self.request_id = sid
            return command
        except Exception:
            logger.debug('subcenter_refresh_url generate_command error:%s' % traceback.format_exc())
            return None


class Subcenter_cert(SubBase):
    """
    证书
    """

    def __init__(self, dict_sub, **kw):
        SubBase.__init__(self, dict_sub, **kw)
        self.tasks = dict_sub.get('tasks')
        self.orgin_ids = self.generate_orgin_ids()
        self.sub_task_id = self.init_mongo()
        self.command = self.generate_command()
        self.body = self.generate_body()
        # self.return_path = dict_sub.get('return_path', 'http://rep.chinacache.com/receiveSubCenterResult_new')

    def generate_command(self):
        """
        according urls, generate xml
        :param urls:
        :return:
        """
        try:
            if self.edge_path == "checkcertisexits":
                return get_cert_query_command(self.tasks)
            elif self.edge_path == "transfer_cert":
                return get_transfer_cert_command(self.tasks)
            else:
                return get_command(self.tasks)
        except Exception:
            logger.debug('subcenter_refresh generate_command error:%s' % traceback.format_exc())
            return None
        #try:
        #    return get_command(self.tasks)
        #except Exception, e:
        #    logger.debug('subcenter_refresh generate_command error:%s' % traceback.format_exc())
        #    return None


class Subcenter_preload(SubBase):

    def __init__(self, dict_sub, **kw):
        super(Subcenter_preload, self).__init__(dict_sub, **kw)
        self.dev = dict_sub.get('failed_dev_list')
        self.action = 'sub_preload'

    def generate_command(self):
        try:
            logger.debug("Subcenter_preload[generate_command] self.tasks: %s" % (self.tasks, ))
            return get_command_preload(self.tasks, self.action, self.dev, check_conn=True)
        except Exception:
            logger.debug('Subcenter_preload[generate_command] error: %s' % traceback.format_exc())
            return None


def getUrlCommand(urls, encoding='utf-8'):
    """
    按接口格式，格式化url
    curl -sv refreshd  -d  "<?xml version=\"1.0\" encoding=\"UTF-8\"?><method name=\"url_purge\" purge_type=\"1\"
    sessionid=\"5\"><url_list><url id=\"1\">www.cjc.com</url></url_list></method>" -x  127.0.0.1:21108

     curl -sv refreshd  -d "<?xml version=\"1.0\" encoding=\"UTF-8\"?><method name=\"dir_purge\" purge_type=\"1\"
           sessionid=\"1\"><dir>dl.appstreaming.autodesk.com</dir></method>" -x  127.0.0.1:21108
    :param urls:
    :param encoding:
    :return:
    """
    # judge whether physical del if True physical del
    physical_del_channel = str(0)
    if urls[0].get('url_encoding') and (len(urls) == 1):
        encoding = urls[0].get('url_encoding')
    if urls[0].get('physical_del_channel'):
        physical_del_channel = str(1)
    sid = urls[0].get('r_id',uuid.uuid1().hex)
    if physical_del_channel == '1':
        content = parseString('<method name="url_expire" sessionid="%s" purge_type="%s"><recursion>0</recursion></method>'
                              % (sid, physical_del_channel))
        if urls[0].get('action') == 'purge':
            content = parseString('<method name="url_purge" sessionid="%s" purge_type="%s"><recursion>0</recursion></method>'
                                  % (sid, physical_del_channel))
    else:
        content = parseString('<method name="url_expire" sessionid="%s"><recursion>0</recursion></method>' % sid)
        if urls[0].get('action') == 'purge':
            content = parseString('<method name="url_purge" sessionid="%s"><recursion>0</recursion></method>' % sid)
    url_list = parseString('<url_list></url_list>')
    tmp = {}
    logger.debug('urls information')
    logger.debug(urls)
    for idx, url in enumerate(urls):
        #if url.get("url") in tmp:
        #    continue
        qurl = url.get("url").lower() if url.get('ignore_case', False) else url.get("url")
        uelement = content.createElement('url')
        #uelement.setAttribute('id', str(idx))
        uelement.setAttribute('id', url.get("id", str(idx))) #store url.id  in id
        logger.debug("send url.id:%s" % url.get("id"))
        # rubin test start
        # qurl = qurl.decode('utf8')
        # qurl = qurl.encode('gb2312')
        # rubin test end
        uelement.appendChild(content.createTextNode(qurl))
        url_list.documentElement.appendChild(uelement)
        tmp[url.get("url")] = ''
    content.documentElement.appendChild(url_list.documentElement)
    return sid,content.toxml(encoding)
    # rubin test start
    # return content.toxml('gb2312')
    # rubin test end
