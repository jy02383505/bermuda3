# coding=utf-8
import sys
import os
import multiprocessing


LOG_PATH = "/Application/bermuda3/logs"

path_of_current_file = os.path.abspath(__file__)
path_of_current_dir = os.path.split(path_of_current_file)[0]

_file_name = os.path.basename(__file__)

sys.path.insert(0, path_of_current_dir)

worker_class = 'gevent'
workers = multiprocessing.cpu_count() * 2 + 1

chdir = path_of_current_dir

worker_connections = 10000
timeout = 30
max_requests = 20000
graceful_timeout = 30
capture_output = True
#forwarded-allow-ips = "*"

loglevel = 'debug'

reload = True
debug = True

bind = "%s:%s" % ("0.0.0.0", 8080)
pidfile = '%s/%s.pid' % (LOG_PATH, 'gunicorn_rece')
errorlog = '%s/%s_error.log' % (LOG_PATH, "gunicorn_rece")
accesslog = '%s/%s_access.log' % (LOG_PATH, "gunicorn_rece")




