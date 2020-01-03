from multiprocessing import Process
from logging import Formatter
import logging
from util import log_utils
from flup.server.fcgi import WSGIServer
from werkzeug.contrib.fixers import ProxyFix
from  receiver import receiver
from core.config import config

app = receiver.r_app
app.wsgi_app = ProxyFix(app.wsgi_app)
