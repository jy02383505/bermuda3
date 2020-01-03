from flask import Flask,request
from flask import jsonify
from flup.server.fcgi import WSGIServer
from multiprocessing import Process
from datetime import datetime
import simplejson as json
import urllib.request, urllib.parse, urllib.error,hashlib
        
        
app = Flask(__name__)
        
REFRESH_ROOT = 'https://r.chinacache.com/content/refresh'
ADAPTER_CALLBACK = 'http://61.182.132.219:8090/adapter/snda_callback'
REPORT_URL = 'http://116.211.20.45/api/refresh?cdn_id=1005'
    
        
@app.route('/')
def hello_world():
    return "Hello World!"
    
@app.route('/adapter/snda_refresh', methods=['GET', 'POST'])
def receiver_snda_proload():
    try:
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        time = request.form.get('time', '') 
        print('request %s with {user:%s,remote_addr:%s}' % (request.path, username, request.remote_addr))
        verify_snda(username, password, time)
        task = load_task(request.form.get("task", "{}"))
        post_data = { 'username': username, 'password': 'ptyy@snda.com' , 'task':task }
        params = urllib.parse.urlencode(post_data)
        response = urllib.request.urlopen( REFRESH_ROOT , params )
        return response.read()
    except InputError as e:
        return jsonify({"success": False, "message": e.__str__()}),403

@app.route('/adapter/snda_refresh/<rid>', methods=['GET', 'POST'])
def search(rid):
    try:
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        print('request %s with {user:%s,remote_addr:%s}' % (request.path, username, request.remote_addr))
        time = request.form.get('time', '')
        verify_snda(username, password, time)
        post_data = { 'username': username, 'password': 'ptyy@snda.com' }
        params = urllib.parse.urlencode(post_data)
        response = urllib.request.urlopen( REFRESH_ROOT+ '/' +rid + '?%s' % params )
        return response.read()
    except InputError as e:
        return jsonify({"success": False, "message": e.__str__()}),403

@app.route('/adapter/snda_callback', methods=['GET', 'POST'])
def callback():
        rid = json.loads(request.data).get('request_id')
        post_data = { 'username': 'snda', 'password': 'ptyy@snda.com' }
        params = urllib.parse.urlencode(post_data)
        response = urllib.request.urlopen( REFRESH_ROOT+ '/' +rid + '?%s' % params )
        data = {}
        data['username'] = 'snda'
        data['data'] = response.read()
        data['time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        data['password'] = hashlib.md5('snda' + 'qetsfh!3' + data.get('time')).hexdigest()
        print(REPORT_URL)
        print(urllib.parse.urlencode(data))
        r = urllib.request.urlopen( REPORT_URL , urllib.parse.urlencode(data))
        print(r.read())
        return 'ok',200
def verify_snda(username, password, time):
    KEY = username + 'qetsfh!3' + time
    md5 = hashlib.md5(KEY.encode('utf-8'))
    print(md5.hexdigest())
    if password != md5.hexdigest():
        raise InputError(403, "WRONG_PASSWORD")

def load_task(task):
    try:
        transform = json.loads(task)
        transform['callback'] = {"url":ADAPTER_CALLBACK,"email":[],"acptNotice":True}
        return json.dumps(transform)
    except Exception:
        raise InputError(500,"The schema of task is error.")

class InputError(Exception):

    def __init__(self, code, error_info):
        self.code = code
        self.error_info = error_info

    def __str__(self):
        return self.error_info

    def __code__(self):
        return self.code

def main():
    for i in range(5):
        Process(target=server, args=(i,)).start()

def server(num):
    WSGIServer(app, bindAddress=('127.0.0.1',5000 + num)).run()

if __name__ == '__main__':
    #app.run()
    main()