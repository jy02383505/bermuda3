import time
import datetime
import json
from core.database import s1_db_session
from core import redisfactory

CERT_PULL_CACHE = redisfactory.getDB(1)
db = s1_db_session()
def run():
    db.cert_update_pull.ensure_index('update_time', unique=True)
    transfer_cert = []
    add_certs = []
    t = int(time.strftime('%Y%m%d'))  # t=20171212
    g = str(t - 1)
    l = str(t)
    data = db.cert_detail.find({'created_time': {"$gte": datetime.datetime(int(g[0:4]), int(g[4:6]), int(g[6:8])),
                                                 "$lte": datetime.datetime(int(l[0:4]), int(l[4:6]), int(l[6:8]))}})
    for d in data:
        co = {'cert': d.get('cert', ''), 'p_key': d.get('p_key', ''), 's_name': d.get('save_name'),
              'task_id': d.get('save_name', ''), 'seed': d.get('seed', ''), 'op_type': d.get('op_type', ''),
              's_dir': "/usr/local/hpc/conf/ssl"}
        add_certs.append(co)
    transfer_data = db.transfer_certs_detail.find({'created_time': {
        "$gte": datetime.datetime(int(g[0:4]), int(g[4:6]), int(g[6:8])),
        "$lte": datetime.datetime(int(l[0:4]), int(l[4:6]), int(l[6:8]))}})
    for t in transfer_data:
        command = {'o_path': t.get('o_path', ''), 'd_path': t.get('d_path', ''), 's_name': t.get('save_name'),
                   'task_id': t.get('save_name', '')}
        transfer_cert.append(command)
    info = {"transfer_cert": transfer_cert, "add_cert": add_certs}
    r = CERT_PULL_CACHE
    t = time.strftime('%Y%m%d')
    print(type(t))
    r.hset("update_res", int(t), json.dumps(info))
    try:
        db.cert_update_pull.insert(
            {"update_time": int(time.strftime('%Y%m%d')), "transfer_cert": transfer_cert, "add_cert": add_certs})
    except Exception:
        print(e)
if __name__ == "__main__":
    run()