# -*- coding: utf-8 -*-
import logging, datetime, simplejson, time, traceback ,urllib.request,urllib.error,urllib.parse,hashlib
from core.database import query_db_session,db_session
from core import redisfactory
from core.config import config
import simplejson as json
# from core.generate_id import ObjectId
from bson.objectid import ObjectId
from core.models import URL_OVERLOAD_PER_HOUR, DIR_OVERLOAD_PER_HOUR, PRELOAD_URL_OVERLOAD_PER_HOUR
import uuid



db = db_session()
CACHERECORD = redisfactory.getMDB(7)
H_PRIORITY_CACHE = redisfactory.getDB(15)

PHYSICAL_URL = redisfactory.getDB(9)
PHYSICAL_URL_key = "physical_url"

LOG_FILENAME = '/Application/bermuda3/logs/bermuda_tools.log'
# LOG_FILENAME = '/home/rubin/logs/bermuda_tools.log'
formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s")
fh = logging.FileHandler(LOG_FILENAME)
fh.setFormatter(formatter)

logger = logging.getLogger('monitor_region_devs')
logger.addHandler(fh)
logger.setLevel(logging.DEBUG)

expire_time = 5 * 24 * 60 * 60

def get_current_date_str(_format='%Y-%m-%d'):
    '''
    获取当天时间key
    '''
    now = datetime.datetime.now()
    return now.strftime(_format)

def get_active_devices():
    '''
    获取当日活跃设备
    '''
    _str = get_current_date_str()
    _key = "%s_failed" %(_str)
    res = CACHERECORD.zrange(_key, 0, -1)
    return res

def is_refresh_high_priority(channel_code):
    '''
    是否为高优先级频道
    '''
    is_high = False
    try:
        channel_code = str(channel_code)
        c_key = 'h_priority_%s'%(channel_code)
        config_str = H_PRIORITY_CACHE.get(c_key)
        if not config_str:
            config_obj = db.refresh_high_priority.find_one({'channel_code':channel_code})
            if config_obj:
                config_obj.pop('_id')
                H_PRIORITY_CACHE.set(c_key, simplejson.dumps(config_obj,cls=DatetimeJSONEncoder))
        else:
            config_obj = simplejson.loads(config_str)

        if config_obj:
            now = datetime.datetime.now()
            start_time = config_obj['start_time']
            end_time = config_obj['end_time']
            if not isinstance(start_time, datetime.datetime):
                start_time = datetime.datetime.fromtimestamp(start_time)
            if not isinstance(end_time, datetime.datetime):
                end_time = datetime.datetime.fromtimestamp(end_time)
            if now >= start_time and now < end_time:
                is_high = True
    except Exception:
        logger.info('getUrlsFromRcms splite error:%s' % traceback.format_exc())

    return is_high


def get_max_receiver_count(date_obj):
    '''
    获取某日的最高 接收数
    return [] or [('19:27:23', 3.0)] 
    '''
    now_key = date_obj.strftime('%Y-%m-%d')
    receiver_group = eval(config.get('monitor', 'receiver_group'))
    sort_all_key = '%s_%s_receiver_sort' %(receiver_group[0][0], now_key)
    res = CACHERECORD.zrevrange(sort_all_key, 0, 0, True)
    if not res:
        return []
    return res


def pager(total_page, current_page, max_page_len=10):                                                                                                                              
    '''
    返回页码
    return page_list, can_pre, can_next                                                                                                                                            
    '''
    can_pre = True
    can_next = True
    if total_page <= max_page_len:     
        return list(range(total_page)), False, False                                                                                                                                     
    #前段个数
    half_num = max_page_len / 2    
    #后段个数
    other_half = max_page_len - half_num                                                                                                                                           

    res = [current_page]
    for x in range(1, other_half+1):  
        page = current_page + x        
        if page < total_page:
            res.append(page)
            other_half -= 1
        else:
            can_next = False
            break

    if other_half > 0:
        left_num = half_num + other_half                                                                                                                                           
    else:
        left_num = half_num

    for n in range(1, left_num+1):    
        pre_page = current_page - n    
        if pre_page >= 0:
            res.insert(0, pre_page)    
        else:
            can_pre = False
            break

    return res, can_pre, can_next  


def get_email_list_by_type(_type):
    '''
    获取通用邮件配置
    '''
    res =  db.email_management.find_one({'type':_type})
    if not res:
        return []
    return res['address'] 


def calculate_diff_between_time(begin_time, end_time):
    """
    calculate the time difference between the two time,
    :param begin_time: the start of time, type datetime
    :param end_time: the end of time, type datetime
    :return: seconds (number, int)
    """
    time_diff = end_time - begin_time
    return time_diff.days * 24 * 3600 + time_diff.seconds


def get_channelname(url):
    '''
    根据url获取频道名称
    '''
    channelname = ''
    try:
       u_s = url.split('/', 3)
       channelname = u_s[0] + '//' + u_s[2]
    except Exception:
        logger.error('get_channelname error is %s' % (traceback.format_exc(), ))
    return channelname


def strip_list(list_substance):
    """
    list which is constituted by the string type, to strip the every string
    :param list_substance: [' xxx', 'xxx ', 'xxx', 'xxx']
    :return: ['xxx', 'xxx', 'xxx', 'xxx']
    """
    if list_substance:
        for i in range(len(list_substance)):
            # delete \n \r \t ' ' of string, at head  and at tail
            list_substance[i] = list_substance[i].strip()
        return list_substance
    else:
        return []


def strip_list_remove_blank(list_result):
    """
    strip function on the contents of the list, and the n delete the empty string in the list
    :param list_result:
    :return:
    """
    result = []
    if not list_result:
        return result
    else:
        for li in list_result:
            result_temp = li.strip()
            if result_temp != '':
                result.append(result_temp)
        return result

class JSONEncoder(json.JSONEncoder):
    """
    solve ObjectId('57515b0a2b8a681de5b0612b') is not JSON serializable
    """

    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        return json.JSONEncoder.default(self, o)


def load_task(json_data):
    """
    parse json,restore the original data structure
    :param json_data: str
    :return: original data structure
    """
    try:
        return json.loads(json_data)
    except Exception:
        logger.debug('parse json error:%s' % e)
        return None


def datetime_convert_timestamp(date_time):
    """
    datetime converted to time stamp
    :param date_time: datetime
    :return: timestamp
    """
    return time.mktime(date_time.timetuple())


def get_overload_cache(username):
    '''
    获取超量配置缓存
    @_type: URL/DIR/PRELOAD_URL
    '''
    _res = {"USERNAME":username, "URL": URL_OVERLOAD_PER_HOUR, "DIR": DIR_OVERLOAD_PER_HOUR, "PRELOAD_URL": PRELOAD_URL_OVERLOAD_PER_HOUR}
    if not username:
        return _res
    res = CACHERECORD.get("overload_"+username)
    if not res:
        db_config = db.overloads_config.find_one({"USERNAME":username})
        if not db_config:
            return _res
        save_data = {"USERNAME":username,"URL": db_config.get("URL", URL_OVERLOAD_PER_HOUR), "DIR": db_config.get("DIR", DIR_OVERLOAD_PER_HOUR), "PRELOAD_URL_OVERLOAD_PER_HOUR": db_config.get("PRELOAD_URL", PRELOAD_URL_OVERLOAD_PER_HOUR)}
        CACHERECORD.set("overload_"+username, json.dumps(save_data))
        return save_data
    res = json.loads(res)
    return res


def get_url_overload_cache(username):
    '''
    获取用户刷新每小时限制
    '''
    res = get_overload_cache(username)
    return res.get("URL",URL_OVERLOAD_PER_HOUR)


def get_dir_overload_cache(username):
    '''
    获取目录刷新每小时限制
    '''
    res = get_overload_cache(username)
    return res.get("DIR", DIR_OVERLOAD_PER_HOUR)

def get_preload_overload_cache(username):
    '''
    获取预加载url每小时限制
    '''
    res = get_overload_cache(username)
    return res.get("PRELOAD_URL", PRELOAD_URL_OVERLOAD_PER_HOUR)


class DatetimeJSONEncoder(simplejson.JSONEncoder):

     def default(self, o):
        if isinstance(o, datetime.datetime):
            return time.mktime(o.timetuple())
        else:
            return super(DatetimeJSONEncoder, self).default(o)


def operation_record_into_mongo(user, operation_type, small_operation_type, content):
    """

    Args:
        user:  the user of operation
        operation_type: 邮件列表，　频道重定向，　频道忽略大小写，　用户超标量，正则表达式等等
        small_operation_type: update delete  add
        content: the operation content

    Returns:

    """
    try:
        db.operation_record.insert_one({'user': user, "operation_type": operation_type,
                                        "small_operation_type": small_operation_type, 'content': content,
                                        "operation_time": datetime.datetime.now()})
        logger.debug("tool operation_record_into_mongo error user:%s, operation:%s, small_operation_type:%s, content:%s"
                     %(user, operation_type, small_operation_type, content))
    except Exception:
        logger.debug("tool operation_record_into_mongo error:%s,user:%s, operation:%s, small_operation_type:%s, content:%s"
                     %(traceback.format_exc(), user, operation_type, small_operation_type, content))


def add_rid_url_info_into_redis(rid, urls):
    """
    rid_id_FC:{URLID_id1_FC, URLID_id2_FC}
    rid_id_HPCC:{URLID_id1_HPCC, URLID_id2_HPCC}

    Args:
        rid: the _id of request
        urls: the urls

    Returns:
    """
    try:
        if urls:
            RESULT_REFRESH = redisfactory.getDB(5)
            RESULT_REFRESH_PIPE = RESULT_REFRESH.pipeline()
            key_fc = "RID_" + str(rid) + "_FC"
            key_hpcc = "RID_" + str(rid) + "_HPCC"
            for url in urls:
                value_fc = "URLID_" + str(url.get("_id")) + "_FC"
                value_fc_r = value_fc + "_R"
                value_hpcc = "URLID_" + str(url.get('_id')) + "_HPCC"
                value_hpcc_r = value_hpcc + "_R"
                # orignal start
                RESULT_REFRESH_PIPE.sadd(key_fc, value_fc)

                RESULT_REFRESH_PIPE.sadd(key_hpcc, value_hpcc)
                # value  key  reverse

                RESULT_REFRESH_PIPE.set(value_fc_r, key_fc)
                RESULT_REFRESH_PIPE.set(value_hpcc_r, key_hpcc)

                # exipire key
                RESULT_REFRESH_PIPE.expire(key_fc, expire_time)
                RESULT_REFRESH_PIPE.expire(key_hpcc, expire_time)
                RESULT_REFRESH_PIPE.expire(value_fc_r, expire_time)
                RESULT_REFRESH_PIPE.expire(value_hpcc_r, expire_time)
                # orignal end

                # logger.debug("rubin_test   delete pipe")
                # RESULT_REFRESH.sadd(key_fc, value_fc)
                #
                # RESULT_REFRESH.sadd(key_hpcc, value_hpcc)
                # # value  key  reverse
                #
                # RESULT_REFRESH.set(value_fc_r, key_fc)
                # RESULT_REFRESH.set(value_hpcc_r, key_hpcc)
                #
                # # exipire key
                # RESULT_REFRESH.expire(key_fc, expire_time)
                # RESULT_REFRESH.expire(key_hpcc, expire_time)
                # RESULT_REFRESH.expire(value_fc_r, expire_time)
                # RESULT_REFRESH.expire(value_hpcc_r, expire_time)

            RESULT_REFRESH_PIPE.execute()
    except Exception:
        logger.error('add_rid_url_info_into_redis error:%s' % traceback.format_exc())
        logger.error('add_rid_url_info_into_redis rid:%s, urls:%s' % (rid, urls))

# def delete_zip(str_t):
#     """
#     delete the .zip character at the end of the string
#     Args:
#         str_t: http://www.baidu.com/asdf/asdf.zip
#
#     Returns:http://www.baidu.com/asdf/asdf
#
#     """
#     try:
#         if str_t:
#             if str_t.endswith('.zip'):
#                 return str_t.rsplit('.', 1)[0]
#         return str_t
#     except Exception, e:
#         logger.debug('delete_zip error:%s' % traceback.format_exc())
#         return str_t


def delete_fc_rid(urls, devices):
    """

    Args:
        urls: [{"username": xxx, "id": xxxx}]
        devices: [{'code': 200, 'type'；‘FC’}]

    Returns:

    """
    try:
        if urls:
            judge_fc_result = judge_device_fc(devices)
            # fc all success
            if judge_fc_result:

                for url in urls:
                    RESULT_REFRESH = redisfactory.getDB(5)
                    url_id = url.get('id')
                    url_id_fc_r = "URLID_" + str(url_id) + '_FC_R'
                    url_id_fc = "URLID_" + str(url_id) + '_FC'
                    rid_id_fc = RESULT_REFRESH.get(url_id_fc_r)
                    # delete url_id_fc_r
                    RESULT_REFRESH.delete(url_id_fc_r)
                    # delete rid_id_fc  value url_id_fc
                    RESULT_REFRESH.srem(rid_id_fc, url_id_fc)
                    rid_id_fc_smembers = RESULT_REFRESH.smembers(rid_id_fc)
                    if not rid_id_fc_smembers:
                        # _F   finish time
                        RESULT_REFRESH.set(rid_id_fc + '_F', time.time())
                        RESULT_REFRESH.expire(rid_id_fc + '_F', expire_time)

    except Exception:
        logger.error("delete_fc_rid error:%s" % traceback.format_exc())
        logger.info('delete_fc_rid urls:%s, devices:%s' % (urls, devices))


def delete_fc_urlid_host(url_id_fc, host):
    """
    delete urlid_id_fc host
    Args:
        url_id_fc: key of reids 5
        host: the ip of device

    Returns:

    """
    try:
        if url_id_fc and host:
            RESULT_REFRESH = redisfactory.getDB(5)
            # delete the value of set
            RESULT_REFRESH.srem(url_id_fc, host)
            hosts_members = RESULT_REFRESH.smembers(url_id_fc)
            if not hosts_members:
                url_id_fc_r = url_id_fc + "_R"
                rid_id_fc = RESULT_REFRESH.get(url_id_fc_r)
                # delete rid_id_fc  value url_id_fc
                RESULT_REFRESH.srem(rid_id_fc, url_id_fc)
                rid_id_fc_smembers = RESULT_REFRESH.smembers(rid_id_fc)
                if not rid_id_fc_smembers:
                    # _F   finish time
                    RESULT_REFRESH.set(rid_id_fc + '_F', time.time())
                    RESULT_REFRESH.expire(rid_id_fc + '_F', expire_time)
    except Exception:
        logger.error('delete_fc_urlid_host error:%s' % traceback.format_exc())
        logger.info('delete_fc_urlid_host url_id_fc:%s, host:%s' % (url_id_fc, host))


def sadd_hpcc_urlid(urls, devices, type_t='HPCC'):
    """
    add hpcc urlid in to redis
    Args:
        urls:
        devices:
        type_t:

    Returns:

    """
    try:
        if urls and devices:
            RESULT_REFRESH = redisfactory.getDB(5)
            for url in urls:
                id = url.get('id')
                urlid_id_type_t = 'URLID_' + str(id) + "_" + type_t
                for dev in devices:
                    host = dev.get('host')
                    type_dev = dev.get('type')
                    code = dev.get('code')
                    if type_dev == 'HPCC' and (code != 204):

                        RESULT_REFRESH.sadd(urlid_id_type_t, host)
                # set expire time
                RESULT_REFRESH.expire(urlid_id_type_t, expire_time)
                smember_type_t = RESULT_REFRESH.smembers(urlid_id_type_t)
                if not smember_type_t:
                    url_id_type_t_r = urlid_id_type_t + "_R"
                    rid_id_type_t = RESULT_REFRESH.get(url_id_type_t_r)
                    smember_rid_type_t = RESULT_REFRESH.smembers(rid_id_type_t)
                    if not smember_rid_type_t:
                        # _F   finish time
                        RESULT_REFRESH.set(rid_id_type_t + '_F', time.time())
                        RESULT_REFRESH.expire(rid_id_type_t + '_F', expire_time)
    except Exception:
        logger.error('sadd_hpcc_urlid error:%s' % traceback.format_exc())
        logger.info('sadd_hpcc_urlid urls:%s, devices:%s' % (urls, devices))





def delete_urlid_host(url_id, host, type_t ='HPCC'):
    """
    delete urlid_id_fc host
    Args:
        url_id_fc: key of reids 5
        host: the ip of device
        type_t: the type of device

    Returns:

    """
    try:
        if url_id and host:
            RESULT_REFRESH = redisfactory.getDB(5)
            url_id_type = 'URLID_' + str(url_id) + "_" + type_t
            # delete the value of set
            RESULT_REFRESH.srem(url_id_type, host)
            hosts_members = RESULT_REFRESH.smembers(url_id_type)
            if not hosts_members:
                url_id_type_r = url_id_type + "_R"
                rid_id_type = RESULT_REFRESH.get(url_id_type_r)
                # delete rid_id_fc  value url_id_fc
                RESULT_REFRESH.srem(rid_id_type, url_id_type)
                rid_id_fc_smembers = RESULT_REFRESH.smembers(rid_id_type)
                if not rid_id_fc_smembers:
                    # _F   finish time
                    RESULT_REFRESH.set(rid_id_type + '_F', time.time())
                    RESULT_REFRESH.expire(rid_id_type + '_F', expire_time)
    except Exception:
        logger.error('delete_fc_urlid_host error:%s' % traceback.format_exc())
        #logger.info('delete_fc_urlid_host url_id_fc:%s, host:%s' % (rid_id_type, host))


def judge_device_fc(devices):
    """
    if all fc is 200, return true,else false
    Args:
        devices:

    Returns:

    """
    try:
        if devices:
            for dev in devices:
                type_t = dev.get('type')
                code = dev.get('code')
                if type_t == 'FC' and code != 204 and code != 200:
                    return False
            return True
    except Exception:
        logger.error('judge_device_fc error:%s' % traceback.format_exc())
        logger.info('judege_device_fc error devices:%s' % devices)
        return False


def is_chinese(uchar):
    """
    judge a unicode is chinese or not
    Args:
        uchar:

    Returns:

    """
    if (uchar >= '\u4e00') and (uchar <= '\u9fa5'):
        return True
    else:
        return False


def judge_contain_chinese(str1):
    """
    judge contain chinese or not
    Args:
        str1: str  utf-8

    Returns: True(have chinese)   False (not have chinese)

    """
    try:
        for str_t in str1:
            if is_chinese(str_t):
                return True
        return False
    except Exception:
        logger.error('judge contain chinese error:%s' % traceback.format_exc())
        return False


def init_dev_test(_type):
    '''
    初始化测试边缘
    '''
    all_list = []
    all_dict = {}
    with open('/Application/bermuda3/conf/test_dev', 'r') as r:
        for i in r.readlines():
            hostname, _ip, h_type = i.split()
            if _type in h_type:
                if hostname != 'CNC-DT-3-3WW':
                    continue
                all_list.append({'name':hostname, 'host': _ip, 'type': h_type})
                all_dict[hostname] = {'name':hostname, 'host': _ip, 'type': h_type}

    return all_list, all_dict


def get_mongo_str(str_number, num):
    """

    Args:
        str_number: str(ObjectId)
        num: the num of mongo

    Returns:str  the number of mongo

    """
    try:
        int_10 = int('0x' + str_number[:8], 16)
        return_t = int_10 % int(num)
        return str(return_t)
        # print int_10
    except Exception:
        logger.debug("get_mongo_str error :%s" % traceback.format_exc())

def sortip(ip_list):
    ip_list.sort(lambda x,y: cmp(''.join([i.rjust(3, '0') for i in x.split('.')]), ''.join([i.rjust(3, '0') for i in y.split('.')])))
    return ip_list


def md5(src):
    m2 = hashlib.md5()
    m2.update(src)
    return m2.hexdigest()

def get_dev_infobyip(dev_ip):
    url='http://j.hope.chinacache.com:8200/api/device/ip/'+dev_ip+'/apps'
    request = urllib.request.Request(url)
    request.add_header('X-HOPE-Authn','hope')
    response = urllib.request.urlopen(request)
    d=json.loads(response.read())
    if d["status"]==0 and len(d['data'])!= 0:
        dic=d['data']
        return dic[0].get('devName', 'ceshi'),dic[0].get('devCode', 'ceshi')
    else:
        dev_name=''
        return dev_name


def judge_dev_ForH_byip(dev_ip):
    res=get_dev_infobyip(dev_ip)
    result = 'UNKNOWN'
    if res:
        dev_code=res[1]
        request = urllib.request.Request('http://j.hope.chinacache.com:8200/api/device/'+dev_code+'/deviceBaseInfo')
        request.add_header('X-HOPE-Authn','hope')
         #response = urllib.request.urlopen(request)
        try:
            response = urllib.request.urlopen(request, timeout=5)
        except:
            return
        d=json.loads(response.read())
        if d['status']==0:
            data = d['data']['mrtgs']
            str1_find='HPCC'
            str2_find='FC'
            for y in data:
                #print y
                if str1_find in y:
                    result='HPCC'
                elif str2_find in y:
                    result='FC'
                    break
                else:
                    continue
        else:
            return result
        return result
    else:
        return result
def get_channel_code(channel):
    code = 0
    try:
        requrl = "https://cms3-apir.chinacache.com/apir/9040/qryChnInfo"
        data_orig = {
            "ROOT": {
                "BODY": {
                    "BUSI_INFO": {
                        "CHN_NAME":channel# "http://resource.alilo.com.cn"
                    }
                },
                "HEADER": {
                    "AUTH_INFO": {
                        "FUNC_CODE": "",
                        "LOGIN_NO": "",
                        "LOGIN_PWD": "",
                        "OP_NOTE": ""
                    }
                }
            }
        }
        headers = {'Content-Type': 'application/json'}
        req = urllib.request.Request(url=requrl, headers=headers, data=json.dumps(data_orig))
        #print req
        res_data = urllib.request.urlopen(req)
        result_data = res_data.read()
        result_dict = json.loads(result_data)
        code =  result_dict["ROOT"]["BODY"]["OUT_DATA"]["extnId"]

        domain_all = PHYSICAL_URL.get(PHYSICAL_URL_key)
        if domain_all:
            domain_dict = json.loads(domain_all)
            domain_dict[channel] = code
        else:
            domain_dict = {channel: code}

        PHYSICAL_URL.set(PHYSICAL_URL_key, json.dumps(domain_dict))

    except Exception:
        logger.debug("get channel code error {}".format(traceback.format_exc()))
    return code
def getcode_from_redis(domain):
    code = 0
    try:
        domain_all = PHYSICAL_URL.get(PHYSICAL_URL_key)
        domain_dict = json.loads(domain_all)
        code = domain_dict[domain]
    except Exception:
        logger.debug("get code from redis error {}".format(traceback.format_exc()))
    return code
def get_uuid():
    return uuid.uuid1().hex
if __name__ == '__main__':

    #get_max_receiver_count(datetime.datetime.now())
    #print get_current_date_str()
    #print get_active_devices()
    #print is_refresh_high_priority(18908)
    print(get_email_list_by_type('faild_device'))
    get_mongo_str('10000001aaaaaaa', '4')
