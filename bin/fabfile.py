# -*- coding:utf-8 -*-
from fabric.api import env, put, run, cd

# 使用远程命令的用户名
env.user = 'refresh'
# 执行命令的服务器


def deploy_test():
    env.hosts = ['223.202.40.159', '223.202.40.142']

def deploy_174():
    env.hosts = ['58.68.228.146', '58.68.228.174', '58.68.228.197', '58.68.228.192']


def deploy_133():
    env.hosts = ['58.68.228.178', '58.68.228.143', '58.68.228.219', '58.68.228.133']


def deploy_198():
    env.hosts = ['58.68.228.198']


def deploy_all():
    env.hosts = ['58.68.228.146', '58.68.228.174', '58.68.228.197', '58.68.228.192', '58.68.228.178', '58.68.228.143', '58.68.228.219', '58.68.228.133']


# def upload(*args):
#     for filename in args:
#         put(filename, "/Application/bermuda-4.5.4.3.dev-r68635/core")


def upload_html(*args):
    for filename in args:
        put(filename, "/Application/bermuda3/static/html")


def restart_celery():
    run('/etc/init.d/celery.d restart')


def stop_celery():
    run('/etc/init.d/celery.d stop')


# def install_bermuda():
#     with cd('/Application/bermuda-4.5.4.3.dev-r68635/'):
#         run('/Application/bermuda3/bin/python setup.py install')


def restart_fastcgi():
    with cd('/Application/bermuda3'):
        run('./restart.sh')


def tail_log(*args):
    env.warn_only = True
    with cd('/Application/bermuda3/logs'):
        for log in args:
            run('tail %s' % log)


def grep_log(log_file, keyword):
    env.warn_only = True
    with cd('/Application/bermuda3/logs'):
        run("grep '%s' %s" % (keyword, log_file))


def set_ssh():
    env.user = 'root'
    run('mkdir -p /home/refresh/.ssh')
    run('cp /root/.ssh/authorized_keys /home/refresh/.ssh/')
    run('chown -R refresh:refresh /home/refresh/.ssh')
    run('service sshd restart')
