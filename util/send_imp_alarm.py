# encoding=utf-8
import urllib.request, urllib.error, urllib.parse
import json
import datetime

def send_imp(to_addrs,title,body):
    #requrl = 'http://223.202.202.209:8900/api/v1.0/thirdparty/events'#测试url
    requrl = 'http://imp.chinacache.com:8900/api/v1.0/thirdparty/events'  # 正式url
    data_orig = {
        "target":"{}".format(datetime.datetime.now()), #告警对象
        "metric": "refresh.url.error",  #监控项
        "tags": {
            "to_addrs":"{}".format(to_addrs)
            #监控标签
        },
        "source": "bermuda",  #告警事件来源
        "status": 0,              #0：告警  1：恢复
        "value": "503,502,501",           #告警值，如果多个可以英文逗号分隔
        #"timestamp": 123456789,   #时间戳
        "ttl":3600*24*2,               #生存时间
        "emails": [               #告警接收邮箱
            #"pengfei.hao@chinacache.com"
        ],
       "phones": [               #告警短信接收人
            # "13812345678",
            # "13888888888"
        ],
        "notice_count": 1,        #告警次数
        "context": [              #告警上下文
            {
                "key": "content",
                "value": "refresh.error"
            }
        ],
        "note":"{}".format(body)
    }
    headers = {'Content-Type': 'application/json'}
    req = urllib.request.Request(url=requrl, headers=headers, data=json.dumps(data_orig))
    #print req
    res_data = urllib.request.urlopen(req)
    print(res_data.read())


if __name__ =="__main__":
    send_imp()