'''
Created on 2012-7-2

@author: wenwen
'''
import subprocess, threading , time, traceback
from datetime import datetime
#from pymongo import ReplicaSetConnection
from pymongo import MongoClient
import re,urllib.request,urllib.error,urllib.parse
from subprocess import Popen, PIPE

# Try and reduce the stack size.
try:
    threading.stack_size(409600)
except:
    pass

import logging
logging.basicConfig(format = '%(asctime)s %(levelname)s - %(message)s', filename = '/Application/bermuda3/logs/mq_agent.log')

def getServerName():
    try:
        server_name = re.search('\d+\.\d+\.\d+\.\d+',urllib.request.urlopen('http://www.whereismyip.com').read()).group(0)
    except:
        try :
            server_name = re.search('\d+\.\d+\.\d+\.\d+',Popen('ifconfig', stdout=PIPE).stdout.read()).group(0)
        except:
            server_name = "localhost"
    return server_name

class Agent(threading.Thread):
    def __init__(self , db):
        self.db = db
        threading.Thread.__init__(self)

    def run(self):
        cmd = "/usr/local/rabbitmq/sbin/rabbitmqctl  list_queues name messages_ready"
        while True:
            try:
                data = []
                time.sleep(120)
                p = subprocess.Popen(cmd, shell = True, close_fds = True, stdout = subprocess.PIPE, stderr = subprocess.PIPE)
                stdoutdata, stderrdata = p.communicate()
                if p.returncode:
                    logging.error("cmd error: %s" % (stderrdata,))
                else:
                    result = stdoutdata.split("\n")[1:-2]
                    for r in result:
                        q_name, messages_ready = r.split("\t")
                        data.append({"name": q_name, "m_ready": int(messages_ready)})
                        self.db.mq_status.save({'_id':getServerName(), 'status':data , 'update_time':datetime.now()})
            except Exception:
                    logging.error(traceback.format_exc())

if __name__ == "__main__":
    agent = Agent(MongoClient('%s:27017,%s:27017,%s:27017' % ('10.68.228.236', '10.68.228.232', '10.68.228.190'), replicaSet = 'bermuda_db')['bermuda'])
    agent.setName('mq_agent')
    agent.setDaemon(True)
    agent.run()
