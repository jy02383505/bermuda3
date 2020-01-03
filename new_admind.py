# -*- coding:utf-8 -*-
from multiprocessing import Process

from flup.server.fcgi import WSGIServer

from core.config import config
from new_admin.app import app


def server(num):
    WSGIServer(app, bindAddress=(config.get('server', 'host'), 8091 + num)).run()

def main():
    """
    管理系统入口

    """
    for i in range(5):
        Process(target=server, args=(i,)).start()


if __name__ == '__main__':
    main()
    #app.run(host=config.get('server', 'host'), port=8089)
