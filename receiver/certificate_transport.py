# -*- coding:utf-8 -*-
import traceback, random, zipfile, zlib, socket,urllib.request,urllib.error,urllib.parse,hashlib
import datetime, time
import shutil, os
import base64
from flask import Blueprint, request, make_response, jsonify, Response
import simplejson as json
from core.generate_id import ObjectId
from util import log_utils
from util import rsa_tools, cert_tools, tools
from core import redisfactory, authentication, database, queue
from core import cert_trans_worker,cert_query_worker,transfer_cert_worker
from core.config import config
from util.link_portal_cms import check_cert_cms
from util.link_portal_cms import cert_portal_delete,cert_cms_delete

RECEV_HOST = socket.gethostname()
logger = log_utils.get_cert_Logger()
s1_db = database.s1_db_session()
db = database.db_session()
CERT_CACHE = redisfactory.getDB(10)
HPCC_SAVE_DIR = config.get('cert_trans', 'cache_dir')

certificate_transport = Blueprint('certificate_transport', __name__, )


@certificate_transport.route("/internal/cert/trans", methods=['GET', 'POST'])
def cert_trans():
    '''
    接收portal下发请求
    '''
    try:
        cert_data = request.data
        logger.debug('receiver cert data:{}'.format(cert_data))
        data = json.loads(cert_data)
        task = make_task(data)
        queue.put_json2('cert_task', [task])
        return jsonify({'code': 200, 'task_id': task['_id'], 'cert_id': task['c_id'], 'cert_cache_name': task['s_name']})
    except CertInputError as ex:
        return jsonify({"code": 504, "msg": ex.__str__()})
    except CertExpireError as ex:
        return jsonify({"code": 505, "msg": ex.__str__()})
    except CertRevokeError as ex:
        return jsonify({"code": 506, "msg": ex.__str__()})
    except CertPrikeyError as ex:
        return jsonify({"code": 507, "msg": ex.__str__()})
    except CertPathError as ex:
        return jsonify({"code": 508, "msg": ex.__str__()})
    except CertDecryptError as ex:
        return jsonify({"code": 509, "msg": ex.__str__()})
    except CertPrikeyTypeError as ex:
        return jsonify({"code": 510, "msg": ex.__str__()})
    except CertSaveNameError as ex:
        return jsonify({"code": 511, "msg": ex.__str__()})
    except CertNoRoot as ex:
        return jsonify({"code": 512, "msg": ex.__str__()})
    except CertNoMiddle as ex:
        return jsonify({"code": 513, "msg": ex.__str__()})
    except CertAliasError as ex:
        return jsonify({"code": 514, "msg": ex.__str__()})
    except Exception:
        logger.debug('/internal/cert/trans error')
        logger.debug(traceback.format_exc())
        logger.debug(e.__str__())
        return jsonify({"code": 500, "msg": "The schema of request is error."})


@certificate_transport.route("/internal/cert/query", methods=['GET', 'POST'])
def cert_query_trans():
    '''
    证书查询任务下发
    '''
    try:
        s1_db = database.s1_db_session()
        data = json.loads(request.data)
        logger.debug('cert_query_trans post data %s' %(data))
        data_username=data.get('username','chinacache')
        data_info=data['info']
        query_ip= data_info.get('ip','')
        query_path=data_info.get('path','')
        query_config_path=data_info.get('config_path','')
        query_cert_type=data_info.get('cert_type','')
        query_type=data_info.get('query_type','')
        query_cert_name=data_info.get('cert_name','')
        query_time=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if not query_ip:
            raise QueryipError('not input ip')
        if not query_path:
            raise QuerypathError('not input path')
        if not query_config_path:
            raise QueryconpathError('not input config path')
        if not query_cert_name:
            raise QuerycertnameError('not input cert name')
        if not query_cert_type:
            raise QuerycerttypeError('not input cert type')
        devices_list=[]
        for q_ip in query_ip:
            q_ip_type=tools.judge_dev_ForH_byip(q_ip)
            if q_ip_type != 'HPCC':
                devices_list.append(q_ip)
        if devices_list:
            raise QuerydevicesError('%s    isn`t HPCC devices '%'  '.join(devices_list))
        q_id=s1_db.cert_query_info.insert({'cert_type':query_cert_type,'cert_name':query_cert_name,'path':query_path,'config_path':query_config_path,'created_time':datetime.datetime.now(),'username':data_username})
        task={}
        task['_id']= str(ObjectId())
        task['query_dev_ip']= tools.sortip(query_ip)
        logger.debug('cert_query_trans query_dev_ip %s'%(task['query_dev_ip']))
        task['dev_ip_md5']=tools.md5(json.dumps(task['query_dev_ip']))
        logger.debug('cert_query_trans dev_ip_md5 %s'%(task['dev_ip_md5']))
        task['q_id']=str(q_id)
        task['username']=data_username
        task['query_path']=query_path
        task['query_cert_name']=query_cert_name
        task['query_cert_type']=query_cert_type
        task['query_config_path']=query_config_path
        task['created_time']=query_time
        queue.put_json2('cert_query_task', [task])
        return jsonify({'code': 200, 'task_id': task['_id'],'cert_query_id':task['q_id']})

    except QueryipError as ex:
        return jsonify({"code": 520, "msg": ex.__str__()})
    except QuerypathError as ex:
        return jsonify({"code": 521, "msg": ex.__str__()})
    except QueryconpathError as ex:
        return jsonify({"code": 522, "msg": ex.__str__()})
    except QuerycertnameError as ex:
        return jsonify({"code": 523, "msg": ex.__str__()})
    except QuerycerttypeError as ex:
        return jsonify({"code": 524, "msg": ex.__str__()})
    except QuerydevicesError as ex:
        return jsonify({"code": 525, "msg": ex.__str__()})
    except Exception:
        logger.debug('/internal/cert/query error')
        logger.debug(traceback.format_exc())
        logger.debug(e.__str__())
        return jsonify({"code": 500, "msg": "The schema of request is error."})

@certificate_transport.route("/internal/cert/transfer_expired_cert", methods=['GET', 'POST'])
def transfer_expired_cert():
    '''
    转移过期证书
    '''
    try:
        s1_db = database.s1_db_session()
        data = json.loads(request.data)
        s_name = data.get('save_name', '')#证书名称
        username=data.get('username','')
        transfer_dev=data.get('transfer_dev','')#转移证书的cache设备
        dev_type=data.get('dev_type','')#转移证书的类型
        c_o_path = config.get('app', 'o_path')
        c_d_path = config.get('app', 'd_path')

        o_path=data.get('o_path',c_o_path)
        d_path=data.get('d_path',c_d_path)
        # o_path = data.get('o_path', '')
        # d_path = data.get('d_path', '')
        transfer_time=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        logger.debug("s_name is %s"%s_name)
        logger.debug("username is %s"%username)
        logger.debug("o_path is %s"%o_path)
        logger.debug("d_path is %s"%d_path)
        logger.debug("dev_type is %s"%dev_type)
        if len(transfer_dev)<=1 and transfer_dev[0]=='' and dev_type!='all_dev':
            raise TransferdevError('not input ip')
        array_s_name = s_name.split(',')
        db.transfer_certs_detail.ensure_index('save_name', unique=True)

        cret_id_list = []
        cert_not_find = []
        for save_name in array_s_name:
            info_cert = s1_db.cert_detail.find_one({'save_name': save_name})
            if not info_cert:
                cert_not_find.append(save_name)
            else:
                cret_id_list.append(str(info_cert['_id']))
        if cert_not_find:
            return jsonify({"code": 504, "msg": 'Certificate does not exist, please check the name of the certificate %s'%(cert_not_find)})
        status,message = check_cert_cms(cret_id_list)
        if status == False:
            return jsonify({"code": 504, "msg": message})

        try:
            status = cert_cms_delete(cret_id_list)
            if status:
                portal_status = cert_portal_delete(cret_id_list)
                if portal_status != True:
                    return jsonify({'code': 504, 'msg': 'portal delete error'})
            else:
                return jsonify({'code': 504, 'msg': 'cms delete error'})
        except Exception:
            logger.error('callback error %s' % (traceback.format_exc()))
            return jsonify({'code': 504, 'msg': 'delete error%s' % (traceback.format_exc())})


        for save_name in array_s_name:
            info = s1_db.cert_detail.find_one({'save_name':save_name})
            #db.transfer_certs_detail.ensure_index('save_name', unique=True)
            datestr = int(time.mktime(datetime.datetime.now().timetuple()))
            change_name = "{}{}{}{}".format("trans_", username, info.get('cert_alias'), datestr)
            t_id=s1_db.transfer_certs_detail.insert({'save_name':save_name,'o_path':o_path,'d_path':d_path,'created_time':datetime.datetime.now(),'username':username})
            #db.transfer_certs_detail.ensure_index('save_name', unique=True)
            s1_db.cert_detail.update({'save_name':save_name},{"$set" : {"t_id" : t_id,"cert_alias":change_name}});
            #if not info:
            #    raise CertNotFoundError()
        task={}
        task['_id']= str(ObjectId())
        if dev_type=='all_dev'or transfer_dev=='all_hpcc':
            task['send_dev']='all_dev'
            task['send_dev_md5']=tools.md5(task['send_dev'])
        else:
            task['send_dev']= tools.sortip(transfer_dev)
            logger.debug(task['send_dev'])
            devices_list=[]
            for q_ip in task['send_dev']:
                q_ip_type=tools.judge_dev_ForH_byip(q_ip)
                if q_ip_type != 'HPCC':
                    devices_list.append(q_ip)
            if devices_list:
                raise QuerydevicesError('%s    isn`t HPCC devices '%'  '.join(devices_list))
            task['send_dev_md5']=tools.md5(json.dumps(task['send_dev']))
            logger.debug(task['send_dev_md5'])
        task['t_id']=str(t_id)
        task['username']=username
        task['o_path']=o_path
        task['d_path']=d_path
        task['save_name']=s_name
        task['created_time']=transfer_time
        queue.put_json2('transfer_cert_task', [task])
        #res ={'code': 200, 'cert_id': str(info.get('_id'))}
        res ={'code': 200}
        return jsonify(res)
    except CertNotFoundError as ex:
        return jsonify({"code": 504, "msg": "The certificate does not exist"})
    except TransferdevError as ex:
        return jsonify({"code": 524, "msg": ex.__str__()})
    except QuerydevicesError as ex:
        return jsonify({"code": 525, "msg": ex.__str__()})
    except Exception:
        logger.debug('/transfer_expired_cert error')
        logger.debug(traceback.format_exc())
        logger.debug(e.__str__())
        return jsonify({"code": 500, "msg": "The schema of request is error."})

@certificate_transport.route("/internal/cert/portal_transfer", methods=['GET', 'POST'])
def transfer_portal_expired_cert():
    '''
    portal转移过期证书
    '''
    try:
        s1_db = database.s1_db_session()
        data = json.loads(request.data)
        cer_id_str = data.get('cert_ids', '')
        #s_name = data.get('save_name', '')#证书名称
        username=data.get('username','portal')
        transfer_dev=data.get('transfer_dev',[''])#转移证书的cache设备
        dev_type=data.get('dev_type','all_dev')#转移证书的类型
        c_o_path = config.get('app', 'o_path')
        c_d_path = config.get('app', 'd_path')

        o_path=data.get('o_path',c_o_path)
        d_path=data.get('d_path',c_d_path)
        # o_path = data.get('o_path', '')
        # d_path = data.get('d_path', '')
        transfer_time=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        #logger.debug("s_name is %s"%s_name)
        logger.debug("username is %s"%username)
        logger.debug("o_path is %s"%o_path)
        logger.debug("d_path is %s"%d_path)
        logger.debug("dev_type is %s"%dev_type)
        if len(transfer_dev)<=1 and transfer_dev[0]=='' and dev_type!='all_dev':
            raise TransferdevError('not input ip')

        #array_s_name = s_name.split(',')
        array_s_name = []
        cer_id_list = cer_id_str.split(',')
        if not cer_id_list:
            return jsonify({"code": 504, "msg": 'please push cert id'})
        for cert_id in cer_id_list:
            cert_id_objectid = ObjectId(cert_id)
            cert_detail_one = s1_db.cert_detail.find_one({'_id':cert_id_objectid})
            if not cert_detail_one:
                return jsonify({"code": 504, "msg": 'this id not exist'})
            array_s_name.append(cert_detail_one['save_name'])
        if not array_s_name:
            return jsonify({"code": 504, "msg": 'please push cert id'})

        db.transfer_certs_detail.ensure_index('save_name', unique=True)

        #cret_id_list = []
        # cert_not_find = []
        # for save_name in array_s_name:
        #     info_cert = s1_db.cert_detail.find_one({'save_name': save_name})
        #     if not info_cert:
        #         cert_not_find.append(save_name)
        #     else:
        #         cret_id_list.append(str(info_cert['_id']))
        # if cert_not_find:
        #     return jsonify({"code": 504, "msg": 'Certificate does not exist, please check the name of the certificate %s'%(cert_not_find)})
        #
        #status,message = check_cert_cms(cret_id_list)

        status, message = check_cert_cms(cer_id_list)
        if status == False:
            return jsonify({"code": 504, "msg": message})


        task={}
        task['_id']= str(ObjectId())
        if dev_type=='all_dev'or transfer_dev=='all_hpcc':
            task['send_dev']='all_dev'
            task['send_dev_md5']=tools.md5(task['send_dev'])
        else:
            task['send_dev']= tools.sortip(transfer_dev)
            logger.debug(task['send_dev'])
            devices_list=[]
            for q_ip in task['send_dev']:
                q_ip_type=tools.judge_dev_ForH_byip(q_ip)
                if q_ip_type != 'HPCC':
                    devices_list.append(q_ip)
            if devices_list:
                raise QuerydevicesError('%s    isn`t HPCC devices '%'  '.join(devices_list))
            task['send_dev_md5']=tools.md5(json.dumps(task['send_dev']))
            logger.debug(task['send_dev_md5'])

        try:
            status = cert_cms_delete(cer_id_list)
            if status:
                    portal_status = cert_portal_delete(cer_id_list)
                    if portal_status != True:
                        return jsonify({'code': 504, 'msg': 'portal delete error'})
            else:
                return jsonify({'code': 504, 'msg': 'cms delete error'})
        except Exception:
            logger.error('callback error %s'%(traceback.format_exc()))
            return jsonify({'code': 504, 'msg': 'delete error%s'%(traceback.format_exc())})

        for save_name in array_s_name:
            info = s1_db.cert_detail.find_one({'save_name':save_name})

            datestr = int(time.mktime(datetime.datetime.now().timetuple()))
            change_name = "{}{}{}{}".format("trans_", username, info.get('cert_alias'), datestr)
            #db.transfer_certs_detail.ensure_index('save_name', unique=True)
            t_id=s1_db.transfer_certs_detail.insert({'save_name':save_name,'o_path':o_path,'d_path':d_path,'created_time':datetime.datetime.now(),'username':username})
            #db.transfer_certs_detail.ensure_index('save_name', unique=True)
            s1_db.cert_detail.update({'save_name':save_name},{"$set" : {"t_id" : t_id,"cert_alias":change_name}});
            #if not info:
            #    raise CertNotFoundError()

        task['t_id']=str(t_id)
        task['username']=username
        task['o_path']=o_path
        task['d_path']=d_path
        task['save_name']=','.join(array_s_name)#s_name
        task['created_time']=transfer_time
        logger.debug('transfer cert task {}'.format([task]))
        queue.put_json2('transfer_cert_task', [task])
        #res ={'code': 200, 'cert_id': str(info.get('_id'))}
        res ={'code': 200,'msg':'ok'}
        return jsonify(res)
    except CertNotFoundError as ex:
        return jsonify({"code": 504, "msg": "The certificate does not exist"})
    except TransferdevError as ex:
        return jsonify({"code": 524, "msg": ex.__str__()})
    except QuerydevicesError as ex:
        return jsonify({"code": 525, "msg": ex.__str__()})
    except Exception:
        logger.debug('/transfer_expired_cert error')
        logger.debug(traceback.format_exc())
        logger.debug(e.__str__())
        return jsonify({"code": 500, "msg": "The schema of request is error."})


@certificate_transport.route("/internal/cert/search", methods=['GET', 'POST'])
def cert_trans_search():
    '''
    portal search cert
    '''
    try:
        data = json.loads(request.data)
        cert_id = data.get('cert_id', '')
        if not cert_id:
            raise
        info = s1_db.cert_detail.find_one({'_id':ObjectId(cert_id)})
        if not info:
            raise CertNotFoundError()
        res ={'code': 200,'save_name':info.get('save_name','') ,'DNS_name': info.get('DNS'),'validity': cert_tools.make_validity_to_China(info.get('validity')), 'subject': info.get('subject'), 'issuer': info.get('issuer'),'pubkey':info.get('pubkey')}
        return jsonify(res)
    except CertNotFoundError as ex:
        return jsonify({"code": 504, "msg": "The certificate does not exist"})
    except Exception:
        logger.debug('/internal/cert/trans error')
        logger.debug(traceback.format_exc())
        logger.debug(e.__str__())
        return jsonify({"code": 500, "msg": "The schema of request is error."})


@certificate_transport.route("/internal/cert/seed", methods=['GET', 'POST'])
def cert_search_seed():
    '''
    查询种子
    '''
    try:
        data = json.loads(request.data)
        username = data.get('username', '')
        if not username:
            raise
        seed = cert_trans_worker.get_custom_seed(username)
        return jsonify({'seed': seed})
    except Exception:
        logger.debug('/internal/cert/trans error')
        logger.debug(traceback.format_exc())
        logger.debug(e.__str__())
        return jsonify({"code": 500, "msg": "The schema of request is error."})


@certificate_transport.route("/internal/cert/sync/portal", methods=['GET', 'POST'])
def cert_sync_portal():
    '''
    portal 同步
    '''
    try:
        data = json.loads(request.data)
        sign = data['sign']
        rsa_tools.verify_sign(sign, rsa_tools.portal_pub_key, 'chinacache')
        #all_certs = s1_db.cert_detail.find()
        all_certs = s1_db.cert_detail.find({'t_id':{"$exists":False}})
        res = []

        for cert in all_certs:
            r = {}
            r['cert_id'] = str(cert['_id'])
            r['username'] = cert['username']
            r['cert_name'] = cert['cert_alias']
            r['expire'] = cert_tools.make_validity_to_China(cert['validity'])['end_time']
            res.append(r)

        cert_trans_worker.make_op_log(request.remote_addr, request.remote_addr,[], 'portal_sync')

        return make_response(json.dumps(res))

    except Exception:
        logger.debug('/internal/cert/sync/portal')
        logger.debug(traceback.format_exc())
        logger.debug(e.__str__())
        return jsonify({"code": 500, "msg": "The schema of request is error."})



@certificate_transport.route("/internal/cert/trans/result", methods=['GET', 'POST'])
def cert_trans_result():
    '''
    证书下发执行结果回调
    '''
    try:
        data = json.loads(request.data)
        logger.debug('cert_trans_result remote_ip %s, get data is %s' %(request.remote_addr, data))
        res = {'status':200, 'task_ids':[i['task_id'] for i in data]}
        cert_trans_worker.save_result.delay(data, request.remote_addr)
        return jsonify(res)
    except Exception:
        logger.debug('/internal/cert/trans/result error')
        logger.debug(traceback.format_exc())
        logger.debug(e.__str__())
        return jsonify({"code": 500, "msg": "The schema of request is error."})

@certificate_transport.route("/internal/cert/query/result", methods=['GET', 'POST'])
def cert_query_result():
    '''
    证书查询执行结果回调
    '''
    try:
        data = json.loads(request.data)
        logger.debug('cert_trans_result remote_ip %s, get data is %s' %(request.remote_addr, data))
        res = {'status':200, 'task_ids':[i['task_id'] for i in data]}
        cert_query_worker.save_result.delay(data, request.remote_addr)
        return jsonify(res)
    except Exception:
        logger.debug('/internal/cert/query/result error')
        logger.debug(traceback.format_exc())
        logger.debug(e.__str__())
        return jsonify({"code": 500, "msg": "The schema of request is error."})

@certificate_transport.route("/internal/cert/transfer_cert/result",methods=['GET', 'POST'])
def transfer_cert_result():
    '''
    证书转移执行结果回调
    '''
    try:
        data = json.loads(request.data)
        logger.debug('transfer_cert_result remote_ip %s, get data is %s' %(request.remote_addr, data))
        res = {'status':200, 'task_ids':[i['task_id'] for i in data]}
        transfer_cert_worker.save_result.delay(data, request.remote_addr)
        return jsonify(res)
    except Exception:
        logger.debug('/internal/cert/transfer/result error')
        logger.debug(traceback.format_exc())
        logger.debug(e.__str__())
        return jsonify({"code": 500, "msg": "The schema of request is error."})


@certificate_transport.route("/internal/cert/dev/pull",methods=['GET', 'POST'])
def cert_trans_dev_pull():
    '''
    设备同步所有证书
    '''
    try:
        o_data = zlib.decompress(request.data)
        data = json.loads(o_data)
        hostname = data['hostname']
        sign = data['sign']
        ignore_n = data['ignore_crt']
        #logger.debug('cert_trans_dev_pull remote_ip %s, get data is %s' %(request.remote_addr, data))
        logger.debug('cert_trans_dev_pull remote_ip %s' %(request.remote_addr))
        #if not ignore_n:
        #    raise
        #验证签名
        _h = rsa_tools.deal(base64.b64decode(sign), 'chinacache')
        logger.debug('A _h is %s, hostname is %s'%(_h, hostname))
        if _h != hostname:
            logger.debug('B _h is %s, hostname is %s'%(_h, hostname))
            raise
        if ignore_n == None:
            ignore_n = []
        all_certs = cert_trans_worker.get_all_cert_by_dev(ignore_n,ignore_transfer=True)
        logger.debug('cert_trans_dev_pull remote_ip %s, all_certs len  is %s' %(request.remote_addr, len(all_certs)))
        cert_trans_worker.make_op_log(hostname, request.remote_addr,[], 'dev_pull')
        #return make_response(json.dumps(all_certs))
        return make_response(zlib.compress(json.dumps(all_certs)))

    except Exception:
        logger.debug('/internal/cert/apply/callback error remote_addr %s'%(request.remote_addr))
        logger.debug(traceback.format_exc())
        return jsonify({"code": 500, "msg": "The schema of request is error."})


@certificate_transport.route("/internal/cert/dev/day/pull",methods=['GET', 'POST'])
def cert_trans_update_pull():
    '''
    夜间设备同步所有证书
    '''

    try:
        logger.debug("request.data is %s"%request.data)
        o_data = zlib.decompress(request.data)
        logger.debug("o_data is %s"%o_data)
        data = json.loads(o_data)
        hostname = data['hostname']
        sign = data['sign']
        version = data['version']
        #logger.debug('cert_trans_dev_pull remote_ip %s, get data is %s' %(request.remote_addr, data))
        logger.debug('cert_trans_update_pull remote_ip %s' %(request.remote_addr))
        #if not ignore_n:
        #    raise
        #验证签名
        _h = rsa_tools.deal(base64.b64decode(sign), 'chinacache')
        logger.debug('C _h is %s, hostname is %s'%(_h, hostname))
        if _h != hostname:
            logger.debug('D _h is %s, hostname is %s'%(_h, hostname))
            raise
        #o_data = zlib.decompress(request.data)
        all_certs=cert_trans_worker.get_allcertdata_from_redis(version)
        if not all_certs:
            all_certs = cert_trans_worker.get_cert_transferAndadd(version)
        logger.debug('cert_trans_dev_pull remote_ip %s, all_certs is %s' %(request.remote_addr, all_certs))
        cert_trans_worker.make_op_log(hostname, request.remote_addr,[], 'dev_day_pull')
        #return make_response(json.dumps(all_certs))
        return make_response(zlib.compress(json.dumps(all_certs)))

    except Exception:
        logger.debug('/internal/cert/apply/callback error remote_addr %s'%(request.remote_addr))
        logger.debug(traceback.format_exc())
        return jsonify({"code": 500, "msg": "The schema of request is error."})

#@certificate_transport.route("/internal/cert/apply")
#def cert_trans_op():
#    '''
#    FC SMS 设备证书申请　
#    '''
#    try:
#
#        data = json.loads(request.data)
#        username = data['username']
#        password = data['password']
#        task_id = data['task_id']
#
#        #TODO　校验用户名　密码
#        cert_info = cert_trans_worker.get_cert_by_task_id(task_id)
#        if not cert_info:
#            raise
#
#        cert = cert_info['cert']
#        r_cert = cert_info['r_cert']
#        p_key = cert_info['p_key']
#        save_name = cert_info['save_name']
#
#        seed = cert_trans_worker.get_custom_seed(username)
#
#        combine_cert = cert + r_cert
#        combine_cert_e = rsa_tools.fun(combine_cert, rsa_tools.cache_pub_key, rsa_tools.bermuda_pri_key, seed)
#        p_key_e = rsa_tools.fun(p_key,rsa_tools.cache_pub_key, rsa_tools.bermuda_pri_key, seed)
#
#        dir_name = cert_trans_worker.make_dir(username)
#        cert_root_dir = cert_trans_worker.CERT_DIR
#        z = zipfile.ZipFile('%s%s.zip'%(cert_root_dir,dir_name), 'a', zipfile.ZIP_DEFLATED)
#        z.writestr('%s.crt'%(save_name), combine_cert_e)
#        z.writestr('%s.key'%(save_name), p_key_e)
#        z.close()
#        zip_file = file('%s%s.zip'%(cert_root_dir,dir_name))
#        resp = Response(zip_file, mimetype="application/zip", headers={'Content-Disposition': 'attachment; filename=%s'%(dir_name + '.zip')})
#        try:
#            os.remove('%s%s.zip'%(cert_root_dir,dir_name))
#            shutil.rmtree('%s%s'%(cert_root_dir,dir_name))
#        except Exception, e:
#            pass
#
#        #TODO 加入操作日志
#        cert_trans_worker.make_op_log(username, request.remote_addr,task_id, 'apply')
#        return resp
#
#    except Exception, e:
#        logger.debug(traceback.format_exc())
#        logger.debug(e.__str__())
#        return jsonify({"code": 500, "msg": "The schema of request is error."})


def make_task(data, _type='portal'):
    '''
    生成证书任务
    '''
    if _type == 'portal':
        s1_db = database.s1_db_session()
        username = data.get('username', 'chinacache')
        user_id = data.get('user_id', 2275)
        p_key = data.get('p_key', '')
        cert = data.get('cert', '')
        r_cert = data.get('r_cert', '')
        cert_alias = data.get('cert_name', 'chinacache-cert')
        seed = cert_trans_worker.get_custom_seed(username)

        is_rigid = data.get('rigid',False)

        try:
            cert_sum = s1_db.cert_detail.find({"username":username,'cert_alias':cert_alias}).count()
            if cert_sum >= 1:
                raise CertAliasError('cert alias has already existed')
        except Exception:
            logger.debug(traceback.format_exc())
            raise
        #私钥
        try:
            p_key_cip, p_key_sign = rsa_tools.split_ciphertext_and_sign(p_key)
            p_key = rsa_tools.decrypt_trunk(p_key_cip, rsa_tools.bermuda_pri_key)
            try:
                rsa_tools.verify_sign(p_key_sign, rsa_tools.portal_pub_key, p_key)
            except Exception:
                logger.debug('---p_key--- verify_sign error---')
                logger.debug(traceback.format_exc())
                raise CertDecryptError('Private key of verify_sign error')

        except Exception:
            logger.debug('---p_key--- decrypt error---')
            logger.debug(traceback.format_exc())
            raise CertDecryptError('Private key of decryption error')

        #证书
        try:
            cert_cip, cert_sign = rsa_tools.split_ciphertext_and_sign(cert)
            cert = rsa_tools.decrypt_trunk(cert_cip, rsa_tools.bermuda_pri_key)
            try:
                rsa_tools.verify_sign(cert_sign, rsa_tools.portal_pub_key, cert)
            except Exception:
                logger.debug('---cert--- verify_sign error---')
                logger.debug(traceback.format_exc())
                raise CertDecryptError('Cert of verify_sign error')
            #去掉多余回车
            cert = cert.strip('\n')

        except Exception:
            logger.debug('---cert--- decrypt error---')
            logger.debug(traceback.format_exc())
            raise CertDecryptError('Cert key of decryption eror')

        if r_cert:
            #根证书
            try:
                r_cert_cip, r_cert_sign = rsa_tools.split_ciphertext_and_sign(r_cert)
                r_cert = rsa_tools.decrypt_trunk(r_cert_cip, rsa_tools.bermuda_pri_key)
                try:
                    rsa_tools.verify_sign(r_cert_sign, rsa_tools.portal_pub_key, r_cert)
                except Exception:
                    logger.debug('---r_cert--- verify_sign error---')
                    logger.debug(traceback.format_exc())
                    raise CertDecryptError('R_cert of verify_sign eror')
                #去掉多余回车
                r_cert = r_cert.strip('\n')

            except Exception:
                logger.debug('---r_cert--- decrypt error---')
                logger.debug(traceback.format_exc())
                raise CertDecryptError('R_cert key of decryption eror')

        #私钥是否为PKCS1
        if 'BEGIN PRIVATE KEY' in p_key:
            raise CertPrikeyTypeError('RSA Private Key must be (PKCS#1)')


        #提交内容合并
        all_cert = cert
        if r_cert:
            all_cert = cert + '\n' + r_cert

        if cert_tools.crt_number(all_cert) < 1:
            raise CertInputError('Certificate must be more content')

        middle_cert_lack = False
        if cert_tools.crt_number(all_cert) < 2:
            '''
            判断有没有中间证书
            '''
            middle_cert_lack = True
        if middle_cert_lack and is_rigid:
            raise CertNoMiddle('Please upload intermediate certificate ')
        all_cert_checked = cert_tools.get_all_chain(all_cert)
        if not all_cert_checked:
            raise CertPathError('The certificate path does not match')
        if all_cert_checked == 1:
            raise CertNoRoot('The match root certificate fails')
        if all_cert_checked in [2, 3]:
            raise CertNoMiddle('The matching intermediate certificate fails')

        cert_last = cert_tools.get_cert(all_cert_checked)[0]

        #检查子证书和私钥match
        if not cert_tools.check_consistency(cert_last, p_key):
            raise CertPrikeyError('Certificates and private keys does not match')


        #检查子证书是否吊销
        crl_info = cert_tools.get_crl(cert_last)
        if crl_info:
            crl_object = cert_tools.get_crl_object(crl_info)
            if crl_object:
                if cert_tools.get_revoke(cert_last, crl_object):
                    raise CertRevokeError('Certificate has been revoked')

        #检查子证书是否过期
        if cert_tools.is_expire(cert_last):
            raise CertExpireError('Certificate Is Expired')

        #解析子证书主要信息
        cert_last_subject = cert_tools.get_subject(cert_last)
        cert_last_issuer = cert_tools.get_issuer(cert_last)
        cert_last_validity = cert_tools.get_Validity(cert_last)
        cert_last_pubkey = cert_tools.get_public_key(cert_last)
        cert_last_DNS = cert_tools.get_DNS(cert_last)

        end_time = cert_tools.make_validity_to_China(cert_last_validity)['end_time']
        end_time_obj = datetime.datetime.strptime(end_time,'%Y%m%d%H%M%S')
        end_time_name = end_time_obj.strftime('%Y-%m-%d-%H')
        now_time_name = datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S')

        if cert_last_DNS:
            save_dns_name = cert_last_DNS[0]
        else:
            save_dns_name = cert_last_subject['CN']

        #替换泛域名×
        save_dns_name = save_dns_name.replace('*','_')
        save_name = '%s-%s-%s'%(end_time_name, save_dns_name, now_time_name)

        #检查存储名是否冲突
        if s1_db.cert_detail.find_one({'save_name':save_name}):
            raise CertSaveNameError('The certificate had same save name')


        #加密证书&pk

        try:
            p_key_e = rsa_tools.fun(p_key,rsa_tools.cache_pub_key, rsa_tools.bermuda_pri_key, seed)
            all_cert_e = rsa_tools.fun(all_cert_checked, rsa_tools.cache_pub_key, rsa_tools.bermuda_pri_key, seed)
            #r_cert_e = rsa_tools.fun(r_cert,rsa_tools.cache_pub_key, rsa_tools.bermuda_pri_key, seed)
        except Exception:
            logger.debug('---make_task--- encrypt error---')
            logger.debug(traceback.format_exc())
            raise

        #origin cert
        o_c_id = s1_db.cert_origin.insert({'cert_origin':cert, 'cert_origin_r': r_cert, 'cert_all': all_cert_checked, 'created_time': datetime.datetime.now()})

        #cert
        c_id = s1_db.cert_detail.insert({'cert':all_cert_e,'p_key':p_key_e,'username':username, 'seed': seed, 'o_c_id': o_c_id, 'cert_alias':cert_alias, 'save_name': save_name, 'subject': cert_last_subject, 'issuer': cert_last_issuer, 'validity': cert_last_validity,'pubkey':cert_last_pubkey, 'DNS':cert_last_DNS, 'user_id':user_id, 'created_time':datetime.datetime.now(),'middle_cert_lack':middle_cert_lack})

        task = {'_id': str(ObjectId()),'middle_cert_lack':middle_cert_lack ,'username':username, 'p_key': p_key_e,'cert':all_cert_e, 'created_time':datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'c_id': str(c_id), 'send_devs': 'all_hpcc', 'cert_alias': cert_alias, 'o_c_id': str(o_c_id), 'op_type':"add", 'seed':seed, 's_name':save_name, 's_dir': HPCC_SAVE_DIR, 'user_id': user_id, 'recev_host': RECEV_HOST}


        return task
    else:
        raise

class CertInputError(Exception):
    '''
    证书内容异常
    '''
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class CertNoRoot(Exception):
    '''
    证书匹配根证书失败
    '''
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)

class CertNoMiddle(Exception):
    '''
    证书匹配中间证书失败
    '''
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class CertExpireError(Exception):
    '''
    证书过期异常
    '''
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)

class CertRevokeError(Exception):
    '''
    证书吊销异常
    '''
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)

class CertPrikeyError(Exception):
    '''
    证书私钥不匹配异常
    '''
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)

class CertPrikeyTypeError(Exception):
    '''
    私钥格式错误
    '''
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class CertPathError(Exception):
    '''
    证书私钥不匹配异常
    '''
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)

class CertDecryptError(Exception):
    '''
    证书私钥解密异常
    '''
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)

class CertAliasError(Exception):
    '''
    证书别名已存在
    '''
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)

class CertNotFoundError(Exception):
    '''
    查询证书不存在
    '''
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class CertSaveNameError(Exception):
    '''
    证书存储名异常
    '''
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)
class QuerypathError(Exception):
    '''
    查询路径异常
    '''
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)
class QueryconpathError(Exception):
    '''
    查询的配置路径异常
    '''
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)
class QueryipError(Exception):
    '''
    查询ip异常
    '''
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)
class QuerychannelError(Exception):
    '''
    查询频道异常
    '''
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)
class QuerycertnameError(Exception):
    '''
    查询的证书名称异常
    '''
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)
class QuerydevicesError(Exception):
    '''
    查询设备异常
    '''
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)
class QuerycerttypeError(Exception):
    '''
    查询的证书类型异常
    '''
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)
class TransferdevError(Exception):
    '''
    证书转移设备异常
    '''
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)
