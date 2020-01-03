#-*- coding:utf-8 -*-
__author__ = 'cl'
import socket
from core import redisfactory,rcmsapi
from datetime import datetime, timedelta
import time
from core.database import query_db_session,db_session,s1_db_session
from core.update import db_update
from bson import ObjectId
import logging,urllib.request,urllib.parse,urllib.error,math ,re ,pymongo
import simplejson as json
from .models import load_url
from util import log_utils
from sys import exit
logger = log_utils.get_admin_Logger()
# logger = logging.getLogger("preload_models")
# logger.setLevel(logging.DEBUG)


preload_cache = redisfactory.getDB(1)
USER_CACHE = redisfactory.getDB(2)
PRELOAD_DEVS = redisfactory.getDB(5)
CACHE_TIMEOUT = 86400
db = db_session()
q_db = query_db_session()
s1_db = s1_db_session()

def get_channels(args):
    per_page = 30
    curpage = args.pop("curpage")
    if not args.get("username"):
        args.pop("username")
    if not args.get("channel_name"):
        args.pop("channel_name")
    channels = [get_device_type(channel) for channel in db.preload_channel.find(args).skip(curpage*per_page).limit(per_page)]
    totalpage = int(math.ceil(db.preload_channel.find(args).count()/(per_page*1.00)))
    return channels,totalpage

def get_all_channels():
    channels = [channel for channel in db.preload_channel.find()]
    return channels

def get_users():
    users = []
    try:
        users = USER_CACHE.get("preload_users")
        if not users:
            users = json.dumps([user for user in q_db.preload_user.find({},{"name":1,"_id":0})])
            USER_CACHE.set("preload_users",users)
            USER_CACHE.expire("preload_users",CACHE_TIMEOUT)
        users = json.loads(users)
        users.sort(key=lambda x:x.get("name"))
    except Exception:
        logger.debug("get_customers error %s" % str(e) )
    return users

def get_channels_unopened(username,usertype):
    logger.debug("get_channels_unopened username %s usertype %s " % (username,usertype) )
    channels = []
    if int(usertype)==1:
        channels = rcmsapi.get_channels(username)
        opened_channels = [c.get("channel_name") for c in db.preload_channel.find({"username":username})]
        return [channel for channel in channels if channel.get("name") not in opened_channels]
    else:
        channels = rcmsapi.get_channels_by_portal(username)
        opened_channels = [c.get("channel_name") for c in db.preload_channel.find({"username":username})]
        for x in channels:
            x['name']=x.get('channelName')
            x['code']=x.get('channelId')
        return [channel for channel in channels if channel.get("name") not in opened_channels]
def add_channel(channels,device_type=500):
#    args = {"status":True,"channels":[]}    
#    for channel in channels:
#        channel_db = db.preload_channel.find_one({"channel_name":channel.get('channel_name')})
#        if channel_db:
#            if channel_db.get("channel_name"):
#                args["status"] = False
#                args["channels"].append(channel_db.get("channel_name"))
#    db.preload_channel.insert(channels)
#    for channel in channels:
#        CHANNEL_CODE = channel["channel_name"]
#        if CHANNEL_CODE in args.get("channels"):
#            logger.debug("channels devs already in PRELOAD_DEVS!!!")
#        else:
#            CONFIG_COUNT = device_type
#            PRELOAD_DEVS.set(CHANNEL_CODE, CONFIG_COUNT)
#    return args
    args = {"status":True,"channels":[]}
    for channel in channels:
        channel_db = db.preload_channel.find_one({"channel_name":channel.get('channel_name')})
        print(channel_db)
        if channel_db:
            if channel_db.get("channel_name"):
                print("dulit channel")
                args["status"] = False
                args["channels"].append(channel_db.get("channel_name"))
        else:
            PRELOAD_DEVS.set(channel["channel_name"],device_type)
        channel_db = db.preload_channel.find_one({"channel_name":channel.get('channel_name'),"username":channel.get('username')})
        if not channel_db:
            db.preload_channel.insert(channel)
    return args


def del_channel(id):
    channel = db.preload_channel.find_one({"_id":ObjectId(id)})
    db.preload_channel.remove({"_id":ObjectId(id)})
    channel_db = db.preload_channel.find({"channel_name":channel["channel_name"]})
    for x in channel_db:
        if x.get("channel_name"):
            return
    PRELOAD_DEVS.delete(channel["channel_name"])

def get_channel_by_id(id):
    channel = db.preload_channel.find_one({"_id":ObjectId(id)})
    get_device_type(channel)
    return channel

def set_channel_status(id,status):
    channel = db.preload_channel.find_one({"_id":ObjectId(id)})
    if status == 1:
        PRELOAD_DEVS.delete(channel["channel_name"])
    else:
        PRELOAD_DEVS.set(channel["channel_name"], channel.get('config_count'))
    db_update(db.preload_channel,{"_id":ObjectId(id)},{"$set":{"is_live":status}})

def config_channel(args):
    channel = db.preload_channel.find_one({"_id":ObjectId(args.get("_id"))})
    channel['type'] = args.get("type")

    device_type_ori = 3 
    if 'config_count' in channel:
        device_type_ori=int(channel['config_count'])
    channel['config_count'] = args.get("device_type")
    channel['has_callback'] = args.get("has_callback")
    channel['callback'] = args.get("callback")
    channel['region'] = args.get("region")
    channel['avoid_period_s'] = args.get("avoid_period_s")
    channel['avoid_period_e'] = args.get("avoid_period_e")
    channel['parse_m3u8_f'] = args.get("parse_m3u8_f")
    channel['parse_m3u8_nf'] = args.get("parse_m3u8_nf")
    today_str = time.strftime('%Y%m%d')
    if channel['avoid_period_s'] and channel['avoid_period_e']:
        start_p = datetime.strptime(today_str+channel['avoid_period_s'], '%Y%m%d%H:%M')
        end_p = datetime.strptime(today_str+channel['avoid_period_e'], '%Y%m%d%H:%M')
        delta_t = end_p - start_p
        avoid_extra_minutes = int(args.get("avoid_extra_minutes", 0))
        channel['period_length'] = (avoid_extra_minutes*60) if (avoid_extra_minutes*60) > delta_t.seconds else delta_t.seconds
        channel['status'] = 'AVOID'
    else:
        channel['status'] = ''
    channel['first_layer_not_first'] = args.get('first_layer_not_first')
    # logger.debug("config_channel args: %s" % args)
    # logger.debug("config_channel channel: %s" % channel)
    db.preload_channel.save(channel)

    if int(args.get("device_type"))!= int(device_type_ori) and int(args.get("device_type"))!=3:
        db.preload_config_device.delete_many({'channel_name': channel['channel_name']})

    PRELOAD_DEVS.set(channel['channel_name'], channel['config_count'])
    
def get_devices(args):
    per_page = 30
    curpage = args.pop("curpage")
#    if not args.get("username"):
#        args.pop("username")
    if not args.get("channel_name"):
        args.pop("channel_name")
    if not args.get("name"):
        args.pop("name")
    devs = [dev for dev in db.preload_config_device.find(args).skip(curpage*per_page).limit(per_page)]
    totalpage = int(math.ceil(db.preload_config_device.find(args).count()/(per_page*1.00)))
    return devs,totalpage

def get_devices_all(c_name):
    channel = {}
    channel['channel_name'] = c_name
    channel['devs_info'] = [{'name': dev.get('name'), 'host': dev.get('host'), 'channel_code': dev.get('channel_code', '0'), 'username': dev.get('username')} for dev in db.preload_config_device.find({'channel_name': c_name})]
    dev_list_str = ''
    for dev in channel['devs_info']:
        dev_list_str += '%s\n' % (dev.get('name'), )
        # dev_list_str += '%s[%s]\n' % (dev.get('name'), dev.get('host'))
    channel['dev_list'] = dev_list_str

    channel_dict = db.preload_channel.find_one({'channel_name': c_name})
    channel['channel_code'] = channel_dict.get('channel_code')
    channel['username'] = channel_dict.get('username')
    return channel

def set_devices(channel, dev_list):
    from core.preload_worker_new import init_pre_devs
    devs_from_cms = init_pre_devs(channel.get('channel_code'), all_dev=True)

    try:
        socket.inet_aton(dev_list[0])
        f_name = 'host'
    except Exception:
        f_name = 'name'
    dev_list_new = [d_all for d_all in devs_from_cms for d in dev_list if d == d_all.get(f_name)]
    logger.debug("set_devices dev_list_new: %s|| len(devs_from_cms): %s" % (dev_list_new, len(devs_from_cms)))
    devices_new = [add_dev_fields(d, username=channel.get('username'), channel_code=channel.get('channel_code'), channel_name=channel.get('channel_name')) for d in dev_list_new]
    # logger.debug("set_devices devices_new: %s" % (devices_new))
    del_ret = db.preload_config_device.delete_many({'channel_name': channel['channel_name']})
    # logger.debug("set_devices del_ret.deleted_count: %s" % (del_ret.deleted_count, ))

    if del_ret:
        devices_ret = db.preload_config_device.insert_many(devices_new)
    # logger.debug("set_devices devices_ret: %s|| devices_new: %s" % (devices_ret, devices_new))
    return devices_ret

def add_dev_fields(dev_dict, **field_dict):
    if isinstance(dev_dict, dict):
        for k, v in list(field_dict.items()):
            dev_dict[k] = v
    return dev_dict

def get_device_type(channel):
    channel['device_type'] = PRELOAD_DEVS.get(channel.get('channel_name'))
    return channel

def get_devs_unopened(args):
    dev_name = args.pop("dev_name")
    rcms_devs = [dev for dev in rcmsapi.getFirstLayerDevices(args.get("channel_code")) + rcmsapi.getDevices(args.get("channel_code"))  if dev.get("status") == "OPEN"]
    if dev_name:
        rcms_devs = [ dev for dev in rcms_devs if dev.get("name") == dev_name ]
    opened_devs = [dev.get("name") for dev in db.preload_config_device.find(args)]
    return [dev for dev in rcms_devs if dev.get("name") not in opened_devs]

def add_dev(devs):
    db.preload_config_device.insert(devs)

def del_dev(id):
    db.preload_config_device.remove({"_id":ObjectId(id)})
def del_devs(id):
    ids = id.split(';')
    del_ids = [ObjectId(idi) for idi in ids]
    logger.error( del_ids)
    db.preload_config_device.remove({"_id":{'$in':del_ids}})


def del_all_devs(channel_name, username):
    """
    delete all devs according channel_name, username
    :param channel_name: the name of channel
    :param username: the name of user
    :return:
    """
    try:
        db.preload_config_device.delete_many({'channel_name': channel_name, 'username': username})
        logger.debug('del_all_devs  delete channel_name:%s, and username:%s succes' % (channel_name, username))
    except Exception:
        logger.debug('del_all_devs delete channel_name:%s, username:%s error:%s' % (channel_name, username, e))

def get_urls(query_args):
    per_page = 30
    urls_dict = {"urls":[],"totalpage":0}
    dt = datetime.strptime(query_args.get("date"), "%m/%d/%Y")
    query = {'created_time':{"$gte":dt, "$lt":(dt + timedelta(days=1))}}
    if query_args.get("username"):
        append_userfield(query_args.get("username"),query)
    if query_args.get("url") :
        query['url'] = re.compile("^%s.*" %query_args.get("url"))
    if query_args.get("status") != "ALL":
        query['status'] = query_args.get("status")
    if query_args.get("status") == "ALL" and query_args.get("username") == '' and query_args.get("url") == '':
        pass
    else:    
        logger.debug("query:%s" % str(query))
        totalpage = int(math.ceil(s1_db.preload_url.find(query).limit(600).count(True)/(per_page*1.00)))
        urls_dict ={"urls": load_url([u for u in s1_db.preload_url.find(query,{"get_url_speed":1,"_id":1,"username":1,'url':1,'created_time':1,'status':1,'finish_time':1,'dev_id':1, 'retry_branch_id': 1}).sort('created_time', pymongo.DESCENDING).skip(query_args.get("curpage")*per_page).limit(per_page)]) ,"totalpage" : totalpage}
    return urls_dict

def append_userfield(username,query):
    from cache import rediscache
    if rediscache.isFunctionUser(username):
        query['username']=username
    else:
        query['parent'] = username

def get_devs_by_id(dev_id):
    return s1_db.preload_dev.find_one({'_id': ObjectId(dev_id)})


def get_result_by_id_new(url_id):
    try:
        result = preload_cache.get(url_id)
        dev_cache = preload_cache.hgetall('%s_dev'%(url_id))
        if result and dev_cache:
            res = json.loads(result)
            devices = {k:json.loads(v) for k,v in list(dev_cache.items())}
            res['devices'] = devices
            return res
        else:
            return s1_db.preload_result.find_one({"_id":ObjectId(url_id)})
    except Exception:
        logger.debug("get_result_by_id_new[error]: %s" % (traceback.format_exc(), ))
        return {}

def get_result_by_id(url_id):
    try:
        result = preload_cache.get(url_id)
        if result:
            return json.loads(result)
        else:
            return s1_db.preload_result.find_one({"_id":ObjectId(url_id)})
    except Exception:
        return {}

def get_email_url_result_by_uid(uid):
    """
    get result of email_url_result
    :param uid: the uid of email_url_result
    :return:
    """
    result = []
    try:
        result = q_db.email_url_result.find({'uid': ObjectId(uid)})
    except Exception:
        logger.debug('get_email_url_result_by_uid find error:%s' % e)
    return result


def get_billing(query_args):
    billing = {'night':{"count":0},'standard':{"count":0},'gold':{"count":0}}
    if query_args.get("username") or query_args.get("channel"):
        query = {}
        if query_args.get("username"):
            query['username'] = query_args.get("username")
        if query_args.get("channel"):
            query['url'] = {'$regex':query_args.get("channel")}
        start_date = datetime.strptime(query_args.get("start_date"), "%m/%d/%Y")
        stop_date = datetime.strptime(query_args.get("stop_date"), "%m/%d/%Y")
        if start_date < stop_date:
            query['created_time'] ={"$gte":start_date, "$lt":stop_date + timedelta(days=1)}
        else:
            query['created_time'] ={"$gte":stop_date, "$lt":start_date + timedelta(days=1)}
        logger.debug("get_billing_query:%s" % str(query))
        for task in s1_db.preload_url.find(query,{"created_time":1}):
            if time(0,00,00) <= task.get('created_time').time()  < time(8,00,00) :
                billing.get('night')['count'] += 1
            elif time(8,00,00) <= task.get('created_time').time() < time(18,00,00) :
                billing.get('standard')['count'] += 1
            elif time(18,00,00) <= task.get('created_time').time() <= time(23,59,59) :
                billing.get('gold')['count'] += 1
    return billing

def get_all_province():
    try:
        province_list = q_db.device_basic_info.distinct('province')
    except:
        province_list = []
    return province_list

def insert_queue_ratio(args):
    has_existed = False
    if s1_db.preload_queue_ratio.find_one({'name': args.get('queue_name')}):
        has_existed = True
    if not has_existed:
        args.update({'created_time': datetime.now()})
        s1_db.preload_queue_ratio.insert_one(args)
    return has_existed, args

def get_queues(query_args):
    per_page = 30
    queues_dict = {"urls":[],"totalpage":0}
    query = {}
    if query_args.get("queue_name"):
        query = {'queue_name': query_args.get('queue_name')}
    logger.debug("query:%s" % str(query))
    totalpage = int(math.ceil(s1_db.preload_queue_ratio.find(query).limit(600).count(True)/(per_page*1.00)))
    queues_dict ={"queues": [queue for queue in s1_db.preload_queue_ratio.find()] ,"totalpage" : totalpage}
    return queues_dict

def del_queue(id):
    return s1_db.preload_queue_ratio.remove({'_id': ObjectId(id)})

def get_the_queue(id):
    return s1_db.preload_queue_ratio.find_one({'_id': ObjectId(id)})

def update_queue_ratio(data):
    return s1_db.preload_queue_ratio.update_one({'_id': ObjectId(data['id'])}, {'$set': {'channel': data['queue_channel']}})

