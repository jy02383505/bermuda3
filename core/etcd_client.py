#!/usr/bin/env python
# coding=utf-8
# Created by vance on 2016-07-01.
__author__ = 'vance'
__doc__ = """"""
__ver__ = '1.0'

import etcd
from util import log_utils
from .config import config
# import requests
import socket
import traceback

HOST = config.get('etcd_server', 'host')
PORT = config.get('etcd_server', 'port')
DIR = "/subcenter/"

logger = log_utils.get_celery_Logger()

try:
    client = etcd.Client(host=HOST, port=int(PORT), allow_redirect=False)
    print(client.stats)
except Exception:
    logger.error(traceback.format_exc())
    # HOST = config.get('etcd_server', 'host_bak')
    # PORT = config.get('etcd_server', 'port_bak')
    # client = etcd.Client(host=HOST, port=int(PORT), allow_redirect=False)

# client = etcd.Client(host="223.202.52.82", port=2379, allow_redirect=False)


def valid_ip(address):
    try:
        socket.inet_aton(address)
        return True
    except:
        return False

def get_subcenters():
    """
    :return: {'BGP-BJ-C-5Hb': '192.168.1.2:21109', 'centos6': '192.168.47.146'}
    """
    subcenter_dir = {}
    try:
        # data = requests.get("http://223.202.52.82:2379/v2/keys/subcenter/")
        # print data.text
        # client.write("subcenter/BGP-BJ-C-5HG", "192.168.1.1:21109", ttl=600)

        for node in client.read(DIR).children:
            val = node.value.encode('utf-8')
            try:
                ip, port = val.split(":")
                if valid_ip(ip):
                    subcenter_dir[node.key.split("/")[2].encode('utf-8')] = val
            except:pass

        logger.debug(subcenter_dir)
        return subcenter_dir
    except etcd.EtcdKeyNotFound:
        logger.warning("subcenters not found")
    except Exception:
        logger.error(traceback.format_exc())

if __name__ == '__main__':
    get_subcenters()
