#-*- coding:utf-8 -*-
from flask import Blueprint, render_template, request, redirect, url_for
from flask_principal import  Permission, RoleNeed
from . import preload_models as model
from datetime import datetime
import logging
from util import log_utils,tools
from .models import get_retry_dev_branch_by_id,statistic_banch_code
from core.config import config
from core  import rcmsapi
import cache.util_redis_api as redisutil
import simplejson as json
import urllib.request, urllib.parse, urllib.error
import sys
import sys,traceback
import re
import imp
imp.reload(sys)

# logger = logging.getLogger("preload")
# logger.setLevel(logging.DEBUG)
logger = log_utils.get_admin_Logger()
all_permission = Permission(RoleNeed('admin'), RoleNeed('operator'))
preload = Blueprint('preload', __name__,
                        template_folder='templates/preload', static_folder='static')

@preload.route('/preload_channels', methods=['GET', 'POST'])
@all_permission.require(http_exception=401)
def preload_channels(pop_mes=None):
    args = {"curpage":int(request.form.get("curpage", 0)),
            "channel_name":request.form.get("channel_name", ""), "username":request.form.get("username", "")}
    channels, totalpage = model.get_channels(args)
    page = int(request.form.get('curpage', 0))
    page_list, can_pre_page, can_next_page = tools.pager(int(totalpage), page)
    args["totalpage"] = totalpage
    args["curpage"] = page
    args["page_list"] = page_list
    args["can_pre_page"] = can_pre_page
    args["can_next_page"] = can_next_page
    if pop_mes!=None:
        if pop_mes.get('status')== False:
            args["already_config_channels"] = pop_mes.get('channels')
            args["already_config_status"] = 1
    return render_template('preload_channels.html', channels=channels, args=args)

@preload.route('/get_channels_by_user', methods=['GET', 'POST'])
@all_permission.require(http_exception=401)
def get_channels_by_user():
    users = model.get_users()
    args = {"username" : request.form.get('username', ''),"usertype":request.form.get('usertype', '')}
    if args.get("username"):
        args["channels"] = model.get_channels_unopened(args.get("username"),args.get("usertype"))
    return render_template('add_channel.html', users=users, args=args)

@preload.route('/add_preload_channel', methods=['GET', 'POST'])
@all_permission.require(http_exception=401)
def add_preload_channel():
    reqe_channels = request.form.get('channels', '')
    logger.debug("add_preload_channel request.form:%s" % request.form)
    reqe_device_type = request.form.get('device_type', '')
    channels = []
    for req_channel in reqe_channels[:-1].split(";"):
        channels.append({"username":  request.form.get('username', ''),
                    "channel_name": req_channel.split("$")[1],
                    "channel_code": req_channel.split("$")[0],
                    "type": request.form.get('type', 0),
                    "has_callback": 0,
                    "callback": {"url":'',"email":[]},
                    "is_live": request.form.get('is_live', 0),
                    "config_count": request.form.get('device_type', 500),
                    "created_time": datetime.now()})
    logger.debug("add_preload_channel channels: %s|| request.form.get('channels'): %s" % (channels, request.form.get('channels')))
    add_result = model.add_channel(channels, int(reqe_device_type))
    
    if int(reqe_device_type)==3:
        return get_devs_by_channel(add_result)
    else:
        return preload_channels(add_result)

@preload.route('/del_preload_channel', methods=['GET', 'POST'])
@all_permission.require(http_exception=401)
def del_channel_action():
    id = request.args.get('id', '')
    channel_name = request.args.get('channel_name', '')
    username = request.args.get('username', '')
    model.del_channel(id)
    # according channel_name, username, delete preload_config_device info
    model.del_all_devs(channel_name, username)
    return preload_channels()

@preload.route('/close_preload_channel/<id>', methods=['GET', 'POST'])
@all_permission.require(http_exception=401)
def close_channel_action(id):
    model.set_channel_status(id,1)
    return preload_channels()

@preload.route('/start_preload_channel/<id>', methods=['GET', 'POST'])
@all_permission.require(http_exception=401)
def start_preload_channel(id):
    model.set_channel_status(id,0)
    return preload_channels()

@preload.route('/config_preload_channel/<id>', methods=['GET', 'POST'])
@all_permission.require(http_exception=401)
def config_preload_channel(id):
    channel = model.get_channel_by_id(id)
    provinces = model.get_all_province()
    return render_template('config_channel.html', channel=channel,provinces=provinces)

@preload.route('/config_channel_action', methods=['GET', 'POST'])
@all_permission.require(http_exception=401)
def config_channel_action():
    callback_email = request.form.get("callback_email", '')
    region = request.form.getlist('region')
    email = [e for e in callback_email.split('\r\n') if e ]
    logger.debug("config_channel_action request.form: %s" % (request.form, ))
    args = {
            "_id":request.form.get("channel_id", 0), "type":int(request.form.get("type", 0)),
            "device_type":int(request.form.get("device_radio", 0)), "region":region,
            "config_count":request.form.get("config_count", 3.5), "has_callback":int(request.form.get("has_callback", 0)),
            "callback":{"url":request.form.get("callback_url", ''), "email":email},
            "avoid_period_s": request.form.get("avoid_period_s", ""), "avoid_period_e": request.form.get("avoid_period_e", ""),
            "avoid_extra_minutes": request.form.get("avoid_extra_minutes", 0) if request.form.get("avoid_extra_minutes") else 0,
            "parse_m3u8_f": True if request.form.get("parse_m3u8_f") else False,
            "parse_m3u8_nf": True if request.form.get("parse_m3u8_nf") else False,
            "first_layer_not_first": True if request.form.get("first_layer_not_first_h") == 'true' else False,
        }
    model.config_channel(args)
    if int(request.form.get("device_radio"))==3:
        return get_devs_by_channel_new(request.form.get("channel_realname"))
    else:
        return preload_channels()


@preload.route('/preload_devices', methods=['GET', 'POST'])
@all_permission.require(http_exception=401)
def preload_devices():
    args = {"curpage":int(request.form.get("curpage", 0)),
            "channel_name":request.form.get("channel_name", ""), "username":request.form.get("username", "")
            , "name":request.form.get("dev_name", "")}
    devs, totalpage = model.get_devices(args)
    args["totalpage"] = totalpage
    return render_template('preload_devices.html', devs=devs, args=args)


@preload.route('/preload_channel_devices', methods=['GET', 'POST'])
@all_permission.require(http_exception=401)
def preload_channel_devices():
    args = {"curpage": int(request.form.get("curpage", 0)),
            "channel_name": request.args.get("channel_name", "")
            , "name": request.form.get("dev_name", "")}
    logger.debug('preload_channel_devices args:%s' % args)
    devs, totalpage = model.get_devices(args)
    args["totalpage"] = totalpage
    return render_template('preload_channel_devices.html', devs=devs, args=args)


@preload.route('/dev_list_input', methods=['GET', 'POST'])
@all_permission.require(http_exception=401)
def dev_list_input():
    if request.method == 'POST':
        dev_list = [i.strip() for i in request.form.get('dev_list').split('\n') if i.strip()]
        # logger.debug('dev_list_input dev_list: %s' % (dev_list, ))
        channel = json.loads(request.form.get('channel'))
        if dev_list:
            s_ret = model.set_devices(channel, dev_list)
            if s_ret:
                return redirect(url_for('preload.preload_channel_devices', channel_name=channel.get('channel_name')))
    channel_name = request.args.get('channel_name')
    # logger.debug('dev_list_input channel_name: %s' % (channel_name, ))
    channel = model.get_devices_all(channel_name)

    # logger.debug('dev_list_input channel: %s' % (channel, ))
    return render_template('dev_list_input.html', channel=channel)


@preload.route('/get_devs_by_channel', methods=['GET', 'POST'])
@all_permission.require(http_exception=401)
def get_devs_by_channel(pop_mes=None):
    channels = model.get_all_channels()

    req_channel = request.form.get('channel', '')
    args = {}
    if req_channel:
        args = {"channel_code": req_channel.split("$")[0] , "channel_name" :req_channel.split("$")[1], "username" :req_channel.split("$")[2], "dev_name":request.form.get('dev_name', '')}
        args["devs"] = model.get_devs_unopened(args)
    if pop_mes!=None:
        if pop_mes.get('status')== False:
            args["already_config_channels"] = pop_mes.get('channels')
            args["already_config_status"] = 1 
    return render_template('add_device.html', channels=channels, args=args)


@preload.route('/get_devs_by_channel_new', methods=['GET', 'POST'])
@all_permission.require(http_exception=401)
def get_devs_by_channel_new(channel_realname=None):
    channels = model.get_all_channels()
    channel_name=""
    if request.args.get('channel_name')!=None:
        channel_name = request.args.get('channel_name', '')
    else:
        channel_name = channel_realname
    for channel_temp in channels:
        if channel_temp.get('channel_name') == channel_name:
            args = {'channel_code': channel_temp.get('channel_code', ''), 'channel_name': channel_name,
                    'username': channel_temp.get('username', ''), 'dev_name': ''}
            args['devs'] = model.get_devs_unopened(args)
            break
    # req_channel = request.form.get('channel', '')
    # args = {}
    # if req_channel:
    #     args = {"channel_code": req_channel.split("$")[0] , "channel_name" :req_channel.split("$")[1], "username" :req_channel.split("$")[2], "dev_name":request.form.get('dev_name', '')}
    #     args["devs"] = model.get_devs_unopened(args)
    return render_template('add_channel_device.html', channels=channels, args=args)

@preload.route('/add_preload_device', methods=['GET', 'POST'])
@all_permission.require(http_exception=401)
def add_preload_device():
    reqe_devs = request.form.get('devs', '')
    devs = []
    for reqe_dev in reqe_devs[:-1].split(";"):
        devs.append({"username":  request.form.get('username', ''),
                   "channel_name": request.form.get('channel_name', ''),
                   "channel_code":  request.form.get('channel_code', ''),
                   "status":  'OPEN',
                   "name":  reqe_dev.split("$")[0],
                   "host":  reqe_dev.split("$")[1],
                   "firstLayer":True if reqe_dev.split("$")[2] == 'True' else False })
    model.add_dev(devs)
    return preload_devices()


@preload.route('/add_preload_channel_device', methods=['GET', 'POST'])
@all_permission.require(http_exception=401)
def add_preload_channel_device():
    reqe_devs = request.form.get('devs', '')
    if reqe_devs:
        devs = []
        for reqe_dev in reqe_devs[:-1].split(";"):
            devs.append({"username":  request.form.get('username', ''),
                       "channel_name": request.form.get('channel_name', ''),
                       "channel_code":  request.form.get('channel_code', ''),
                       "status":  'OPEN',
                       "name":  reqe_dev.split("$")[0],
                       "host":  reqe_dev.split("$")[1],
                       "firstLayer":True if reqe_dev.split("$")[2] == 'True' else False })
        model.add_dev(devs)
        logger.debug('preload_channel_devices:%s' % url_for('preload.preload_channel_devices'))
    return redirect(url_for('preload.preload_channel_devices', channel_name=request.form.get('channel_name', ''),
                            username=request.form.get('username', '')))
    # return preload_channel_devices()

@preload.route('/del_preload_device/<id>', methods=['GET', 'POST'])
@all_permission.require(http_exception=401)
def del_preload_device(id):
    model.del_devs(id)
    # if (id.index(';')>0):
    #     model.del_devs(id)
    # else:
    #     model.del_dev(id)
    return preload_devices()


@preload.route('/del_preload_channel_device', methods=['GET', 'POST'])
@all_permission.require(http_exception=401)
def del_preload_channel_device():
    id = request.args.get('id')
    model.del_devs(id)
    # if (id.index(';')>0):
    #     model.del_devs(id)
    # else:
    #     model.del_dev(id)
    # return preload_devices()
    return redirect(url_for('preload.preload_channel_devices', channel_name=request.args.get('channel_name', ''),
                            username=request.args.get('username', '')))


@preload.route('/del_all_preload_channel_device', methods=['GET', 'POST'])
@all_permission.require(http_exception=401)
def del_all_preload_channel_device():
    channel_name = request.args.get('channel_name', '')
    username = request.args.get('username', '')
    if channel_name and username:
        model.del_all_devs(channel_name, username)
    # model.del_devs(id)
    # if (id.index(';')>0):
    #     model.del_devs(id)
    # else:
    #     model.del_dev(id)
    # return preload_devices()
    return redirect(url_for('preload.preload_channel_devices', channel_name=channel_name,
                            username=username))


@preload.route('/preload_query', methods=['GET', 'POST'])
def query_url():
    totalpage = 0
    args = {"totalpage":totalpage,"curpage":int(request.form.get("curpage",0)),
    "username":request.form.get("username",""),"status":request.form.get("status",""),
    "url":request.form.get("url",""),"date":request.form.get("date",datetime.strftime(datetime.now(),"%m/%d/%Y"))}
    urls_dict = model.get_urls(args)
    args["totalpage"] = urls_dict.get("totalpage")
    logger.debug(urls_dict.get("urls"))
    return render_template('preload_query.html', urls=urls_dict.get("urls"),args=args)

@preload.route("/preload_timing", methods=['GET','POST'])
@all_permission.require(http_exception=401)
def preload_timing():
    time_now = datetime.now()
    logger.debug("time_now:::::%s" %time_now)
    timing = time_now.strftime("%Y-%m-%d %H:%M")
    logger.debug("timing:::::%s" %timing)
    args = {}
    args['timing'] = timing
    args['device_error'] = 'device_right'
    return render_template('preload_big_timing.html',args=args)

@preload.route("/preload_timing_action", methods=['GET','POST'])
def preload_timing_action():
    username = request.form.get('username')
    parent_name = request.form.get('parent_name')
    preload_timing = request.form.get('preload_timing')
    preload_url = request.form.get('preload_url')
    preload_devices = request.form.get('preload_device')
    preload_validation = request.form.get('preload_validation')
    logger.debug("username:::%s" %username)
    logger.debug("parent_name:::%s" %parent_name)
    logger.debug("preload_timing:::%s"%preload_timing)
    logger.debug("preload_url::::%s"%preload_url)
    logger.debug("preload_devices:::%s"%preload_devices)
    logger.debug("preload_validation:::%s"%preload_validation)
    utf_username = username.encode("utf-8")
    utf_parent_name = parent_name.encode("utf-8")
    utf_preload_timing = preload_timing.encode("utf-8")
    utf_preload_url = preload_url.encode("utf-8")
    utf_preload_devices = preload_devices.encode("utf-8")
    utf_preload_validation = preload_validation.encode("utf-8")
    logger.debug("username:::%s" %type(utf_username))
    logger.debug("parent_name:::%s" %type(utf_parent_name))
    logger.debug("preload_timing:::%s"%type(utf_preload_timing))
    logger.debug("preload_url::::%s"%utf_preload_url)
    logger.debug("preload_devices:::%s"%utf_preload_devices)
    logger.debug("preload_validation:::%s"%type(utf_preload_validation))
    url_list=utf_preload_url.split('\r\n')
    device_list=utf_preload_devices.split('\r\n')
    logger.debug("url_list::::%s" %url_list)
    logger.debug("device_list::::%s" %device_list)
    all_data_devices=[]
    if utf_parent_name =='':
        for url_line in url_list:
            isValid, is_multilayer, channel_code, ignore_case = rcmsapi.isValidUrl(utf_username, url_line)
            if isValid: 
                pre_devs =init_preload_devs(channel_code)
                if pre_devs:
                    for pre_line in pre_devs:  
                        if pre_line['name'] in device_list:
                            all_data_devices.append(pre_line)
                            device_list.remove(pre_line['name'])
    else:
        for url_line in url_list:
            isValid, is_multilayer, channel_code, ignore_case = rcmsapi.isValidUrlByPortal(utf_username, utf_parent_name, url_line)
            if isValid:
                pre_devs =init_preload_devs(channel_code)
                if pre_devs:
                    for pre_line in pre_devs:
                        if pre_line['name'] in device_list:
                            all_data_devices.append(pre_line)
                            device_list.remove(pre_line['name'])
    logger.debug("all_data_devices::::%s" %all_data_devices)
    all_data_urls=[]
    index=1
    for url_line in url_list:
        
        if url_line !='':
            all_data_dict={}
            all_data_dict['url']=url_line
            all_data_dict['id']=index
            all_data_urls.append(all_data_dict)
        index=index+1
    logger.debug("all_data_urls::::%s" %all_data_urls)
    send_type = config.get("big_preload_address", "preload_address")
    if len(all_data_devices)==0:
        #return redirect(url_for('preload.preload_timing',device_error='device_error'))
        time_now = datetime.now()
        timing = datetime.strftime(time_now,"%Y-%m-%d %H:%m")
        args = {}
        args['timing'] = timing
        args['device_error'] = 'device_error'
        return render_template('preload_big_timing.html',args=args)
    else:
        big_preload_url="http://"+send_type+"/internal/preloadDevice"
        logger.debug("big_preload_url:::::%s" %big_preload_url) 
        utf_preload_timing=utf_preload_timing+":00"
        params = urllib.parse.urlencode({"username": utf_username, "compressed": False,"tasks": json.dumps(all_data_urls), "nest_track_level": 0, "startTime": utf_preload_timing, "validationType": utf_preload_validation, "speed": "","devices": json.dumps(all_data_devices)})
        logger.debug("params:::%s" %params)
        try:
            logger.debug("param")
            urllib.request.urlopen(big_preload_url,params)
        except Exception:
            logger.debug("200G:error--%s" %traceback.format_exc())
        return redirect('/preload_query')

def init_preload_devs(channel_code):
    try:
        rcms_devs = []
        for dev in rcmsapi.getFirstLayerDevices(channel_code):
            if dev.get("status") == "OPEN":
                rcms_devs.append(dev)
        for dev in rcmsapi.getDevices(channel_code):
            if dev.get("status") == "OPEN":
                rcms_devs.append(dev)
        logger.debug("rcms_devs::::%s"%rcms_devs)
        return rcms_devs
    except Exception:
        logger.debug("init_pre_devs error:%s " % e)
        logger.debug(traceback.format_exc())

@preload.route("/pre_device/<dev_id>", methods=['GET','POST'])
def find_devs(dev_id):
    db_devs = model.get_devs_by_id(dev_id)
    devs = list(db_devs.pop("devices").values())
    devs.sort(reverse=True, key=lambda  x:x.get('code'))
    devs.sort(reverse=True, key=lambda  x:x.get('firstLayer'))
    return render_template('prelaod_query_dev.html', devs=devs,unprocess=db_devs.get("unprocess"),count=len(devs))

@preload.route("/pre_result/<url_id>", methods=['GET','POST'])
def find_result(url_id):

    try:
        preload_send_type = config.get('preload_send', 'send_type')
    except Exception:
        preload_send_type = 'xml'

    if preload_send_type == 'xml':
        result = model.get_result_by_id(url_id)
    else:
        result = model.get_result_by_id_new(url_id)
    # logger.debug("find_result result: %s" % result)
    devs = list(result.get("devices").values())
    devs.sort(reverse=True, key=lambda  x:x.get('code'))
    devs.sort(reverse=True, key=lambda  x:x.get('firstLayer'))
    return render_template('preload_result.html',count=len(result.get("devices")),result=result,devs=devs)


@preload.route("/callback_result/<url_id>", methods=['GET','POST'])
def find_email_url_result(url_id):
    result = model.get_email_url_result_by_uid(url_id)
    # here can add the sort by time
    # devs = result.get("devices").values()
    # devs.sort(reverse=True, key=lambda  x:x.get('code'))
    # devs.sort(reverse=True, key=lambda  x:x.get('firstLayer'))
    logger.debug("find_email_url_result result:%s" % result)
    return render_template('preload_email_url_result.html', result=result)


@preload.route("/preload_billing", methods=['GET','POST'])
def preload_billing():
    args = {"username":request.form.get("username",""),"channel":request.form.get("channel",""),
            "start_date":request.form.get("start_date",datetime.strftime(datetime.now(),"%m/%d/%Y")),
            "stop_date":request.form.get("stop_date",datetime.strftime(datetime.now(),"%m/%d/%Y"))}
    billing = model.get_billing(args)
    return render_template('preload_billing.html',billing=billing,args=args)

@preload.route("/retry_branch_device_preload/<retry_branch_id>", methods=['GET', 'POST'])
def find_retry_branch_devices(retry_branch_id):
    logger.debug("find_retry_branch_devices retry_branch_id:%s" % retry_branch_id)
    db_devs = get_retry_dev_branch_by_id(retry_branch_id)
    logger.debug("db_devs:%s" % db_devs)
    count, unprocess = statistic_banch_code(db_devs)
    db_devs.sort(reverse=True, key=lambda x:x.get('branch_code'))
    db_devs.sort(reverse=True, key=lambda x:x.get('firstLayer'))
    return render_template('retry_branch_devices.html', devs=db_devs, unprocess=unprocess, count=count)

@preload.route('/add_queue_ratio', methods=['GET', 'POST'])
def add_queue_ratio():
    if request.method == 'POST':
        args = {
            "queue_name": request.form.get("queue_name",""),
            "queue_ratio": request.form.get("queue_ratio",""),
            "status": "ready",
        }
        if not args['queue_name'] or not args['queue_ratio']:
            flash('queue_name or queue_ratio be not empty!')
            return render_template('add_queue_ratio.html')
        logger.debug("args: %s, type: %s" % (args, type(args)))
        has_existed, args_dict = model.insert_queue_ratio(args)
        if has_existed:
            flash('The queue_name you submitted has existed!')
            return render_template('add_queue_ratio.html')
        return redirect('/preload_queue_ratio')
    return render_template('add_queue_ratio.html')

@preload.route('/preload_queue_ratio', methods=['GET', 'POST'])
def preload_queue_ratio():
    totalpage = 0
    args = {
        "totalpage":totalpage,
        "curpage":int(request.form.get("curpage",0)),
        "status":request.form.get("status",""),
    }
    queue_dict = model.get_queues(args)
    args["totalpage"] = queue_dict.get("totalpage")
    logger.debug(queue_dict)
    return render_template('preload_queue_ratio.html', queues=queue_dict.get('queues'), args=args)

@preload.route('/preload_queue_del/<id>', methods=['GET'])
def preload_queue_del(id):
    del_id = model.del_queue(id)
    logger.debug('preload_queue_del del_id: %s' % del_id)
    if del_id:
        return redirect('/preload_queue_ratio')
    return render_template('preload_queue_ratio.html')

@preload.route('/preload_queue_channel', methods=['GET', 'POST'])
def preload_queue_channel():
    totalpage = 0
    args = {
        "totalpage":totalpage,
        "curpage":int(request.form.get("curpage",0)),
        "status":request.form.get("status",""),
    }
    queue_dict = model.get_queues(args)
    args["totalpage"] = queue_dict.get("totalpage")
    logger.debug(queue_dict)
    return render_template('preload_queue_ratio.html', queues=queue_dict.get('queues'), args=args)

@preload.route('/add_queue_channel/<q_id>', methods=['GET', 'POST'])
def add_queue_channel(q_id):
    the_queue = model.get_the_queue(q_id)
    if request.method == 'POST':
        d = json.loads(request.data)
        model.update_queue_ratio(d)
        return redirect('/preload_queue_channel') # not work
    return render_template('add_queue_channel.html', queue=the_queue)
