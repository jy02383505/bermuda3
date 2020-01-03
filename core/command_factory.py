# -*- coding:utf-8 -*-
__author__ = 'cl'

import simplejson as json
from xml.dom.minidom import parseString
from core.config import initConfig
import uuid,logging
from util import log_utils
import traceback

# logger = logging.getLogger('command')
# logger.setLevel(logging.DEBUG)

logger = log_utils.get_postal_Logger()

config = initConfig()

def get_command_json(urls, action, dev, check_conn=False):
    '''
    组装下发json
    '''
    logger.debug('get_command_json urls: %s|| dev: %s' % (urls, dev))
    json_obj = {}
    try:
        sid = uuid.uuid1().hex
        json_obj['sessionid'] = sid
        json_obj['action'] = action
        json_obj['lvs_address'] = dev.get('host')
        json_obj['report_address'] = config.get("server","preload_report")
        json_obj['is_override'] = 1
        json_obj['switch_m3u8'] = dev.get('parse_m3u8_f', False) if dev.get('firstLayer') else dev.get('parse_m3u8_nf', False)
        for url in urls:
            if not url.get('compressed'):
                if not 'url_list' in json_obj:
                    json_obj['url_list'] = []
                bowl = json_obj['url_list']
            else:
                if not 'compressed_url_list' in json_obj:
                    json_obj['compressed_url_list'] = []
                bowl = json_obj['compressed_url_list']
            url_id = str(url.get('_id'))
            _url = url.get('url')
            md5_value = url.get("md5")
            tmp = {}
            tmp['id'] = url_id
            tmp['url'] = _url
            tmp['origin_remote_ip'] = url.get('remote_addr')
            tmp['priority'] = url.get('priority')
            tmp['nest_track_level'] = url.get('nest_track_level')
            tmp['check_type'] = url.get('check_type')
            tmp['limit_rate'] = url.get('get_url_speed')
            tmp['preload_address'] = url.get('preload_address')
            tmp['header_list'] = url.get('header_list')
            if md5_value:
                if check_conn:
                    tmp.update({'conn': url.get('conn_num', 0) if dev.get('type') == 'FC' else 0, 'rate': url.get('single_limit_speed', 0), 'check_value': md5_value})
                else:
                    tmp.update({'check_value': md5_value})
            else:
                if check_conn:
                    tmp.update({'conn': url.get('conn_num', 0) if dev.get('type') == 'FC' else 0, 'rate': url.get('single_limit_speed', 0)})
            bowl.append(tmp)

        logger.debug('get_command_json json_obj: %s' % json_obj)
    except Exception:
        logger.debug('get_command_json except: %s' % traceback.format_exc())
    return json.dumps(json_obj)


def get_command(urls, action, dev_ip, conn_num=0, speed=0, test=0):
    """
    组装下发格式
    :param urls:
    :param action:
    :return:
    """

    hasCompressedUrl = False
    hasNonCompressedUrl = False
    logger.debug('test:%s' % test)
    logger.debug("conn_num:%s, speed:%s" % (conn_num, speed))
    try:
        sid = uuid.uuid1().hex
        command_str = '<preload_task sessionid="%s">' % sid
        command_str += '<action>%s</action>' % action
        command_str += '<priority>%s</priority>' % urls[0].get("priority")
        command_str += '<nest_track_level>%s</nest_track_level>' % urls[0].get("nest_track_level")
        command_str += '<check_type>%s</check_type>' % urls[0].get("check_type")
        # send the md5 field to the edge device   package to the xml file
        md5_value = urls[0].get("md5")
        if md5_value:
            command_str += '<check_value>%s</check_value>' % md5_value
        else:
             command_str += '<check_value>%s</check_value>' % (str("-"))
        command_str += '<limit_rate>%s</limit_rate>' % urls[0].get("get_url_speed")
        command_str += '<preload_address>%s</preload_address>' % urls[0].get("preload_address")
        command_str += '<lvs_address>%s</lvs_address>' % dev_ip
        command_str += '<report_address need="yes">%s</report_address>' % config.get("server","preload_report")
        command_str += '<is_override>1</is_override>'
        command_str += '</preload_task>'
        content = parseString(command_str)
        url_list = parseString('<url_list></url_list>')
        compressed_url_list = parseString('<compressed_url_list></compressed_url_list>')
        for url in urls:
            if not url.get('compressed'):
                if not hasNonCompressedUrl:
                    hasNonCompressedUrl = True
                uelement = content.createElement('url')
                uelement.setAttribute('id', str(url.get('_id')))
                if speed:
                    uelement.setAttribute('conn', str(conn_num))
                    uelement.setAttribute('rate', str(speed))
                uelement.appendChild(content.createTextNode(url.get('url')))
                url_list.documentElement.appendChild(uelement)
            else:
                if not hasCompressedUrl:
                    hasCompressedUrl = True
                uelement = content.createElement('url')
                uelement.setAttribute('id', str(url.get('_id')))
                if speed:
                    uelement.setAttribute('conn', str(conn_num))
                    uelement.setAttribute('rate', str(speed))
                uelement.appendChild(content.createTextNode(url.get('url')))
                compressed_url_list.documentElement.appendChild(uelement)
        if hasNonCompressedUrl:
            content.documentElement.appendChild(url_list.documentElement)
        if hasCompressedUrl:
            content.documentElement.appendChild(compressed_url_list.documentElement)
        logger.debug(content.toxml('utf-8'))
        return content.toxml('utf-8')
    except Exception:
        logger.debug('get_command except: %s' % traceback.format_exc())



def re_handle_command(command):
    from . import preload_worker
    try:
        from xml.dom import  minidom
        root = minidom.parseString(command).documentElement
        sid = uuid.uuid1().hex
        command_str = '<preload_task sessionid="%s">' % sid
        command_str += '<action>%s</action>' % preload_worker.get_nodevalue(preload_worker.get_xmlnode(root, 'action')[0])
        command_str += '<priority>%s</priority>' % preload_worker.get_nodevalue(preload_worker.get_xmlnode(root, 'priority')[0])
        command_str += '<nest_track_level>%s</nest_track_level>' % preload_worker.get_nodevalue(preload_worker.get_xmlnode(root, 'nest_track_level')[0])
        command_str += '<check_type>%s</check_type>' % preload_worker.get_nodevalue(preload_worker.get_xmlnode(root, 'check_type')[0])
        command_str += '<limit_rate>%s</limit_rate>' % preload_worker.get_nodevalue(preload_worker.get_xmlnode(root, 'limit_rate')[0])
        command_str += '<preload_address>%s</preload_address>' % preload_worker.get_nodevalue(preload_worker.get_xmlnode(root, 'preload_address')[0])
        command_str += '<report_address need="yes">%s</report_address>' % preload_worker.get_nodevalue(preload_worker.get_xmlnode(root, 'report_address')[0])
        command_str += '<is_override>1</is_override>'
        command_str += '</preload_task>'
        content = parseString(command_str)
        url_list = parseString('<url_list></url_list>')
        for url in preload_worker.get_xmlnode(root, 'url_list'):
            uelement = content.createElement('url')
            uelement.setAttribute('id', str(preload_worker.get_attrvalue(preload_worker.get_xmlnode(url,'url')[0],'id')))
            uelement.appendChild(content.createTextNode(preload_worker.get_firstChild(url,'url')))
            url_list.documentElement.appendChild(uelement)
        content.documentElement.appendChild(url_list.documentElement)
        return content.toxml('utf-8')
    except Exception:
        logger.debug('re_handle_command except: %s' % traceback.format_exc())
