#-*- coding:utf-8 -*-
import io
import gzip
import hashlib
import os
import shutil
import time
import traceback
import urllib.request, urllib.error, urllib.parse, urllib.request, urllib.parse, urllib.error
import http.client,httplib2
import zipfile
from datetime import datetime, timedelta

import simplejson as json
from flask import render_template,  request,session ,Flask, current_app, redirect, make_response, Response
from flask_principal import Principal, Permission, UserNeed, RoleNeed, Identity, AnonymousIdentity, identity_changed, identity_loaded

from .models import User, find_urls, find_urls_for_csv, get_devs_by_id, get_user, get_user_list, add_user, del_user,get_retryDevice_by_id, find_cert_tasks,find_cert_query,find_cert_query_tasks,find_transfer_cert_tasks,get_devs_cert_task,get_devs_cert_task_res,get_expired_cert_res,get_devs_cert_query_task,get_devs_cert_query_task_res,get_devs_cert_query_task_detail, find_cert, cert_all_count,get_devs_transfer_cert_task,get_devs_transfer_cert_task_res,get_devs_transfer_cert_task_detail
from .models import get_channelignore_list, add_channelignore_data, del_channelignore_data
from .models import get_keycustomer_list,add_keycustomer_data,del_keycustomer_data
from .models import get_overloads_config_list, add_overloads_config_data, del_overloads_config_data
from .models import get_regex_list, add_regex_data, del_regex_data
from .models import get_rewrite_list, add_rewrite_data, del_rewrite_data
from .models import get_timer_tasks,add_timer_tasks_data,del_timer_tasks_data
from .models import retry_api, model_update_callback_email, model_delete_callback_email

from .models import get_retry_re_id
# add content
# from models import rewrite_query_n_to_n, update_rewrite_id, update_rewrite_no_id, delete_rewrite_id
from receiver.receiver_rewrite import rewrite_query, update_rewrite_no_id, delete_rewrite_id,\
                                       update_prefix_data, delete_rewrite_prefix_id, rewrite_prefix_query
from bson import ObjectId
from .models import get_rewrite_list_new, find_link_device_hours_result, get_device_link_detail

from .models import get_url_by_id, callback_email_query
from .models import get_refresh_result_by_sessinId, get_retry_dev_branch_by_id, get_retry_dev_bran_by_id, statistic_banch_code, \
    get_hour_link_detect_result, get_hour_link_detect_result_province, get_subcenter_info
from .models import find_urls_custom, get_devs_custom_by_id, parse_dev_custom_result
from .models import get_device_monitor, get_device_monitor_page, get_device_failed_url, device_failed_url_to_txt, get_device_failed_detail_page, init_monitor_data, make_failed_url_res
from .models import get_all_refresh_high_priority_page, get_refresh_high_priority_unopen, add_refresh_high_priority, del_refresh_high_priority
from .models import get_email_management_list, add_email_management, del_email_management, get_devs_opened, insert_email_management, operation_log_list
from core.config import config
from .preload import preload
from util import tools
import core.rcms_change_worker as rcms_change_worker
from util.tools import strip_list_remove_blank
from core import cert_trans_worker,cert_query_worker
from util import rsa_tools
from new_admin.models_physical_del import physical_del_channel_qu, delete_physical_del_channel_id, get_physical_del_channel_list,\
                                update_physical_del_channel_data


from logging import Formatter
import logging.handlers,logging
from cache.rediscache import device_cache, channels_cache
#import httplib2 as httplib

from .models import get_regex_list_h
from .models import add_regex_data_h,del_regex_data_h
from .models import get_subcent_refresh_dev,get_sub_refreh_result
from .models import find_expired_cert

from .models import get_domain_ignore_list,add_domain_lignore_data,del_domain_ignore_data
from .models import get_dirandurl_list,add_dirandurl_data,del_dir_and_url_data
import imp


LOG_FILENAME = '/Application/bermuda3/logs/new_admin.log'
handler = logging.handlers.RotatingFileHandler(LOG_FILENAME, maxBytes=100000000, backupCount=5)
handler.setFormatter(Formatter('%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s'))

app = Flask(__name__,static_folder='static', template_folder='templates')
app.register_blueprint(preload)
app.logger.setLevel(logging.DEBUG)
app.logger.addHandler(handler)
app.secret_key = 'A0Zr98j/3yX R~XHH!jmN]LWX/,?RT'


import sys
imp.reload(sys)

# load the extension
principals = Principal(app)

# Create a permission with a single Need, in this case a RoleNeed.
all_permission = Permission(RoleNeed('admin'),RoleNeed('operator'))
admin_permission = Permission(RoleNeed('admin'))

@app.errorhandler(401)
def unauthorized(e):
    return render_template('errors.html',message ="unauthorized" ), 401

@app.errorhandler(400)
def page_not_found(e):
    return render_template('errors.html', message=e.description), 400

@app.errorhandler(403)
def access_forbidden(e):
    return render_template('errors.html', message=e.description), 403

@app.errorhandler(404)
def access_notfound(e):
    return render_template('errors.html', message='The requested URL was not found on the server. '), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('index.html'), 500

@app.before_request
def before_request():
    """Make sure we are connected to the database each request."""
    #p = request.path.split(".")
    #plist = ["js","css","png","ico"]
    #if request.path != '/auth' and request.path != "/login" and p[len(p)-1] not in plist:
    if 'index' in request.path :
        return index()
    app.logger.info("request path:  %s" %(request.path))

@identity_loaded.connect_via(app)
def on_identity_loaded(sender, identity):
    identity.user = session.get("user")
    if session.get("user"):
        identity.provides.add(UserNeed(session.get("user").account))
        identity.provides.add(RoleNeed(session.get("user").role))

@app.route("/logout", methods=['GET'])
def logout():
    app.logger.info("user logout: user - %s " % session.get("user"))
    try:
        session.pop("user")
    except Exception:
         app.logger.error(traceback.format_exc())
    for key in ('identity.name', 'identity.auth_type'):
        session.pop(key, None)
    # Tell Flask-Principal the user is anonymous
    identity_changed.send(current_app._get_current_object(),
                          identity=AnonymousIdentity())
    return redirect('/login')

@app.route("/auth", methods=['GET'])
def auth():
    try:
        ioss = request.args.get('ioss')
        md5 = hashlib.md5()
        md5.update(config.get('admin', 'client') + ioss + "CssoC")
        # hc = httplib2.Http(timeout=4)
        # repo, response_body = hc.request('https://sso.chinacache.com/queryByTokenId?clientName=' + config.get('admin', 'client') + '&tokenId=%s&md5Hash=%s' % (ioss, md5.hexdigest()))
        try:

            urllib.request.ssl._DEFAULT_CIPHERS += 'HIGH:!DH:!aNULL'
            response = urllib.request.urlopen('https://sso.chinacache.com/queryByTokenId?clientName=' + config.get('admin', 'client') + '&tokenId=%s&md5Hash=%s' % (ioss, md5.hexdigest()))
        except Exception:
            urllib.ssl._DEFAULT_CIPHERS += 'HIGH:!DH:!aNULL'
            response = urllib.request.urlopen('https://sso.chinacache.com/queryByTokenId?clientName=' + config.get('admin', 'client') + '&tokenId=%s&md5Hash=%s' % (ioss, md5.hexdigest()))

        response_body = response.read()
        app.logger.debug(response_body)
        user_info = json.loads(response_body)
        user = get_user(user_info)
        session["user"] = user
        identity_changed.send(current_app._get_current_object(),
                              identity=Identity(user.account))
        app.logger.info("user login: account - %s, role- %s" %(session.get("user").account,session.get("user").role))
        return index()
    except Exception:
        app.logger.error(traceback.format_exc())


@app.route('/', methods=['GET', 'POST'])
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    return render_template('login.html',client=config.get('admin', 'client'))


@app.route('/cert_tools', methods=['GET'])
@all_permission.require(http_exception=401)
def cert_tools():

    username = session.get('user').account
    app.logger.info('----user account %s'%(username))
    if not username:
        raise
    seed = cert_trans_worker.get_custom_seed(username)
    total_count = cert_all_count()

    return render_template('cert_tools.html',seed=seed, total_count=total_count)


@app.route('/cert_callback', methods=['POST'])
@all_permission.require(http_exception=401)
def cert_callback():

    username = session.get('user').account
    app.logger.info('----user account %s'%(username))

    if not username:
        raise

    cert_id = request.form.get('cert_id', '')
    if not cert_id:
        return json.dumps({'msg':'no cert_id'})
    try:
        cert_info = cert_trans_worker.get_cert_info(cert_id)
        if not cert_info:
            return json.dumps({'msg':'no cert'})

        task_info = cert_trans_worker.get_task_info_by_cert_id(cert_id)
        if not task_info:
            return json.dumps({'msg':'no task'})

        success = cert_trans_worker.make_all_callback(task_info, cert_info)
        cert_trans_worker.make_op_log(username, request.remote_addr, [cert_id], 'cert_callback')
        if success:
            return json.dumps({'msg':'ok'})
        else:
            return json.dumps({'msg':'callback failed'})
    except Exception:
        app.logger.info('----cert_callback error %s'%(e))
        return json.dumps({'msg':'please enter right cert id'})


@app.route('/cert_download_all', methods=['GET'])
@all_permission.require(http_exception=401)
def cert_download_all():
    '''
    下载全部证书
    '''
    return cert_download()

         

@app.route('/cert_download', methods=['POST'])
@all_permission.require(http_exception=401)
def cert_download():
    '''
    证书下载
    '''
    username = session.get('user').account
    app.logger.info('----user account %s'%(username))
    if not username:
        raise
    seed = cert_trans_worker.get_custom_seed(username)
    download_ids = request.form.get('download_ids')
    app.logger.info('download_ids %s'%(download_ids))
    if not download_ids:
        download_id_list = []
    else:
        download_id_list = download_ids.split(',')
    app.logger.info('download_id_list %s'%(download_id_list))

    if not download_id_list:
        #执行全部证书下载
        all_certs = cert_trans_worker.get_all_cert()
    else:
        all_certs = cert_trans_worker.get_cert_by_ids(download_id_list)

    dir_name = cert_trans_worker.make_dir(username)
    cert_root_dir = cert_trans_worker.CERT_DIR
    try:
        z = zipfile.ZipFile('%s%s.zip'%(cert_root_dir,dir_name), 'a', zipfile.ZIP_DEFLATED)
        for cert in all_certs:

            cert_body = cert.get('cert')
            p_key = cert.get('p_key')
            save_name = cert.get('save_name')
            cert_type = cert.get('cert_type')
            if not cert_body:
                continue
            combine_cert = cert_body
            #加密 TODO 钥匙替换
            combine_cert_e = rsa_tools.fun(combine_cert, rsa_tools.cache_pub_key, rsa_tools.bermuda_pri_key, seed)
            p_key_e = rsa_tools.fun(p_key,rsa_tools.cache_pub_key, rsa_tools.bermuda_pri_key, seed)

            z.writestr('%s.%s'%(save_name, cert_type), combine_cert_e)
            z.writestr('%s.key'%(save_name), p_key_e)

        z.close()
        zip_file = file('%s%s.zip'%(cert_root_dir,dir_name))
        resp = Response(zip_file, mimetype="application/zip", headers={'Content-Disposition': 'attachment; filename=%s'%(dir_name + '.zip')})
        if download_id_list:
            cert_trans_worker.make_op_log(username, request.remote_addr, download_id_list, 'cert_download')
        else:
            cert_trans_worker.make_op_log(username, request.remote_addr, [], 'cert_download_all')
        os.remove('%s%s.zip'%(cert_root_dir,dir_name))
        shutil.rmtree('%s%s'%(cert_root_dir,dir_name))
        return resp
    except Exception:
        app.logger.debug('--cert_download error is %s'%(e))
        os.remove('%s%s.zip'%(cert_root_dir,dir_name))
        shutil.rmtree('%s%s'%(cert_root_dir,dir_name))
        raise


@app.route('/query_cert_task', methods=['GET', 'POST'])
def query_cert_task():

    totalpage = 0
    args = {"totalpage":totalpage,"curpage":int(request.form.get("curpage",0)),
    "username":request.form.get("username",""),"status":request.form.get("status",""),
    "task_id":request.form.get("task_id",""),"date":request.form.get("date",datetime.strftime(datetime.now(),"%m/%d/%Y")),
    "query_type": request.form.get("query_type", 'normal_query'),
    "start_datetime":request.form.get("start_datetime",(datetime.now() - timedelta(hours=1)).strftime('%Y-%m-%d %H')),
    "end_datetime":request.form.get("end_datetime",(datetime.now() + timedelta(hours=1)).strftime('%Y-%m-%d %H')),
    }
    tasks_dict = find_cert_tasks(args)
    args["totalpage"] = tasks_dict.get("totalpage")
    return render_template('query_cert_tasks.html', tasks=tasks_dict.get("tasks"),args=args)

@app.route('/cert_query_task', methods=['GET', 'POST'])
def cert_query_task():

    totalpage = 0
    args = {"totalpage":totalpage,"curpage":int(request.form.get("curpage",0)),
    "username":request.form.get("username",""),"status":request.form.get("status",""),
    "task_id":request.form.get("task_id",""),"date":request.form.get("date",datetime.strftime(datetime.now(),"%m/%d/%Y")),
    "query_type": request.form.get("query_type", 'normal_query'),
    "start_datetime":request.form.get("start_datetime",(datetime.now() - timedelta(hours=1)).strftime('%Y-%m-%d %H')),
    "end_datetime":request.form.get("end_datetime",(datetime.now() + timedelta(hours=1)).strftime('%Y-%m-%d %H')),
    }
    tasks_dict = find_cert_query_tasks(args)
    args["totalpage"] = tasks_dict.get("totalpage")
    app.logger.info('tasks_dict is %s'%tasks_dict)
    return render_template('cert_query_tasks.html', tasks=tasks_dict.get("tasks"),args=args)

@app.route('/transfer_cert_task', methods=['GET', 'POST'])
def transfer_cert_task():

    totalpage = 0
    args = {"totalpage":totalpage,"curpage":int(request.form.get("curpage",0)),
    "username":request.form.get("username",""),"status":request.form.get("status",""),
    "task_id":request.form.get("task_id",""),"date":request.form.get("date",datetime.strftime(datetime.now(),"%m/%d/%Y")),
    "query_type": request.form.get("query_type", 'normal_query'),
    "start_datetime":request.form.get("start_datetime",(datetime.now() - timedelta(hours=1)).strftime('%Y-%m-%d %H')),
    "end_datetime":request.form.get("end_datetime",(datetime.now() + timedelta(hours=1)).strftime('%Y-%m-%d %H')),
    }
    tasks_dict = find_transfer_cert_tasks(args)
    args["totalpage"] = tasks_dict.get("totalpage")
    app.logger.info('tasks_dict is %s'%tasks_dict)
    return render_template('transfer_cert_tasks.html', tasks=tasks_dict.get("tasks"),args=args)

@app.route("/expired_cert_portal", methods=['GET','POST'])
@all_permission.require(http_exception=401)
def expired_cert_portal():
    time_now = datetime.now()
    app.logger.debug("time_now is%s" %time_now)
    timing = time_now.strftime("%Y-%m-%d %H:%M")
    app.logger.debug("timing is%s" %timing)
    args = {}
    args['timing'] = timing
    return render_template('expired_cert_portal.html',args=args)

@app.route('/expired_cert', methods=['GET', 'POST'])
@all_permission.require(http_exception=401)
def expired_cert():
    username = session.get('user').account
    app.logger.info('----user account %s'%(username))
    if not username:
        raise
    totalpage = 0
    args = {"totalpage":totalpage,"curpage":int(request.form.get("curpage",0)),
    "username":request.form.get("username",""),"cert_alias":request.form.get("cert_alias",""),
     "save_name":request.form.get("save_name", "")}
    certs_dict = find_expired_cert(args)
    args["totalpage"] = certs_dict.get("totalpage")
    app.logger.debug("cert_dict is %s"%certs_dict)
    return render_template('expired_cert.html',certs=certs_dict.get("certs"),args=args)

@app.route("/expired_cert_res/<cert_id>", methods=['GET','POST'])
def expired_cert_res(cert_id):
    app.logger.info("cert_id is %s"%cert_id)
    DNS_info, subject_info, issuer_info,type_info = get_expired_cert_res(cert_id)
    return render_template('expired_cert_res.html', DNS_info=DNS_info, subject_info=subject_info, issuer_info=issuer_info,type_info=type_info)

@app.route("/transfer_expired_cert/<save_name>", methods=['GET','POST'])
def transfer_expired_cert(save_name):
    #usernamecert_name = request.form.get('cert_name')
    username = session.get('user').account
    try:
        url = config.get('app', 'url')
    except:
        url = "r.chinacache.com"
    o_path = config.get('app', 'o_path')
    d_path = config.get('app', 'd_path')
    conn = http.client.HTTPConnection(url)
    headers = {"Content-type":"application/json"}
    params = ({'save_name': save_name,'username':username,'transfer_dev':'all_hpcc','o_path':o_path,'d_path':d_path})
    conn.request("POST", "/internal/cert/transfer_expired_cert", json.JSONEncoder().encode(params), headers)
    response = conn.getresponse()
    res=json.loads(response.read())
    app.logger.debug('response is %s'%res)
    conn.close()
    if res['code']==200:
        return json.dumps(res['code'])
    else:
        return json.dumps(res['msg'])
    return jsonify(res)


@app.route('/query_cert', methods=['GET', 'POST'])
@all_permission.require(http_exception=401)
def query_cert():

    username = session.get('user').account
    app.logger.info('----user account %s'%(username))
    if not username:
        raise
    seed = cert_trans_worker.get_custom_seed(username)
    args = {"curpage":int(request.form.get("curpage",0)),
    "username":request.form.get("username",""),"cert_id":request.form.get("cert_id",""),
    "cert_alias":request.form.get("cert_alias",""), "save_name":request.form.get("save_name", ""),
    "type":request.form.get("type",""),
    }
    certs_dict = find_cert(args)
    args["totalpage"] = certs_dict.get("totalpage")
    page = int(request.form.get('curpage', 0))
    page_list, can_pre_page, can_next_page = tools.pager(int(args["totalpage"]), page)
    args["curpage"] = page
    args["page_list"] = page_list
    args["can_pre_page"] = can_pre_page
    args["can_next_page"] = can_next_page

    app.logger.debug("cert_dict is %s"%certs_dict)
    return render_template('query_cert.html', certs=certs_dict.get("certs"),args=args, seed=seed)


@app.route("/cert_portal", methods=['GET','POST'])
@all_permission.require(http_exception=401)
def cert_portal():
    time_now = datetime.now()
    app.logger.debug("time_now is%s" %time_now)
    timing = time_now.strftime("%Y-%m-%d %H:%M")
    app.logger.debug("timing is%s" %timing)
    args = {}
    args['timing'] = timing
    return render_template('cert_portal.html',args=args)


@app.route("/cert_portal_action", methods=['GET','POST'])
def cert_portal_action():
    #username = request.form.get('username')
    username = session.get('user').account
    cert_name = request.form.get('cert_name')
    query_ip = request.form.get('query_ip')
    cert_type = request.form.get('cert_type')
    utf_username = username.encode("utf-8")
    utf_cert_name = cert_name.encode("utf-8")
    utf_query_ip = query_ip.encode("utf-8")
    utf_cert_type = cert_type.encode("utf-8")
    app.logger.debug('utf_username is %s'%utf_username)
    app.logger.debug('utf_query_ip is %s'%utf_query_ip)
    device_list=utf_query_ip.split('\r\n')
    app.logger.debug("device_list::::%s" %device_list)
    try:
        url = config.get('app', 'url')
    except:
        url = "r.chinacache.com"
    conn = http.client.HTTPConnection(url)
    headers = {"Content-type":"application/json"}
    #params = ({'username': utf_username,'info':{'ip':device_list,'path':'/home/lh/Documents','config_path':'/usr/local/hpc/conf/vhost','type':'isexits4path','cert_name':utf_cert_name}})
    params = ({'username': utf_username,'info':{'cert_type':utf_cert_type,'ip':device_list,'path':'/usr/local/hpc/conf/ssl/','config_path':'/usr/local/hpc/conf/vhost/','type':'isexits4path','cert_name':utf_cert_name}})
    conn.request("POST", "/internal/cert/query", json.JSONEncoder().encode(params), headers)
    response = conn.getresponse()
    res=json.loads(response.read())
    app.logger.debug('response is %s'%res)
    conn.close()
    if res['code']==200:
        return json.dumps(res['code'])
    else:
        return json.dumps(res['msg'])
    return jsonify(res)

@app.route("/transfer_cert_portal_action", methods=['GET','POST'])
def transfer_cert_portal_action():
    #usernamecert_name = request.form.get('cert_name')

    username = session.get('user').account
    query_ip = request.form.get('query_ip')#发送设备的ip列表
    dev_type = request.form.get('dev_type')#发送全网设备还是指定设备
    if request.form.get('save_name').strip()=='':
        return json.dumps({'error':'cert name is null'})
    if dev_type == 'define_dev' and query_ip.strip()=='':
        return json.dumps({'error': 'server ip is null'})
    save_name = request.form.get('save_name').replace('\r\n',',')#转移证书的名称
    save_name = save_name.replace(' ','') #將空格刪除
    utf_username = username.encode("utf-8")
    utf_save_name = save_name.encode("utf-8")
    utf_query_ip = query_ip.encode("utf-8")
    utf_dev_type = dev_type.encode("utf-8")
    #save_name_list=utf_save_name.split('\r\n')
    device_list=query_ip.split('\r\n')
    app.logger.debug("utf_save_name::::%s" %save_name)
    app.logger.debug("device_list::::%s" %device_list)
    o_path = config.get('app', 'o_path')
    d_path = config.get('app', 'd_path')
    try:
        url = config.get('app', 'url')
    except:
        url = "r.chinacache.com"
    conn = http.client.HTTPConnection(url)
    headers = {"Content-type":"application/json"}
    #params = ({'username': utf_username,'transfer_dev':device_list,'o_path':'/usr/local/hpc/conf/ssl/','d_path':'/usr/local/hpc/conf/ssl1/','save_name':save_name_list})
    params = ({'username': utf_username,'transfer_dev':device_list,'o_path':o_path,'d_path':d_path,'save_name':utf_save_name,'dev_type':utf_dev_type})
    conn.request("POST", "/internal/cert/transfer_expired_cert", json.JSONEncoder().encode(params), headers)
    response = conn.getresponse()
    res=json.loads(response.read())
    app.logger.debug('response is %s'%res)
    conn.close()
    if res['code']==200:
        return json.dumps(res['code'])
    else:
        return json.dumps(res['msg'])
    return jsonify(res)


@app.route('/cert_query', methods=['GET', 'POST'])
@all_permission.require(http_exception=401)
def cert_query():

    username = session.get('user').account
    app.logger.info('----user account %s'%(username))
    if not username:
        raise
    totalpage = 0
    args = {"totalpage":totalpage,"curpage":int(request.form.get("curpage",0)),
    "username":request.form.get("username",""),"cert_query_id":request.form.get("cert_query_id",""),
    "cert_name":request.form.get("cert_name",""), "channel":request.form.get("channel", "")
    }
    app.logger.debug("args is %s"%args)
    certs_dict = find_cert_query(args)
    args["totalpage"] = certs_dict.get("totalpage")
    app.logger.debug("cert_dict is %s"%certs_dict)
    return render_template('cert_query.html', cert_query=certs_dict.get("cert_query"),args=args)

@app.route('/query', methods=['GET', 'POST'])
def query_url():
    totalpage = 0
    args = {"totalpage":totalpage,"curpage":int(request.form.get("curpage",0)),
    "username":request.form.get("username",""),"status":request.form.get("status",""),
    "url":request.form.get("url",""),"date":request.form.get("date",datetime.strftime(datetime.now(),"%m/%d/%Y")),
    "query_type": request.form.get("query_type", 'normal_query'),
    "start_datetime":request.form.get("start_datetime",(datetime.now() - timedelta(hours=1)).strftime('%Y-%m-%d %H')),
    "end_datetime":request.form.get("end_datetime",(datetime.now() + timedelta(hours=1)).strftime('%Y-%m-%d %H')),
    "channel_name":request.form.get("channel_name", "")
    }
    urls_dict = find_urls(args)
    args["totalpage"] = urls_dict.get("totalpage")
    return render_template('query.html', urls=urls_dict.get("urls"),args=args)

@app.route('/user_retry', methods=['GET', 'POST'])
def user_retry_url():
    totalpage = 0
    args = {"totalpage":totalpage,"curpage":int(request.form.get("curpage",0)),
    "username":request.form.get("username",""),"status":request.form.get("status",""),
    "url":request.form.get("url",""),"date":request.form.get("date",datetime.strftime(datetime.now(),"%m/%d/%Y")),
    "query_type": request.form.get("query_type", 'normal_query'),
    "start_datetime":request.form.get("start_datetime",(datetime.now() - timedelta(hours=1)).strftime('%Y-%m-%d %H')),
    "end_datetime":request.form.get("end_datetime",(datetime.now() + timedelta(hours=1)).strftime('%Y-%m-%d %H')),
    "channel_name":request.form.get("channel_name", "")
    }
    #retry_user(args)#
   
    try:
        try:
            url = config.get('app', 'url')
        except:
            url = "r.chinacache.com"
        conn = http.client.HTTPConnection(url)
        headers = {"Content-type":"application/json"}
        params = (args)
        conn.request("POST", "/internal/retry_user", json.JSONEncoder().encode(params), headers)
    except Exception:
        app.logger.error('retry_api error:%s' % traceback.format_exc())

    urls_dict = find_urls(args)
    args["totalpage"] = urls_dict.get("totalpage")
    return render_template('query.html', urls=urls_dict.get("urls"),args=args)


@app.route('/page_retry', methods=['GET', 'POST'])
def page_retry_url():
    totalpage = 0
    args = {"totalpage": totalpage, "curpage": int(request.form.get("curpage", 0)),
            "username": request.form.get("username", ""), "status": request.form.get("status", ""),
            "url": request.form.get("url", ""),
            "date": request.form.get("date", datetime.strftime(datetime.now(), "%m/%d/%Y")),
            "query_type": request.form.get("query_type", 'normal_query'),
            "start_datetime": request.form.get("start_datetime",
                                               (datetime.now() - timedelta(hours=1)).strftime('%Y-%m-%d %H')),
            "end_datetime": request.form.get("end_datetime",
                                             (datetime.now() + timedelta(hours=1)).strftime('%Y-%m-%d %H')),
            "channel_name": request.form.get("channel_name", "")
            }
    # retry_user(args)#

    try:
        try:
            url = config.get('app', 'url')
        except:
            url = "r.chinacache.com"
        conn = http.client.HTTPConnection(url)
        headers = {"Content-type": "application/json"}
        params = ({"strurl":request.form.get("strurl")})
        conn.request("POST", "/internal/page_retry", json.JSONEncoder().encode(params), headers)
    except Exception:
        app.logger.error('retry_api error:%s' % traceback.format_exc())

    urls_dict = find_urls(args)
    args["totalpage"] = urls_dict.get("totalpage")
    return redirect('/query')
    #return render_template('query.html', urls=urls_dict.get("urls"), args=args)

@app.route('/query_custom', methods=['GET', 'POST'])
def query_url_custom():
    app.logger.debug("/quer_custom get request")
    totalpage = 0
    args = {"totalpage":totalpage,"curpage":int(request.form.get("curpage",0)),
    "username":request.form.get("username",""),"status":request.form.get("status",""),
    "url":request.form.get("url",""),"date":request.form.get("date",datetime.strftime(datetime.now(),"%m/%d/%Y")),
    "query_type": request.form.get("query_type", 'normal_query'),
    "start_datetime":request.form.get("start_datetime",(datetime.now() - timedelta(hours=1)).strftime('%Y-%m-%d %H')),
    "end_datetime":request.form.get("end_datetime",(datetime.now() + timedelta(hours=1)).strftime('%Y-%m-%d %H')),
    "channel_name":request.form.get("channel_name", "")
    }
    urls_dict = find_urls_custom(args)
    args["totalpage"] = urls_dict.get("totalpage")
    return render_template('query_custom.html', urls=urls_dict.get("urls"),args=args)

@app.route('/query_to_csv', methods=['GET', 'POST'])
def query_to_csv():
    '''
    查询并导出
    '''
    args = {}
    args["url"] = request.form.get("url","")
    args["username"] = request.form.get("username","")
    args["status"] = request.form.get("status","")
    args["channel_name"] = request.form.get("channel_name", "")
    args["start_datetime"] = request.form.get("start_datetime",(datetime.now() - timedelta(hours=1)).strftime('%Y-%m-%d %H'))
    args["end_datetime"] = request.form.get("end_datetime",(datetime.now()).strftime('%Y-%m-%d %H'))
    if not args["username"] and not args["channel_name"] and not args["url"]:
         return 'must enter username or channle_name or url'
    res = find_urls_for_csv(args)
    csv_name = ['query']
    if args["username"]:
        csv_name.append(args["username"])
    if args["url"]:
        csv_name.append(args["url"])
    app.logger.info("query_to_csv: %s" % args["username"])
    csv_headers = ['username', 'channel_name', 'url', 'status', 'is_dir', 'action', 'type', 'created_time', 'finish_time']
    csv_detail = []
    csv_detail.append(','.join(csv_headers))
    for info in res:
        created_time = info.get('created_time','')
        finish_time = info.get('finish_time','')
        if created_time:
            created_time = created_time.strftime('%Y-%m-%d %H:%M:%D')
        if finish_time:
            finish_time = finish_time.strftime('%Y-%m-%d %H:%M:%D')
        _info = [info.get('username',''),info.get('channel_name',''),info.get('url',''),info.get('status',''),str(info.get('isdir','')),info.get('action',''),info.get('type',''),created_time,finish_time]
        csv_detail.append(','.join(_info))
    sio=io.StringIO()
    sio.write('\n'.join(csv_detail))
    res = make_response(sio.getvalue())
    res.headers['Content-Type'] = 'text/csv'
    res.headers['Content-Disposition'] = 'attachment;filename="%s.csv"'%('_'.join(csv_name))
    return res
    

@app.route("/device/<dev_id>", methods=['GET','POST'])
def find_devs(dev_id):
    db_devs = get_devs_by_id(dev_id)
    devs = list(db_devs.get("devices").values())
    devs.sort(reverse=True, key=lambda  x:x.get('code'))
    devs.sort(reverse=True, key=lambda  x:x.get('firstLayer'))
    return render_template('url_devices.html', devs=devs,unprocess=db_devs.get("unprocess"),count=len(devs))


@app.route("/device_cert_task/<dev_id>", methods=['GET','POST'])
def find_devs_cert_task(dev_id):
    success, failed, unprocess, all_len = get_devs_cert_task(dev_id)
    failed.sort(reverse=True, key=lambda  x:x.get('type'))
    return render_template('cert_devices.html', success_devs=success, failed_devs=failed, unprocess=unprocess,count=all_len)

@app.route("/device_cert_task_res/<task_id>", methods=['GET','POST'])
def find_cert_task_dev_res(task_id):

    success, failed, unprocess, all_len = get_devs_cert_task_res(task_id)
    failed.sort(reverse=True, key=lambda  x:x.get('type'))
    return render_template('cert_devices_res.html', success_devs=success, failed_devs=failed, unprocess=unprocess,count=all_len)

@app.route("/device_cert_query_task/<dev_id>", methods=['GET','POST'])
def find_devs_query_cert_task(dev_id):
    success, failed, unprocess, all_len = get_devs_cert_query_task(dev_id)
    failed.sort(reverse=True, key=lambda  x:x.get('type'))
    return render_template('cert_query_devices.html', success_devs=success, failed_devs=failed, unprocess=unprocess,count=all_len)

@app.route("/device_cert_query_task_res/<task_id>", methods=['GET','POST'])
def device_cert_query_task_res(task_id):
    success, failed, unprocess, all_len = get_devs_cert_query_task_res(task_id)
    failed.sort(reverse=True, key=lambda  x:x.get('type'))
    return render_template('cert_query_devices_res.html', success_devs=success, failed_devs=failed, unprocess=unprocess,count=all_len)

@app.route("/device_cert_query_task_detail/<task_id>", methods=['GET','POST'])
def find_cert_task_dev_detail(task_id):
    success, failed, unprocess, all_len = get_devs_cert_query_task_detail(task_id)
    failed.sort(reverse=True, key=lambda  x:x.get('type'))
    return render_template('cert_query_devices_detail.html', success_devs=success, failed_devs=failed, unprocess=unprocess,count=all_len)

@app.route("/device_transfer_cert_task/<dev_id>", methods=['GET','POST'])
def find_devs_transfer_cert_task(dev_id):
    success, failed, unprocess, all_len = get_devs_transfer_cert_task(dev_id)
    failed.sort(reverse=True, key=lambda  x:x.get('type'))
    return render_template('transfer_cert_devices.html', success_devs=success, failed_devs=failed, unprocess=unprocess,count=all_len)

@app.route("/device_transfer_cert_task_res/<task_id>", methods=['GET','POST'])
def find_devs_transfer_cert_task_res(task_id):
    success_strs, failed_certs, unprocess, all_len , dic_res, all_certs = get_devs_transfer_cert_task_res(task_id)
    return render_template('transfer_cert_devices_res.html',success_strs=success_strs, failed_certs=failed_certs, unprocess=unprocess,count=all_len,dic_res=dic_res, all_certs=all_certs)

@app.route("/device_transfer_cert_task_detail/<task_id>", methods=['GET','POST'])
def find_devs_transfer_cert_task_dev_detail(task_id):
    success, failed, unprocess, all_len = get_devs_transfer_cert_task_detail(task_id)
    failed.sort(reverse=True, key=lambda  x:x.get('type'))
    return render_template('transfer_cert_devices_detail.html', success_devs=success, failed_devs=failed, unprocess=unprocess,count=all_len)


@app.route("/device_new/<_id>", methods=['GET','POST'])
def find_devs_new(_id):
    dev_id = get_url_by_id(_id)
    db_devs = get_devs_by_id(dev_id)
    devs = list(db_devs.get("devices").values())
    devs.sort(reverse=True, key=lambda  x:x.get('code'))
    devs.sort(reverse=True, key=lambda  x:x.get('firstLayer'))
    return render_template('url_devices.html', devs=devs,unprocess=db_devs.get("unprocess"),count=len(devs))

@app.route("/device_custom/<dev_id>", methods=['GET','POST'])
def find_devs_custom(dev_id):
    db_devs = get_devs_custom_by_id(dev_id)
    devs = list(db_devs.get("devices").values())
    num_all, num_204, num_success, num_failed, num_error = parse_dev_custom_result(devs)
    devs.sort(reverse=True, key=lambda  x:x.get('code'))
    devs.sort(reverse=True, key=lambda  x:x.get('firstLayer'))

    return render_template('url_devices_custom.html', devs=devs, num_all=num_all, num_204=num_204, num_success=num_success,
                           num_failed=num_failed, num_error=num_error)


@app.route("/deviceUrl", methods=['GET','POST'])
def find_refresh_dev():
    """
     点击界面上的刷新详细，出现的界面信息
    接口接收后台传过来的两个参数 url._id(url　collection 中的 _id)   url.dev_id(url collection中的dev_id )
    根据这两个参数  查找到设备的总数   没有处理的设备数
    列表中的内容  根据url._id  查找refresh_result中的内容  即表中的session_id
    :return:  跳转到refresh_result.html
    """

    # 此处接收url._id  此处有bug  按理应该是用_id接收对应的参数，通过前台观察发现传过来的参数为url

    url_id = request.args.get('url', '')
    dev_id = request.args.get('dev_id', '')

    #app.logger.info("接收url中_id: %s" % url_id)
    #app.logger.info("接收dev_id")
    #app.logger.info(dev_id)
    #设备信息
    db_devs = get_devs_by_id(dev_id)
    devs = list(db_devs.get("devices").values())
    devices_dict = db_devs.get('devices')
    app.logger.debug("test devices_dict:%s" % devices_dict)
    #hpcc设备的总数
    try:
        try:
            countAll = len([i for i in devs if i['type'] == 'HPCC' and i['code'] != 204 ])
        except KeyError:
            countAll = len([i for i in devs if i['code'] != 204 ])
    except KeyError:
        countAll = len(devs)

    #app.logger.info("设备信息")
    #app.logger.info(devs)

    # 根据url_id 即refresh_result中的session_id  查找相应的内容
    refresh_results = get_refresh_result_by_sessinId(url_id)
    # app.logger.debug("refresh_result:%s" % refresh_results)
    #refresh_results = get_refresh_result_by_sessinId("552f25c72b8a68da7a670667")
    count_temp = 0
    refresh_result = []
    for dev in refresh_results:
        for dev_value in devs:
            if dev['host']==dev_value['host']:
                dev['name']=dev_value['name']
                dev['time']=dev['time'].strftime("%Y-%m-%d %H:%M:%S")#time.strftime("%Y-%m-%d %H:%M:%S",dev['time']) 
                break
        refresh_result.append(dev)
        if dev.get('result') != '0':
            count_temp += 1
    refresh_result = sorted(refresh_result, key=lambda value: value.get('result'), reverse=True)
    #app.logger.info("列表中的内容  已赋值完毕")
    # refresh_results = [{'name':'ads','status':"pro",'result':'200', \
    # 'result_gzip':'220', 'host':'10.20.20.20', 'firstlayer':'true'}]


    # 计算设备总数   未完成设备数
    result = {'count':countAll, 'unprocess': countAll - count_temp}
    # 跳转到相应的前台界面
    return render_template('refresh_result.html', refresh_results=refresh_result, result=result)


#hpf
@app.route("/retrynum/<u_id>", methods=['GET','POST'])
def find_h_retrynum(u_id):
    devs= get_retry_re_id(u_id)
    #devs = db_devs.get("devices").values()
    devs.sort(reverse=True, key=lambda  x:x.get('code'))
    devs.sort(reverse=True, key=lambda  x:x.get('firstLayer'))
    return render_template('url_h_retry.html', devs=devs)

@app.route("/retryDevice/<dev_id>", methods=['GET', 'POST'])
def find_retryDevice(dev_id):
    app.logger.debug("kkkkk")
    db_devs = get_retryDevice_by_id(dev_id)
    devs = db_devs.get("devices")
    devs.sort(reverse=True, key=lambda  x:x.get('code'))
    devs.sort(reverse=True, key=lambda  x:x.get('firstLayer'))
    return render_template('url_devices.html', devs=devs,unprocess=0,count=len(devs))

@app.route("/cert/retryBranchDevice/<retry_branch_id>", methods=['GET', 'POST'])
def find_retry_branch_device(retry_branch_id):
    app.logger.debug("find_retry_branch_devices retry_branch_id:%s" % retry_branch_id)
    db_devs = get_retry_dev_bran_by_id(retry_branch_id)
    app.logger.debug("db_devs:%s" % db_devs)
    for k,dev in list(db_devs.items()):
        for m in dev:
            app.logger.debug("m  is %s"%m)
    #count, unprocess = statistic_banch_code(db_devs)
    #db_devs.sort(reverse=True, key=lambda x:x.get('branch_code'))
    #db_devs.sort(reverse=True, key=lambda x:x.get('firstLayer'))
    return render_template('retry_branch_devices.html', devs=db_devs)

@app.route("/retryBranchDevice/<retry_branch_id>", methods=['GET', 'POST'])
def find_retry_branch_devices(retry_branch_id):
    app.logger.debug("find_retry_branch_devices retry_branch_id:%s" % retry_branch_id)
    db_devs = get_retry_dev_branch_by_id(retry_branch_id)
    app.logger.debug("db_devs:%s" % db_devs)
    count, unprocess = statistic_banch_code(db_devs)
    db_devs.sort(reverse=True, key=lambda x:x.get('branch_code'))
    db_devs.sort(reverse=True, key=lambda x:x.get('firstLayer'))
    return render_template('retry_branch_devices.html', devs=db_devs, unprocess=unprocess, count=count)


@app.route("/retry/<dev_id>", methods=['GET','POST'])
def retry(dev_id):
    message = retry_api(dev_id)
    return render_template('retry.html', message=message)


@app.route('/user_role', methods=['GET', 'POST'])
@admin_permission.require(http_exception=401)
def user_config():
    users = get_user_list()
    return render_template('user_role.html',users=users)

@app.route('/grant_role', methods=['GET','POST'])
@admin_permission.require(http_exception=401)
def grant_role():
    user = User(request.form.get("username"),request.form.get("role"))
    if user.account != "":
        add_user(user)
    return user_config()

@app.route('/del_role/<account>', methods=['GET','POST'])
@admin_permission.require(http_exception=401)
def del_role(account):
    del_user(account)
    return user_config()

@app.route('/rewrite', methods=['GET', 'POST'])
@all_permission.require(http_exception=401)
def rewrite():
    args = {"totalpage":0,"curpage":int(request.form.get("curpage",0)),"CHANNEL_NAME":request.form.get('CHANNEL_NAME', ''),"REWRITE_NAME":request.form.get('REWRITE_NAME', '')}
    rewrite_list = get_rewrite_list(args)
    return render_template('rewrite.html',rewrite_list=rewrite_list,args=args)

@app.route("/add_rewrite", methods=['GET', 'POST'])
@all_permission.require(http_exception=401)
def add_rewrite():
    CHANNEL_NAME = request.form.get('channel_name', '')
    REWRITE_NAME = request.form.get('rewrite_name', '')
    if CHANNEL_NAME != "" and REWRITE_NAME != "":
        add_rewrite_data(CHANNEL_NAME,REWRITE_NAME)
    return rewrite()

@app.route("/del_rewrite", methods=['GET','POST'])
@all_permission.require(http_exception=401)
def del_rewrite():
    CHANNEL_NAME = request.args.get('channel_name', '')
    REWRITE_NAME = request.args.get('rewrite_name', '')
    del_rewrite_data(CHANNEL_NAME,REWRITE_NAME)
    return rewrite()

@app.route('/regex1', methods=['GET', 'POST'])
@all_permission.require(http_exception=401)
def get_regex():
    regex_list = get_regex_list()
    return render_template('regex.html',regex_list=regex_list)


@app.route('/regex', methods=['GET', 'POST'])
@all_permission.require(http_exception=401)
def get_regex_h():
    regex_list = get_regex_list_h()
    return render_template('regex.html',regex_list=regex_list)

@app.route("/add_regex", methods=['GET','POST'])
@all_permission.require(http_exception=401)
def add_regexConfig():
    username = request.form.get('username', '')
    isdir = (request.form.get('type', '') == "DIR")
    regex = request.form.get('regex', '')
    append = request.form.get('append', '')
    ignore = request.form.get('ignore', '')
    user_email = request.form.get('user_email', '')
    if username != "" and regex != "":
        if ignore == "":
            ignore = "no ignore"
        add_regex_data(username,isdir,regex,append,ignore, user_email=user_email)
    return get_regex()

@app.route("/add_regexh", methods=['GET','POST'])
@all_permission.require(http_exception=401)
def add_regexConfig_h():
    username = request.form.get('username', '')
    domain = request.form.get('domain', '')
    isdir = (request.form.get('type', '') == "DIR")
    regex = request.form.get('regex', '')
    method = request.form.get('method', '')
    act = request.form.get('act', '')
    end = request.form.get('end', '')
    append = request.form.get('append', '')
    ignore = request.form.get('ignore', '')

    user_email = request.form.get('user_email', '')


    if domain != "" and regex != "" and username != "":
        add_regex_data_h(username,domain,isdir, regex,method,act, end,append,ignore,user_email)
    return get_regex_h()

@app.route("/del_regex/<username>/<regexConfigId>", methods=['GET'])
@all_permission.require(http_exception=401)
def del_regex(username,regexConfigId):
    user_email = request.args.get('user_email', '')
    del_regex_data(username,regexConfigId, user_email=user_email)
    return get_regex()

@app.route("/del_regexh/<username>/<regexConfigId>", methods=['GET'])
@all_permission.require(http_exception=401)
def del_regex_h(username,regexConfigId):

    user_email = request.args.get('user_email', '')
    del_regex_data_h(username,regexConfigId, user_email=user_email)
    return get_regex_h()

@app.route('/channelignore', methods=['GET', 'POST'])
@all_permission.require(http_exception=401)
def get_channelignore():
    channels = get_channelignore_list()
    return render_template('channelignore.html',channels=channels)

@app.route("/add_channelignore", methods=['GET','POST'])
@all_permission.require(http_exception=401)
def add_channelignore():
    CHANNEL_NAME = request.form.get('CHANNEL_NAME', '')
    if CHANNEL_NAME != "":
        add_channelignore_data(CHANNEL_NAME)
    return get_channelignore()


@app.route("/del_channelignore/<CHANNEL_CODE>", methods=['GET','POST'])
@all_permission.require(http_exception=401)
def del_channelignore(CHANNEL_CODE):
    del_channelignore_data(CHANNEL_CODE)
    return get_channelignore()

@app.route('/h_domainignore_html', methods=['GET', 'POST'])
@all_permission.require(http_exception=401)
def h_get_domain_ignore():
    channels = get_domain_ignore_list()
    return render_template('domain_ignore.html',channels=channels)

@app.route("/h_add_domainignore", methods=['GET','POST'])
@all_permission.require(http_exception=401)
def h_add_domain_ignore():
    createUser = session.get("user").account
    CHANNEL_NAME = request.form.get('CHANNEL_NAME', '')
    if CHANNEL_NAME != "":
        add_domain_lignore_data(CHANNEL_NAME,createUser)
    return h_get_domain_ignore()


@app.route("/h_del_domain_ignore/<CHANNEL_CODE>", methods=['GET','POST'])
@all_permission.require(http_exception=401)
def h_del_domain_ignore(CHANNEL_CODE):
    del_domain_ignore_data(CHANNEL_CODE)
    return h_get_domain_ignore()

@app.route('/h_dirandurl', methods=['GET', 'POST'])
@all_permission.require(http_exception=401)
def h_dirandurl():
    channels = get_dirandurl_list()
    return render_template('get_dirandurl.html',channels=channels)

@app.route("/h_add_dirandurl", methods=['GET','POST'])
@all_permission.require(http_exception=401)
def h_add_dirandurl():
    createUser = session.get("user").account
    CHANNEL_NAME = request.form.get('CHANNEL_NAME', '')
    if CHANNEL_NAME != "":
        add_dirandurl_data(CHANNEL_NAME,createUser)
    return h_dirandurl()


@app.route("/h_del_dirandurl/<CHANNEL_CODE>", methods=['GET','POST'])
@all_permission.require(http_exception=401)
def h_del_dirandurl(CHANNEL_CODE):
    del_dir_and_url_data(CHANNEL_CODE)
    return h_dirandurl()



@app.route('/overloads', methods=['GET', 'POST'])
@all_permission.require(http_exception=401)
def get_overloads_config():
    overloads = get_overloads_config_list()
    return render_template('overloads.html',overloads=overloads)

@app.route("/add_overloads_config", methods=['GET','POST'])
@all_permission.require(http_exception=401)
def add_overloads_config():
    username = request.form.get('username', '')
    max_url = request.form.get('max_url', '0')
    max_dir = request.form.get('max_dir', '0')
    max_preload = request.form.get('max_preload', '0')
    user_email = request.form.get('user_email', '')
    if username != "" and max_url != "" and max_dir != "" and max_preload != "":
        add_overloads_config_data(username, max_url, max_dir, max_preload, user_email)
    return get_overloads_config()


@app.route("/del_overloads_config/<username>", methods=['GET','POST'])
@all_permission.require(http_exception=401)
def del_overloads_config(username):
    user_email = request.args.get('user_email', '')
    del_overloads_config_data(username, user_email)
    return get_overloads_config()

@app.route('/keycustomer', methods=['GET', 'POST'])
@admin_permission.require(http_exception=401)
def get_keycustomer():
    args = {"USERNAME":request.form.get('key_customer', '')}
    keycustomer_list = get_keycustomer_list(args)
    return render_template('key_customer.html',keycustomer_list=keycustomer_list,args=args)

@app.route("/add_keycustomer", methods=['GET','POST'])
@admin_permission.require(http_exception=401)
def add_keycustomer():
    key_customer = request.form.get('key_customer', '')
    channel_code = request.form.get('channel_code', '')
    monitor_email = request.form.get('monitor_email', '')
    if key_customer != "" and monitor_email != "":
        add_keycustomer_data(key_customer, channel_code, monitor_email.split('\r\n'))
    return get_keycustomer()
@app.route("/update_keycustomer", methods=['GET','POST'])
@admin_permission.require(http_exception=401)
def update_keycustomer():
    request_data = json.loads(request.data)
    key_customer = request_data.get('key_customer', '')
    channel_code = request_data.get('channel_code', '')
    monitor_email = request_data.get('monitor_email', '')
    #app.logger.info('--------{}-----{}--------{}-----{}---'.format(request.values,request.data,request.args,request.content_type))
    #app.logger.info('-------------{}-----------------{}------------{}'.format(key_customer,channel_code,monitor_email))
    if key_customer != "" and monitor_email != "":
        add_keycustomer_data(key_customer, channel_code, monitor_email.split('\n'))
    return json.dumps({"status":"sucess","code":200})


@app.route("/del_keycustomer/<k_id>", methods=['GET','POST'])
@admin_permission.require(http_exception=401)
def del_keycustomer(k_id):
    del_keycustomer_data(k_id)
    return get_keycustomer()

@app.route('/timer', methods=['GET', 'POST'])
@admin_permission.require(http_exception=401)
def timer_tasks():
    timer_tasks = get_timer_tasks()
    return render_template('timer.html',timer_tasks=timer_tasks)

@app.route("/add_timer", methods=['GET','POST'])
@admin_permission.require(http_exception=401)
def add_timer_tasks():
    timer = {'username':request.form.get('username', ''),'run_time':[ int(request.form.get('hour',0)),int(request.form.get('minute', 0))],
                'urls':(request.form.get('urls','')).split('\n'),'dirs':(request.form.get('dirs', '')).split('\n'),"remote_addr" : "timer"}
    add_timer_tasks_data(timer)
    return timer_tasks()

@app.route("/del_timer/<username>/<run_time>", methods=['GET','POST'])
@admin_permission.require(http_exception=401)
def del_timer_tasks(username,run_time):
    run_time = [int(run_time[1:run_time.index(',')]) ,int(run_time[run_time.index(',')+1:-1])]
    del_timer_tasks_data(username,run_time)
    return timer_tasks()

@app.route("/internal/changePushByRCMS", methods=['POST','GET'])
def change_push_by_rcms():
    request_args = {}
    if request.method == 'POST':
        request_args = request.form
    elif request.method == 'GET':
        request_args = request.args
    data = dict((key, request_args.getlist(key) if len(request_args.getlist(key)) > 1 else request_args.getlist(key)[0]) for key in list(request_args.keys()))
    try:
        data = json.loads(list(data.keys())[0])
    except Exception:
        app.logger.debug("request not called by java")
        pass    
    channelIds = data.get('channelIds',[])
    customerIds = data.get('customerIds',[])
    app.logger.info("change info : %s, %s" % (channelIds,customerIds))
    if not channelIds and not customerIds:
        return json.dumps({'msg': 'parameters all empty','result': 'failure'})

    
    app.logger.info("###########begin %s %s##############"%(channelIds,customerIds))
    if channelIds:
        for c in channelIds:
            logger_test_redis(c, 'channel','before')
    if customerIds:
        for _c in customerIds:
            logger_test_redis(_c, 'customer', 'before')

    rcms_change_worker.get_new_info(channelIds,customerIds)

    if channelIds:
        for c in channelIds:
            logger_test_redis(c, 'channel', 'after')
    if customerIds:
        for _c in customerIds:
            logger_test_redis(_c, 'customer', 'after')
    app.logger.info("###########over %s %s##############"%(channelIds,customerIds))

    return json.dumps({'msg': 'ok','result': 'success'})


@app.route('/rewrite/rewrite_query', methods=['GET', 'POST'])
@all_permission.require(http_exception=401)
def rewrite_n_to_n():
    """
    according username  channel_name to search info
    :return: html
    """
    # get username
    username = request.form.get('USERNAME', '')
    # get channel name
    channel_name = request.form.get('CHANNEL_NAME', '')
    app.logger.debug("username1:%s, channel_name1:%s" % (username, channel_name))

    args = {"totalpage":0,"curpage":int(request.form.get("curpage",0)), "username":request.form.get('USERNAME', ''),\
            "channel_name":request.form.get('CHANNEL_NAME', '')}
    result_list = []
    # if username != '':
    # encode and loads   handle the ObjectId
    results = rewrite_query(username.strip(), channel_name.strip())
    app.logger.debug("rewrite_n_to_n results:%s" % results)
    results = JSONEncoder().encode(results)
    results = load_task(results)
    result_list = get_rewrite_list_new(results, args)
    app.logger.debug("result_list:%s" % result_list)

    return render_template('rewrite_new.html', result_list=result_list, args=args)


@app.route('/rewrite/update_rewrite_new', methods=['GET', 'POST'])
@all_permission.require(http_exception=401)
def update_rewrite_new():
    """
    get data from front of platform, contains data of form     username    channels
    :return: html
    """
    # get the username and channels
    username = request.form.get('username', '')

    channels = request.form.get('channels', '')
    user_email = request.form.get('user_email', '')

    app.logger.debug("update_rewrite_new username:%s, channels:%s" % (username, channels))
    if username != '' and channels != '':
        data = {}
        data['username'] =username
        data['channel_list'] = tools.strip_list(channels.split(','))
        data['user_email'] = user_email
        update_rewrite_no_id(data)
    return rewrite_n_to_n()


@app.route('/rewrite/delete_rewrite_new', methods=['GET', 'POST'])
@all_permission.require(http_exception=401)
def del_rewrite_new():
    """
    delete data from mongo, and update the redis
    the format of receive data
     [{"id":XXXX, "username":XXXX, "channel_list":[xxxx,xxxx,xxx,xxxx]},
      {"id":XXXX, "username":XXXX, "channel_list":[xxxx,xxxx,xxx,xxxx]}
      ]

    :return:{'msg':xxxx, 'result':xxxxxx}  json
    """
    id = request.args.get('id', '')
    user_email = request.args.get('user_email', '')
    # app.logger.debug("del_rewrite_new request.form:%s" % request.form)
    # app.logger.debug("del_rewrite_new id:%s" % id)
    app.logger.debug('del_rewrite_new request.args:%s' % request.args)


    if id:
        res = {}
        res['id'] = id
        app.logger.debug('app del_rewrite_new res:%s' % res)
        res['user_email'] = user_email
        delete_rewrite_id(res)
    return rewrite_n_to_n()


@app.route('/callback_email/query_callback_email', methods=['GET', 'POST'])
@all_permission.require(http_exception=401)
def query_callback_email():
    """

    :return: html
    """
    # get username
    username = request.form.get('USERNAME', '')
    # get channel name
    # channel_name = request.form.get('CHANNEL_NAME', '')
    app.logger.debug("query callback username:%s" % (username,))

    args = {"totalpage":0,"curpage":int(request.form.get("curpage",0)), "username":request.form.get('USERNAME', '')}
    result_list = []
    # if username != '':
    # encode and loads   handle the ObjectId
    results = callback_email_query(username.strip())
    app.logger.debug("query_callback :%s" % results)
    results = JSONEncoder().encode(results)
    results = load_task(results)
    result_list = get_rewrite_list_new(results, args)
    app.logger.debug("query _callback result_list:%s" % result_list)
    # totalpage
    args['page_list'], args['can_pre_page'], args['can_next_page'] = \
        tools.pager(args['totalpage'], args.get('curpage'))


    return render_template('callback_email_control.html', result_list=result_list, args=args)


@app.route('/callback_email/update_callback_email', methods=['GET', 'POST'])
@all_permission.require(http_exception=401)
def update_callback_email():
    """

    :return: html
    """
    # get the username
    username = request.form.get('username', '')

    user_email = request.form.get('user_email', '')

    app.logger.debug("update_callback_email username:%s" % (username, ))
    if username != '' :
        data = {}
        data['username'] =username
        data['user_email'] = user_email
        model_update_callback_email(data)
    return redirect('/callback_email/query_callback_email')


@app.route('/callback_email/delete_callback_email', methods=['GET', 'POST'])
@all_permission.require(http_exception=401)
def del_callback_email():
    """
    delete data from mongo, and update the redis
    the format of receive data
     [{"id":XXXX, "username":XXXX, "channel_list":[xxxx,xxxx,xxx,xxxx]},
      {"id":XXXX, "username":XXXX, "channel_list":[xxxx,xxxx,xxx,xxxx]}
      ]

    :return:{'msg':xxxx, 'result':xxxxxx}  json
    """
    id = request.args.get('id', '')
    username = request.args.get('username', '')
    # user_email = request.args.get('user_email', '')
    # app.logger.debug("del_rewrite_new request.form:%s" % request.form)
    # app.logger.debug("del_rewrite_new id:%s" % id)


    app.logger.debug('del_callback_email request.args:%s' % request.args)


    if id:
        res = {}
        res['id'] = id
        res['username'] = username
        app.logger.debug('app del_rewrite_new res:%s' % res)
        # res['user_email'] = user_email
        model_delete_callback_email(res)
    return redirect('/callback_email/query_callback_email')



@app.route('/query_device_link_hours_result', methods=['GET', 'POST'])
def query_device_link_hours_result():
    totalpage = 0
    args = {"totalpage": totalpage, "curpage": int(request.form.get("curpage", 0)),
     "name": request.form.get("name", ""), "ip": request.form.get("ip", ""),
            'time_start': request.form.get('time_start', datetime.strftime(datetime.now(), "%Y-%m-%d %H")),
            'time_end': request.form.get('time_end', datetime.strftime(datetime.now(), "%Y-%m-%d %H"))}

    app.logger.debug("args:%s" % args)
    # test
    # app.logger.debug("date:%s, type:%s" % (request.form.get('date'), type(request.form.get('date'))))
    # app.logger.debug('args.date:%s, type:%s' % (args.get('date'), type(args.get('date'))))
    devs_dict = find_link_device_hours_result(args)
    # args["totalpage"] = devs_dict.get("totalpage")
    app.logger.debug("args['totalpage']:%s" % args['totalpage'])
    return render_template('device_link.html', devs=devs_dict, args=args)

@app.route('/query_device_link_detail', methods=['GET', 'POST'])
def query_device_link_detail():
    """
    according time and ip
    :return: the device detail info of link detection
    """
    # end_time = request.args.get('end_time', None)
    start_time = request.args.get('start_time', None)
    end_time = request.args.get('end_time', None)
    ip = request.args.get('ip', None)
    app.logger.debug("start_time:%s, end_time: %s, ip:%s" % (start_time, end_time, ip))
    devs = get_device_link_detail(start_time, end_time, ip)
    app.logger.debug("query_device_link_detail devs length:%s" % len(devs))
    return render_template('device_link_detail.html', devs=devs)


@app.route('/failed_dev_map_show', methods=['GET', 'POST'])
def map_show():
    """

    :return: map display home page
    """
    return render_template('failed_dev_map_show.html')


@app.route('/province_failed_dev_number', methods=['GET', 'POST'])
def map_show_failed_dev_number():
    """
    according time, get data from mongo (device_link_hours_result)
    :return:
    """
    app.logger.debug('get province data')
    return get_hour_link_detect_result()


@app.route('/province_failed_dev_number_update', methods=['GET', 'POST'])
def map_show_failed_dev_number_update():
    """
    update data fo map
    :return:
    """
    isp_list = request.args.get('isp_list', '')
    app.logger.debug('isp_list:%s' % isp_list)
    return get_hour_link_detect_result(isp_list=isp_list, flag=2)


@app.route('/province_failed_dev_detail', methods=['GET', 'POST'])
def map_show_failed_province_detail():
    """
    get the detail of failed dev in city which get from front end
    :param city: the name of city
    :return:
    """
    city = request.args.get('city', '')
    isp_list = request.args.get('isp_list', [])
    app.logger.debug(' province_failed_dev_detail city:%s, isp_list:%s, type isp_list:%s' % (city, isp_list, type(isp_list)))
    result_detail = get_hour_link_detect_result_province(city, isp_list)
    return render_template('failed_dev_map_province_detail.html', devs=result_detail)


@app.route('/subcenter_info', methods=['GET', 'POST'])
def query_subcenter_info():
    totalpage = 0
    args = {"totalpage":totalpage,"curpage":int(request.form.get("curpage",0)),
              "name": request.form.get("name", ""), 'ip': request.form.get('ip', "")}
    subcenter_info = get_subcenter_info(args)

    return render_template('subcenter_info.html', devs=subcenter_info, args=args)


def load_task(data):
    """
    analysis the data use json
    :param data:
    :return:
    """
    try:
        return json.loads(data)
    except Exception:
        app.logger.warn(data, exc_info=sys.exc_info())


def logger_test_redis(_id, _type, step):
    try:
        if _type == 'customer':
            _id = 'c_by_%s' %(_id)
            app.logger.debug('############%s %s###############'%(_id, step))
            app.logger.debug(channels_cache.hgetall(_id))
            app.logger.debug('############%s %s over##########'%(_id, step))
        elif _type == 'channel':
            _id = 'd_by_%s' %(_id)
            app.logger.debug('############%s %s###############'%(_id, step))
            app.logger.debug(device_cache.hgetall(_id))
            app.logger.debug('############%s %s over##########'%(_id, step))
    except Exception:
        app.logger.error('logger_test_redis error is %s' %(e))


class JSONEncoder(json.JSONEncoder):
    """
    solve ObjectId('57515b0a2b8a681de5b0612b') is not JSON serializable
    """
    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        return json.JSONEncoder.default(self, o)

@app.route('/monitor/device', methods=['GET', 'POST'])
def monitor_device_info():
    '''
    设备任务情况
    '''
    hostname = request.form.get('hostname', '')
    page = int(request.form.get('page', 0))
    if page > 0:
        hostname = ''
    search_date_from = request.form.get("datefrom",datetime.strftime(datetime.now(),"%m/%d/%Y"))
 
    search_date_to = request.form.get("dateto",datetime.strftime(datetime.now(),"%m/%d/%Y"))

    if not hostname:
        _info = get_device_monitor_page(page, search_date_from ,search_date_to)
    else:
        _info = {'total_page':0, 'devs':[get_device_monitor(hostname, search_date_from , search_date_to)]}
    app.logger.debug("hostname:%s" %hostname)
    app.logger.debug("_info:::%s" %_info)
    page_list, can_pre_page, can_next_page = tools.pager(_info['total_page'], page) 
    res = {}
    res['total_page'] = _info['total_page']
    res['devs'] = _info['devs']
    res['hostname'] = hostname
    res['page'] = page
    res['page_list'] = page_list 
    res['can_pre_page'] = can_pre_page
    res['can_next_page'] = can_next_page
    res['datefrom'] = search_date_from
    res['dateto'] = search_date_to
   # app.logger.debug(res['page_list'])
    app.logger.debug(res) 
    app.logger.debug("resresres")
    return render_template('monitor_device.html', res=res)


@app.route('/monitor/device/txt/<hostname>', methods=['GET'])
def monitor_device_txt(hostname):
    '''
    生成txt文件
    '''
    channel_name = request.args.get('channel_name', '')
    js_date_from = request.args.get('qdfrom')
    js_date_to = request.args.get('qdto')
    js_date_l_s = js_date_from.split('/')
    start_date  = '%s-%s-%s'%(js_date_l_s[2],js_date_l_s[0], js_date_l_s[1])
    start_d = datetime.strptime(start_date + ' ' +'00:00:00','%Y-%m-%d %H:%M:%S')
    js_date_t_s = js_date_to.split('/')
    end_date  = '%s-%s-%s'%(js_date_t_s[2],js_date_t_s[0], js_date_t_s[1])
    end_d = datetime.strptime(end_date + ' ' +'23:59:59','%Y-%m-%d %H:%M:%S')

    start_time = request.args.get('start_time')
    end_time = request.args.get('end_time')
    app.logger.debug("js_date_from:%s,js_date_to:%s" %(js_date_from,js_date_to))
    app.logger.debug("start_time:%s,end_time:%s" %(start_time,end_time))
    if start_time == None:
        res = get_device_failed_url(hostname, start_d , end_d, channel_name)
        txt_name = '%s_to_%s_%s' %(start_d.strftime('%Y-%m-%d_%H:%M:%S'), end_d.strftime('%Y-%m-%d_%H:%M:%S'), hostname)
    else:
        start_t = datetime.strptime(start_time.encode('utf-8'),'%Y-%m-%d %H:%M:%S')
        end_t = datetime.strptime(end_time.encode('utf-8'),'%Y-%m-%d %H:%M:%S')
        start_list = start_time.encode('utf-8').split(' ')
        start_time_d = start_list[0] + '_' +start_list[1]
        end_list = end_time.encode('utf-8').split(' ')
        end_time_d = end_list[0] + '_' +end_list[1]
        
        res = get_device_failed_url(hostname, start_t , end_t, channel_name)
        
        txt_name = '%s_to_%s_%s' %(start_time_d, end_time_d, hostname)
    if channel_name:
        txt_name = '%s_%s' %(txt_name,channel_name.replace('/','_'))
    app.logger.debug("txt_name:%s" %txt_name)
    app.logger.debug("res:%s" %res) 
    device_failed_url_to_txt(txt_name, res)
    return redirect('/%s.txt.gz'%(txt_name))


@app.route('/device/cron-gz/<hostname>', methods=['GET'])
def device_cron_gz(hostname):
    '''
    设备定时获取失败任务
    '''
    now = datetime.now()
    username = request.args.get('username', '')
    username_list = []
    if username:
        username_list = username.split(',')
    start_time = request.args.get('start_time','')
    end_time = request.args.get('end_time','')
    if not start_time or not end_time:
        return 'no start_time or no end_time'
    start_obj = datetime.strptime(start_time,'%Y-%m-%d_%H:%M')
    end_obj = datetime.strptime(end_time,'%Y-%m-%d_%H:%M')

    res = get_device_failed_url(hostname, start_obj, end_obj, username_list=username_list)
    write_list = make_failed_url_res(res)
    if not write_list:
        return 'no data'
    
   # app.logger.debug('----------write_list-----')
   # app.logger.debug(hostname)
   # app.logger.debug(start_obj)
   # app.logger.debug(end_obj)
   # app.logger.debug(username_list)
   # app.logger.debug(write_list)
   # app.logger.debug('----------write_list-----')

    gz_name = '%s_%s.txt.gz'%(hostname,now.strftime('%Y-%m-%d-%H-%M-%S'))
    c_io = io.StringIO()
    with gzip.GzipFile(gz_name,'wb',fileobj=c_io) as f:
        f.write('\n'.join(write_list))
    response = make_response(c_io.getvalue())
    c_io.close()
    response.headers['Content-Type'] = 'application/octet-stream'
    response.headers['Content-Disposition'] = 'attachment;filename="%s"'%(gz_name)
    return response


@app.route('/monitor/device/detail/<hostname>', methods=['GET', 'POST'])
def monitor_device_detail(hostname):

    page = int(request.form.get('page', 0))
    channel_name = request.form.get('channel_name', '')
    js_date_from = request.args.get('qdfrom')
    js_date_l_from = js_date_from.split('/')
    js_date_to = request.args.get('qdto')
    #app.logger.debug(js_date_to)
    js_date_l_to = js_date_to.split('/')
    search_date_from = '%s-%s-%s'%(js_date_l_from[2],js_date_l_from[0], js_date_l_from[1])
    search_date_to = '%s-%s-%s'%(js_date_l_to[2],js_date_l_to[0], js_date_l_to[1])

    search_start_time = datetime(int(js_date_l_from[2]),int(js_date_l_from[0]),int(js_date_l_from[1]),00,00,00)
    search_end_time = datetime(int(js_date_l_to[2]),int(js_date_l_to[0]),int(js_date_l_to[1]),23,59,59)
    app.logger.debug("search_start_time:%s,search_end_time:%s" %(search_start_time,search_end_time))    

    search_start_detail_time = request.form.get('datepickera_start', '')
    search_end_detail_time = request.form.get('datepickera_end', '')
    app.logger.debug("search_start_detail_time:%s,search_end_detail_time:%s" %(search_start_detail_time,search_end_detail_time))
    if search_start_detail_time:
        search_start_time =datetime.strptime(search_start_detail_time.encode('utf-8'),'%Y-%m-%d %H:%M:%S') 
    if search_end_detail_time:
        search_end_time =datetime.strptime(search_end_detail_time.encode('utf-8'),'%Y-%m-%d %H:%M:%S')
    app.logger.debug("search_start_time:%s" %type(search_start_time))   
 
    _details = get_device_failed_detail_page(page, search_start_time, search_end_time, hostname, channel_name)

    page_list, can_pre_page, can_next_page = tools.pager(_details['total_page'], page) 
    
    time_now = datetime.now()
    res = {}
    res['hostname'] = hostname
    res['js_date_from'] = js_date_from
    res['js_date_to'] = js_date_to
    res['start_time'] = search_start_time
    res['end_time'] = search_end_time
    res['can_txt'] = True
    res['channel_name'] = channel_name
    res['details'] = _details['details']
    res['total_page'] = _details['total_page']
    res['page'] = page
    res['page_list'] = page_list 
    res['can_pre_page'] = can_pre_page
    res['can_next_page'] = can_next_page
    if len(res['details']) <= 0:
        res['can_txt'] = False
    return render_template('monitor_device_detail.html', res=res)


@app.route('/monitor/receiver', methods=['GET'])
def monitor_receiver():
    '''
    监控接收任务数量情况
    '''
    now = datetime.now() - timedelta(seconds=1)
    now_s = now.strftime('%H:%M:%S')
    #初始化 接收端数据
    servers = eval(config.get('monitor', 'receiver_group'))      
    init_data = []
    for info in servers:
        _id = info[1][0]
        init_data.append(init_monitor_data(now_s,_id,'receiver'))
    #初始化 refresh worker 数据
    refresh_data = []
    refresh_group = eval(config.get('monitor', 'refresh_group'))      
    for _g in refresh_group:
        _gid = _g[0]
        _g_members = _g[1]
        _refresh_data = []
        for m in _g_members:
            #_g_data = {'name': m, 'type': 'line', 'data': [random.randint(1,100) for i in range(10)]}
            _g_data = {'name': m, 'type': 'line', 'data': init_monitor_data(now_s,m,'refresh')}
            _refresh_data.append(_g_data)
        refresh_data.append(_refresh_data)

    
    #app.logger.debug('-------------refresh_data----------------')
    #app.logger.debug(refresh_data)
    ts = int(time.time()) * 1000
    #app.logger.debug(ts)

    res = {'servers':servers, 'init_data': init_data, 'servers_count': len(servers), 'refresh_data': refresh_data, 'refresh_group_count':len(refresh_group), 'refresh_group':refresh_group, 'ts':ts}
    return render_template('monitor_receiver.html', res=res)


@app.route('/monitor/receiver/result', methods=[ 'POST'])
def monitor_receiver_result():
    '''
    最新接收计数
    '''
   
    #_json_str = request.get_data()

    #app.logger.debug(_json_str)

    now = datetime.now() - timedelta(seconds=1)
    _date = now.strftime('%H:%M:%S')

   # _obj = json.loads(_json_str)
   # _date = _obj['date'] 

    res = {'receiver':[], 'refresh':[], 'ts':int(time.time())*1000}
    servers = eval(config.get('monitor', 'receiver_group'))      
    #初始化 receiver数据
    for info in servers:
        _id = info[1][0]
        values = init_monitor_data(_date, _id, 'receiver', 1)
        res['receiver'].append(values[0])
        #res['receiver'].append(random.randint(1,100))

    #初始化 refresh数据
    refresh_group = eval(config.get('monitor', 'refresh_group'))      
    for r_info in refresh_group:
        _m = r_info[1]
        r_values = []
        for m_id in _m:
            _v = init_monitor_data(_date, m_id, 'refresh', 1)
            r_values.append(_v[0])
            #r_values.append(random.randint(1,100))

        res['refresh'].append(r_values)        
        
    #app.logger.debug('monitor_receiver_result %s'%(res))

    return json.dumps(res)


@app.template_filter('datetime_print')
def datetime_print(s):
    return s.strftime('%Y-%m-%d %H:%M:%S')


@app.route('/refresh/high_priority', methods=['GET', 'POST'])
def refresh_high_priority():
    '''
    高优先级 频道配置
    '''
    page = int(request.form.get('page', 0))
    channel_name = request.form.get('channel_name', '')
    username = request.form.get('username', '')

    _info = get_all_refresh_high_priority_page(username,channel_name, page)


    page_list, can_pre_page, can_next_page = tools.pager(_info['total_page'], page) 
    res = {}
    res['page'] = page
    res['total_page'] = _info['total_page']
    res['page_list'] = page_list
    res['can_pre_page'] = can_pre_page
    res['can_next_page'] = can_next_page
    res['details'] = _info['details']
    res['username'] = username
    res['channel_name'] = channel_name

    #app.logger.debug('_info %s' %(res['details']))

    return render_template('refresh_high_priority.html', res=res)


@app.route('/refresh/high_priority/add/detail', methods=['GET', 'POST'])
def refresh_high_priority_add_detail():
    '''
    添加配置 页
    '''
    username = request.form.get('username', '')
    unopen = []
    if username:
        unopen = get_refresh_high_priority_unopen(username)
    res = {} 
    res['channels'] = unopen
    res['username'] = username
    return render_template('add_high_priority.html', args=res)
    

@app.route('/refresh/high_priority/add', methods=['POST'])
def refresh_high_priority_add():
    '''
    添加配置执行
    '''
    reqe_channels = request.form.get('channels', '')
    start_time = request.form.get('start_time', '')
    end_time = request.form.get('end_time', '')
    if not start_time or not end_time or not reqe_channels:
        return 'Please enter start time and end time and channel'
    start_date, start_t = start_time.split(' ')
    start_month, start_day, start_year = start_date.split('/')
    start_h, start_m = start_t.split(':')
    start_obj = datetime(int(start_year), int(start_month), int(start_day), int(start_h), int(start_m),0)

    end_date, end_t = end_time.split(' ')
    end_month, end_day, end_year = end_date.split('/')
    end_h, end_m = end_t.split(':')
    end_obj = datetime(int(end_year), int(end_month), int(end_day), int(end_h), int(end_m),0)

    if start_obj >= end_obj:
        return 'Please check start time and end time'

    db_map = []
    for req_channel in reqe_channels[:-1].split(";"):
        db_map.append(
                  {"username":  request.form.get('username', ''),
                   "channel_name": req_channel.split("$")[1],
                   "channel_code":  req_channel.split("$")[0],
                   "start_time": start_obj,
                   "end_time": end_obj,
                   "created_time": datetime.now(),
                  })

    add_refresh_high_priority(db_map)
    return redirect('/refresh/high_priority') 

@app.route('/refresh/high_priority/del/<channel_code>', methods=['GET'])
def refresh_high_priority_del(channel_code):
    '''
    删除高优先级配置
    '''
    del_refresh_high_priority(channel_code)
    return redirect('/refresh/high_priority') 


@app.route('/email_management', methods=['GET', 'POST'])
#@admin_permission.require(http_exception=401)
def email_management():
    """

    :return:
    """
    _type = request.form.get('type_name', '').lower().strip()
    email_name = request.form.get('email_name', '').strip()
    page = int(request.form.get('page', 0))
    app.logger.debug("email_management _type:%s, email_name:%s, page:%s" % (_type, email_name, page))

    query = {}
    if _type:
        query['type'] = _type
    if email_name:
        query['email_name'] = email_name
    query['page'] = page

    management_list = get_email_management_list(query)
    page_list, can_pre_page, can_next_page = tools.pager(query['total_page'], page)
    res = {}
    res['total_page'] = query['total_page']
    # res['devs'] = _info['devs']
    # res['hostname'] = hostname
    res['page'] = page
    res['page_list'] = page_list
    res['can_pre_page'] = can_pre_page
    res['can_next_page'] = can_next_page
    # res['date'] = js_date
    return render_template('email_management.html', management_list=management_list, args=query, res=res)


@app.route('/email_management_add', methods=['GET', 'POST'])
#@admin_permission.require(http_exception=401)
def email_management_add():

    _type = request.form.get('type', '').lower()
    email_address = request.form.get('email_address', '')
    devices = request.form.get('devices', '')
    threshold = request.form.get('threshold', '')
    #app.logger.debug(_type)
    #app.logger.debug(email_address)
    if not _type or not email_address or not devices or not threshold:
        return email_management()
    management_list = add_email_management(_type, email_address, devices, threshold)
    return redirect('/email_management')


@app.route('/email_management_del/<_id>', methods=['GET', 'POST'])
#@admin_permission.require(http_exception=401)
def email_management_del(_id):
    user_email = request.args.get('user_email')
    # app.logger.debug('test_rubin email_management user_email:%s' % user_email)
    del_email_management(_id, user_email)
    return redirect('/email_management')

@app.route('/email_management_add_1', methods=['GET', 'POST'])
def email_amangement_add_1():
    """

    :return:
    """
    result = {}
    # result['failed_type'] = 'failed_device'
    result['failed_type'] = ''
    result['email_address'] = ''
    result['devices'] = ''
    # failed threshold
    result['threshold'] = '6'
    # Transmit frequency
    result['rate'] = '1'
    result['email_address_end'] = ''
    return render_template('email_management_add.html', result=result)

@app.route('/email_management_add_dev', methods=['GET', 'POST'])
def email_management_add_dev():
    """

    :return:
    """
    # channels = model.get_all_channels()
    # channel_name = request.form.get('channel', '')
    # dev_name = request.form.get('dev_name', '')

    # get from email_management_add  request
    failed_type = request.args.get('failed_type', '')
    email_address = request.args.get('email_address', '')
    devices = request.args.get('devices', '')
    threshold = request.args.get('threshold', '')
    rate = request.args.get('rate', '')
    result = {}
    result['failed_type'] = failed_type
    result['email_address'] = email_address
    result['devices'] = devices
    result['threshold'] = threshold
    result['rate'] = rate
    app.logger.debug("result:%s" % result)

    args ={}
    args['channel_name'] = []
    args['dev_name'] = []
    app.logger.debug('print email_management_add_dev!!!!')
    return render_template('email_management_add_device.html', args=args, result=result)
    # if not channel_name and not dev_name:
    #     app.logger.debug("email_management_add_dev args:%s" % args)
    #     return render_template('email_management_add_device.html', args=args, result=result)
    # else:
    #     args["devs"] = get_devs_opened(args)
    #     app.logger.debug("email_management_add_dev args:%s" % args)
    #     return render_template('email_management_add_device.html', args=args, result=result)



@app.route('/email_management_channel_search', methods=['GET', 'POST'])
def email_management_channel_search():
    """

    :return:
    """
    channel_name = request.form.get('channel', '')
    dev_name = request.form.get('dev_name', '')
    args = {}
    args['channel_name'] = channel_name
    args['dev_name'] = dev_name
    result = request.args.get('result', '')
    app.logger.debug('result:%s' % result)
    if not channel_name and not dev_name:
        app.logger.debug("email_management_add_dev args:%s" % args)
        return render_template('email_management_add_device.html', args=args, result=result)
    else:
        args["devs"] = get_devs_opened(args)
        app.logger.debug("email_management_add_dev args:%s" % args)
        return render_template('email_management_add_device.html', args=args, result=result)


@app.route('/email_management_add_result', methods=['GET', 'POST'])
def email_management_add_result():
    """

    :return:
    """
    devs = request.form.get('devs', '')
    result = request.args.get('result', '')
    result = eval(result)
    app.logger.debug('email_management_add_result result:%s, type:%s' % (result, type(result)))
    devices = result['devices']
    if devices and devs:
        result['devices'] += ',' + devs
    elif devs:
        result['devices'] = devs
    app.logger.debug('result["devices"]:%s' % result['devices'])
    return render_template('email_management_add.html', result=result)


@app.route('/email_management_add_result_insert', methods=['GET', 'POST'])
def email_management_add_result_insert():
    """

    :return:
    """
    result = {}
    result['failed_type'] = request.form.get('failed_type', '')
    result['email_address'] = request.form.get('email_address', '')
    result['email_address_end'] = request.form.get('email_address_end', '')
    result['devices'] = request.form.get('devices', '')
    result['threshold'] = request.form.get('threshold', '')
    result['rate'] = request.form.get('rate', '')
    result['_id'] = request.form.get('_id', '')
    result['user_email'] = request.form.get('user_email', '')

    app.logger.debug("email_management_add_result_insert request.form:%s" % request.form)
    if not result['email_address']:
        return redirect('/email_management')
    else:
        result['email_address'] = result['email_address'].split('\n')
        result['email_address_end'] = result['email_address_end'].split('\n')
    if result['failed_type'] != 'custom_email':
        if not result['devices']:
            return redirect('/email_management')
        else:
            result['devices'] = result['devices'].split('\n')

        if not result['threshold']:
            return redirect('/email_management')
        else:
            result['threshold'] = int(result['threshold'])
        if not result['rate']:
            return redirect('/email_management')
        else:
            result['rate'] = int(result['rate'])
        # rearrange list
        result['devices'] = strip_list_remove_blank(result['devices'])
    else:
        result['email_address_end'] = strip_list_remove_blank(result['email_address_end'])
        result['custom_name'] = request.form.get('custom_name')
        if not result['custom_name']:
            return redirect('/email_management')

    # rearrange list
    result['email_address'] = strip_list_remove_blank(result['email_address'])

    insert_email_management(result)
    app.logger.debug(result)
    app.logger.debug(type(result))
    return redirect('/email_management')


@app.route('/email_management_alter', methods=['GET', 'POST'])
def email_managemnet_alter():
    """
    click modify button
    :param body_alter:
    :return:information modification interface
    """
    result = {}
    result['failed_type'] = request.args.get('failed_type', '')
    result['email_address'] = request.args.get('email_address', '')
    result['email_address_end'] = request.args.get('email_address_end', '')
    result['devices'] = request.args.get('devices', '')
    result['threshold'] = request.args.get('threshold', '')
    result['rate'] = request.args.get('rate', '')
    result['_id'] = request.args.get('_id', '')
    result['custom_name'] = request.args.get('custom_name', '')
    app.logger.debug('type _id:%s' % type(result['_id']))
    app.logger.debug("result:%s" % result)

    return render_template('email_management_add.html', result=result)


@app.route('/operation_log_query', methods=['GET', 'POST'])
def operation_log_query():
    """

    Returns: query operation log

    """
    query = {}
    time_now = datetime.now()
    user_email = request.form.get('user_email', '')
    operation_type = request.form.get('operation_type', '')
    # small_operation_type = request.get('small_operation_type', '')
    time_start = request.form.get('time_start', datetime.strftime(time_now + timedelta(days=-1), "%Y-%m-%d %H"))
    time_end = request.form.get('time_end', datetime.strftime(time_now,"%Y-%m-%d %H"))
    content = request.form.get('content', '')
    page = int(request.form.get('curpage', 0))
    query['user'] = user_email
    query['operation_type'] = operation_type
    query['time_start'] = time_start
    query['time_end'] = time_end
    query['content'] = content



    args = {}
    args['page'] = page
    args['time_start'] = time_start
    args['time_end'] = time_end
    args['user_email'] = user_email
    args['operation_type'] = operation_type
    args['content'] = content
    # app.logger.debug('test_rubin page:%s' % page)
    result = operation_log_list(args, query)

    args['page_list'], args['can_pre_page'], args['can_next_page'] = \
                            tools.pager(args['total_page'], page)

    return render_template('operation_log.html', result= result, args=args)



@app.route('/prefix/prefix_query', methods=['GET', 'POST'])
@all_permission.require(http_exception=401)
def prefix_query():
    """
    according username  channel_name to search info
    :return: html
    """
    # get username
    username = request.form.get('USERNAME', '')
    # get channel name
    channel_original = request.form.get('CHANNEL_ORIGINAL', '')
    app.logger.debug("username1:%s, channel_orignal:%s" % (username, channel_original))

    args = {"totalpage":0,"curpage":int(request.form.get("curpage",0)), "username": request.form.get('USERNAME', ''),\
            "channel_original":request.form.get('CHANNEL_ORIGINAL', '')}
    result_list = []
    # if username != '':
    # encode and loads   handle the ObjectId
    # results = rewrite_query(username.strip(), channel_orignal.strip())
    results = rewrite_prefix_query(username.strip(), channel_original.strip())
    app.logger.debug("prefix_query results:%s" % results)
    results = JSONEncoder().encode(results)
    results = load_task(results)
    result_list = get_rewrite_list_new(results, args)
    app.logger.debug("result_list:%s" % result_list)

    return render_template('prefix_url_replace.html', result_list=result_list, args=args)

@app.route('/prefix/add_prefix', methods=['GET', 'POST'])
@all_permission.require(http_exception=401)
def add_prefix():
    """
    get data from front of platform, contains data of form     username    channels
    :return: html
    """
    # get the username and channels
    username = request.form.get('username', '')

    channel_original = request.form.get('channel_original', '')
    channels_after = request.form.get('channels_after', '')
    user_email = request.form.get('user_email', '')

    app.logger.debug("add_prefix username:%s, channel_original:%s, channels_after:%s" % (username,
                                channel_original, channels_after))
    if username != '' and channel_original != '' and channels_after:
        data = {}
        data['username'] =username
        data['channel_original'] = channel_original.strip()
        data['channels_after'] = tools.strip_list(channels_after.split(','))
        data['user_email'] = user_email
        # update_rewrite_no_id(data)
        update_prefix_data(data)
    return prefix_query()

@app.route('/prefix/delete_rewrite_prefix', methods=['GET', 'POST'])
@all_permission.require(http_exception=401)
def del_rewrite_prefix():
    """
    delete data from mongo, and update the redis
    the format of receive data
     [{"id":XXXX, "username":XXXX, "channel_list":[xxxx,xxxx,xxx,xxxx]},
      {"id":XXXX, "username":XXXX, "channel_list":[xxxx,xxxx,xxx,xxxx]}
      ]
    :return:{'msg':xxxx, 'result':xxxxxx}  json
    """
    id = request.args.get('id', '')
    user_email = request.args.get('user_email', '')
    # app.logger.debug("del_rewrite_new request.form:%s" % request.form)
    # app.logger.debug("del_rewrite_new id:%s" % id)
    # app.logger.debug('del_rewrite_new request.args:%s' % request.args)


    if id:
        res = {}
        res['id'] = id
        app.logger.debug('app del_rewrite_prefix res:%s' % res)
        res['user_email'] = user_email
        # delete_rewrite_id(res)
        delete_rewrite_prefix_id(res)
    return prefix_query()


@app.route('/physical/physical_del_channel_query', methods=['GET', 'POST'])
@all_permission.require(http_exception=401)
def physical_del_channel_query():
    """
    according username  channel_name to search info
    :return: html
    """
    # get username
    username = request.form.get('USERNAME', '')
    # get channel name
    physical_del_channel = request.form.get('physical_del_channel', '')
    page = int(request.form.get('curpage', 0))
    app.logger.debug("username1:%s, physical_del_channel:%s" % (username, physical_del_channel))

    args = {"total_page":0,"curpage":int(request.form.get("curpage",0)), "username": request.form.get('USERNAME', ''),\
            "physical_del_channel":request.form.get('physical_del_channel', '')}

    result_list = []

    results = physical_del_channel_qu(username.strip(), physical_del_channel.strip())
    app.logger.debug("physical_del_channel_query  results:%s" % results)
    results = JSONEncoder().encode(results)
    results = load_task(results)
    result_list = get_physical_del_channel_list(results, args)
    app.logger.debug("result_list:%s" % result_list)

    args['page_list'], args['can_pre_page'], args['can_next_page'] = \
                            tools.pager(args['total_page'], page)

    return render_template('physical_del_channel.html', result_list=result_list, args=args)


@app.route('/physical/add_physical_del_channel', methods=['GET', 'POST'])
@all_permission.require(http_exception=401)
def add_physical_del_channel():
    """
    get data from front of platform, contains data of form     username    channels
    :return: html
    """
    # get the username and channels
    username = request.form.get('username', '')

    physical_del_channels = request.form.get('physical_del_channels', '')

    app.logger.debug("add_physical_del_channel username:%s, physical_del_channels:%s" % (username, physical_del_channels))
    list_insert = []
    if username != '' and physical_del_channels != '':
        for physical_del_channel in physical_del_channels.split(','):
            data = {}
            data['username'] =username
            data['physical_del_channel'] = physical_del_channel.strip()
            if data['physical_del_channel']:
                list_insert.append(data)

            # update_rewrite_no_id(data)
        update_physical_del_channel_data(list_insert)
    return physical_del_channel_query()


@app.route('/physical/delete_physical_del_channel', methods=['GET', 'POST'])
@all_permission.require(http_exception=401)
def del_physical_del_channel():
    """
    delete data from mongo, and update the redis

    :return:
    """
    id = request.args.get('id', '')
    # user_email = request.args.get('user_email', '')

    if id:
        res = {}
        res['id'] = id
        app.logger.debug('app delete_physical_del_channel res:%s' % res)
        # res['user_email'] = user_email
        delete_physical_del_channel_id(res)
    return physical_del_channel_query()
@app.route("/subcenter_refresh_dev/<uid>", methods=['GET', 'POST'])
def subcenter_refresh_dev(uid):
    app.logger.debug("find_retry_branch_devices uid:%s" % uid)
    count, unprocess, db_devs = get_subcent_refresh_dev(uid)
    app.logger.debug("db_devs:%s" % db_devs)
    #count, unprocess = get_sub_refreh_result(uid)
    db_devs.sort(reverse=True, key=lambda x:(x.get('edge_host')))
    db_devs_dict={}
    for dev_o in db_devs:
        #dev_name = dev_o.pop('name')
        #db_devs_dict.setdefault(dev_name,[]).append(dev_o)
        dev_name = dev_o.pop('name')
        host = dev_o.pop('edge_host')
        #db_devs_dict.setdefault(dev_name,[]).append(dev_o)
        db_devs_dict.setdefault('%s/%s'%(dev_name,host), []).append(dev_o)
    # db_devs.sort(reverse=True, key=lambda x:x.get('firstLayer'))
    #app.logger.debug("db_devs  results:%s" % (db_devs))
    return render_template('subcent_refresh_dev.html', devs=db_devs_dict, unprocess=unprocess, count=count)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8090)
    # app.run(host='0.0.0.0', port=8099)
