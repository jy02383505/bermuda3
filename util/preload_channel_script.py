#! -*- coding=utf-8 -*-
"""
@version: ??
@author: rubin
@license:
@contact: longjun.zhao@chinacache.com
@site: 
@software: PyCharm
@file: preload_channel_script.py
@time: 16-11-8 上午11:18
"""
import xlrd
import logging
import traceback
from core import redisfactory, rcmsapi
from core.database import query_db_session,db_session
from datetime import datetime
import sys



PRELOAD_DEVS = redisfactory.getDB(5)
db = db_session()
# LOG_FILENAME = '/Application/bermuda3/logs/autodesk_postal.log'
LOG_FILENAME = '/home/rubin/logs/preload_channel_script.log'

# logging.basicConfig(filename=LOG_FILENAME,
#                     format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s',
#                     level=logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(process)d - Line:%(lineno)d - %(message)s")
fh = logging.FileHandler(LOG_FILENAME)
fh.setFormatter(formatter)

logger = logging.getLogger('preload_channel_script')
logger.addHandler(fh)
logger.setLevel(logging.DEBUG)


def open_excel(file='jingdong.xlsx'):
    """

    :param file:
    :return:
    """
    try:
        data = xlrd.open_workbook(file)
        return data
    except Exception:
        logger.debug("read xml file error:%s" % traceback.format_exc())


def excep_table_byindex(file='jingdong.xlsx', colnameindex=0, by_index=0):
    """

    :param file: the file of excel
    :param colnameindex:
    :param by_index:
    :return:
    """
    data = open_excel(file)
    table = data.sheets()[by_index]
    nrows = table.nrows  # the number of rows
    # ncols = table.ncols  # the number of ncols
    # colonames = table.row_values(colnameindex)  # get data of rows
    try:

        for rownum in range(0, nrows):
            row = table.row_values(rownum)
            # if row:
            #     for i in range(len(colonames)):
            #         print row[i]
            username = str(row[0]).strip()
            channel = str(row[1]).strip()
            logger.debug('username:%s, channel:%s' % (username, channel))
            add_channel(username, channel)


    except Exception:
        logger.debug('parse data error:%s' % traceback.format_exc())





def add_channel(username, channel):
    """

    :param username:
    :param channel:
    :return:
    """
    bool_result, content = judge_channel_is_not_need(username, channel)
    bool_result_n, content_n = judge_channel_is_not_need_all(username, channel)
    if bool_result:
        insert_content = {
            'username':username, 'channel_name': channel, 'channel_code': content.get('code'),
            'type': 0, 'has_callback': 0, 'callback': {'url': '', 'email': []}, 'is_live': 0,
            'config_count': 500, 'created_time': datetime.now()
        }
        try:
            db.preload_channel.insert_one(insert_content)
            logger.debug('insert prelod_channel success username:%s, channel:%s' % (username, channel))
        except Exception:
            logger.debug('insert preload_channel error:%s' % e)
            return
        # insert into redis
        CHANNEL_CODE = insert_content["channel_name"]
        CONFIG_COUNT = insert_content["config_count"]
        PRELOAD_DEVS.set(CHANNEL_CODE, CONFIG_COUNT)
        logger.debug('complete channel insertion')
        logger.debug('start insert device, all device')
        args = {
            'channel_code': insert_content['channel_code'], 'channel_name': channel,
            'username': username
        }
        unopend_device = get_devs_unopened(args)
        devs_t = []
        if unopend_device:
            for dev_t in unopend_device:
                #  only hanndle first layer device
                if dev_t.get('firstLayer') == True:
                    devs_t.append({'username': username, 'channel_name': channel, 'channel_code': content.get('code'),
                                   'status': 'OPEN', 'name': dev_t.get('name'), 'host': dev_t.get('host'),
                                   'firstLayer': True})
            try:
                db.preload_config_device.insert(devs_t)
                logger.debug('insert preload_config_device success content:%s' % devs_t)
            except Exception:
                logger.debug('insert preload_config_device error:%s, username:%s, channel:%s' % (e, username, channel))
            logger.debug('insert preload_config_device end')
    elif bool_result_n:

        logger.debug('start insert device, all device')
        args = {
            'channel_code': content_n.get('code'), 'channel_name': channel,
            'username': username
        }
        unopend_device = get_devs_unopened(args)
        devs_t = []
        if unopend_device:
            for dev_t in unopend_device:
                #  only hanndle first layer device
                if dev_t.get('firstLayer') == True:
                    devs_t.append({'username':username, 'channel_name': channel, 'channel_code': content_n.get('code'),
                                   'status': 'OPEN', 'name': dev_t.get('name'), 'host': dev_t.get('host'),
                                   'firstLayer': True})
            try:
                db.preload_config_device.insert(devs_t)
                logger.debug('bool_result_n insert preload_config_device success content:%s' % devs_t)
            except Exception:
                logger.debug('bool_result_n insert preload_config_device error:%s, username:%s, channel:%s'
                             % (e, username, channel))
            logger.debug('bool_result_n insert preload_config_device end')







def judge_channel_is_not_need(username, channel):
    """
    判断频道是否在没有配置之列，如果没有配置就可以配置，否则，不能进行配置
    :param username:
    :param channel:
    :return:
    """
    unopended_channel = get_channels_unopened(username)
    logger.debug('judge_channel  unponeded_channel:%s' % unopended_channel)
    if unopended_channel:
        for unopen in unopended_channel:
            if channel == unopen.get('name'):
                logger.debug('this channel can open username:%s, channel:%s' % (username, channel))
                return True, unopen
    logger.debug('this channel can not open, not in unopen list, username:%s, channel:%s' % (username, channel))

    return False, None



def get_channels_unopened(username):
    """
    返回没有配置的频道
    :param username:
    :return:
    """
    logger.debug("get_channels_unopened username %s " % username)
    channels = rcmsapi.get_channels(username)
    opened_channels = [c.get("channel_name") for c in db.preload_channel.find({"username": username})]
    # logger.debug('get_channels_upopened username:%s, channels:%s' % (username, channels))
    # print channels
    return [channel for channel in channels if channel.get("name") not in opened_channels]


def judge_channel_is_not_need_all(username, channel):
    """

    :param username:
    :param channel:
    :return:
    """
    unopended_channel = get_all_channels(username)
    logger.debug('judge_channel  unponeded_channel:%s' % unopended_channel)
    if unopended_channel:
        for unopen in unopended_channel:
            if channel == unopen.get('name'):
                logger.debug('this channel can open username:%s, channel:%s' % (username, channel))
                return True, unopen
    logger.debug('this channel can not open, not in unopen list, username:%s, channel:%s' % (username, channel))

    return False, None


def get_all_channels(username):
    """

    :param username:
    :return:
    """
    logger.debug('get_channels_unopend username %s' % username)
    channels = rcmsapi.get_channels(username)
    return [channel for channel in channels]


def get_devs_unopened(args):
    # dev_name = args.pop("dev_name")

    rcms_devs = [dev for dev in rcmsapi.getFirstLayerDevices(args.get("channel_code")) + rcmsapi.getDevices(args.get("channel_code"))  if dev.get("status") == "OPEN"]
    # if dev_name:
    #     rcms_devs = [ dev for dev in rcms_devs if dev.get("name") == dev_name ]

    opened_devs = [dev.get("name") for dev in db.preload_config_device.find(args)]
    return [dev for dev in rcms_devs if dev.get("name") not in opened_devs]



def test_get_devs_unopened():
    args = {'channel_code': '28444'}
    rcms_devs = [dev for dev in rcmsapi.getFirstLayerDevices(args.get("channel_code")) + rcmsapi.getDevices(args.get("channel_code"))  if dev.get("status") == "OPEN"]
    print(rcms_devs)




if __name__ == "__main__":
    # excep_table_byindex()
    # get_channels_unopened('163web')
    # test_get_devs_unopened()
    filename = ''
    try:
        if sys.argv[1]:
            filename = sys.argv[1]
            print('file location:%s' % filename)
            logger.debug('file location:%s' % filename)
        else:
            print('请增加文件位置')
    except Exception:
        print('请输入一个参数，文件位置')
        logger.debug('请输入一个参数，文件位置')



    excep_table_byindex(filename)
