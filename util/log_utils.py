#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging.config
import os


log_dir = os.path.join("/Application/bermuda3", "logs")
if not os.path.exists(log_dir):
    os.mkdir(log_dir)

logging.config.fileConfig("/Application/bermuda3/conf/logging.conf")
logger = logging.getLogger("root")
logger_receiver = logging.getLogger("receiver")
logger_celery = logging.getLogger("celery")
logger_router = logging.getLogger("router")
logger_rcms = logging.getLogger("rcms")
logger_postal = logging.getLogger("postal")
logger_admin = logging.getLogger("admin")
logger_pcelery = logging.getLogger("pcelery")
logger_preload = logging.getLogger("preload")
logger_rtime = logging.getLogger("rtime")
logger_cert = logging.getLogger("cert")
logger_cert_worker = logging.getLogger("cert_worker")
logger_cert_postal = logging.getLogger("cert_postal")
logger_cert_query_postal = logging.getLogger("cert_query_postal")
logger_cert_query_worker = logging.getLogger("cert_query_worker")
logger_transfer_cert_postal = logging.getLogger("transfer_cert_postal")
logger_transfer_cert_worker = logging.getLogger("transfer_cert_worker")
logger_redis = logging.getLogger("redis")
logger_refresh_result=logging.getLogger("refresh_result")


def getLogger():
    return logger


def get_receiver_Logger():
    return logger_receiver


def get_celery_Logger():
    return logger_celery


def get_router_Logger():
    return logger_router


def get_rcms_Logger():
    return logger_rcms

def get_redis_Logger():
    return logger_redis


def get_postal_Logger():
    return logger_postal

def get_admin_Logger():
    return logger_admin

def get_preload_Logger():
    return logger_preload

def get_pcelery_Logger():
    return logger_pcelery

def get_rtime_Logger():
    return logger_rtime

def get_cert_Logger():
    return logger_cert

def get_cert_worker_Logger():
    return logger_cert_worker

def get_cert_postal_Logger():
    return logger_cert_postal
def get_cert_query_worker_Logger():
    return logger_cert_query_worker

def get_cert_query_postal_Logger():
    return logger_cert_query_postal

def get_logger_refresh_result():
    return logger_refresh_result

def get_transfer_cert_worker_Logger():
    return logger_transfer_cert_worker

def get_transfer_cert_postal_Logger():
    return logger_transfer_cert_postal
