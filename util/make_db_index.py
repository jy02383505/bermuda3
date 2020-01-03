# coding=utf-8
from pymongo import MongoClient, ASCENDING, DESCENDING, IndexModel
#db = MongoClient("mongodb://bermuda:bermuda_refresh@223.202.52.82/bermuda", 27018)['bermuda']
db = MongoClient("mongodb://bermuda:bermuda_refresh@101.251.97.254/bermuda", 27017)['bermuda']

#callback
db.callback.create_index("task_id")
print('callback add ok')

#device
db.device.create_index("url_id")
db.device.create_index([("created_time", DESCENDING)], expireAfterSeconds=604800)
print('device add ok')

#preload_channel
preload_channel_index1 = IndexModel([("username", ASCENDING)])
preload_channel_index2 = IndexModel([("channel_code", ASCENDING)])
preload_channel_index3 = IndexModel([("is_live", ASCENDING)])
preload_channel_index4 = IndexModel([("channel_name", ASCENDING)])
preload_channel_index5 = IndexModel([("has_callback", ASCENDING)])
preload_channel_index6 = IndexModel([("username", ASCENDING),("channel_name",ASCENDING)])
db.preload_channel.create_indexes([preload_channel_index1,preload_channel_index2,preload_channel_index3,preload_channel_index4,preload_channel_index5,preload_channel_index6])
print('preload_channel add ok')

#preload_config_device
preload_config_device_index1 = IndexModel([("username",ASCENDING)])
preload_config_device_index2 = IndexModel([("channel_code",ASCENDING)])
preload_config_device_index3 = IndexModel([("channel_name",ASCENDING)])
preload_config_device_index4 = IndexModel([("username", ASCENDING),("channel_name",ASCENDING)])
db.preload_config_device.create_indexes([preload_config_device_index1, preload_config_device_index2, preload_config_device_index3, preload_config_device_index4])
print('preload_config_device add ok')

#preload_dev
preload_dev_index1 = IndexModel([("created_time",DESCENDING)])
db.preload_dev.create_indexes([preload_dev_index1])
print('preload_dev add ok')

#preload_error_task
preload_error_task_index1 = IndexModel([("last_retrytime",DESCENDING)], expireAfterSeconds=604800)
preload_error_task_index2 = IndexModel([("host",ASCENDING)])
preload_error_task_index3 = IndexModel([("url_id",ASCENDING),("host",ASCENDING)])
preload_error_task_index4 = IndexModel([("type",ASCENDING),("host",ASCENDING),("last_retrytime",ASCENDING)])
db.preload_error_task.create_indexes([preload_error_task_index1, preload_error_task_index2, preload_error_task_index3, preload_error_task_index4])
print('preload_error_task add ok')

#preload_url
preload_url_index1 = IndexModel([("status",ASCENDING),("start_time",DESCENDING)])
preload_url_index2 = IndexModel([("task_id",ASCENDING),("username",ASCENDING)])
preload_url_index3 = IndexModel([("username",ASCENDING)])
preload_url_index4 = IndexModel([("task_id",ASCENDING)])
preload_url_index5 = IndexModel([("username",ASCENDING),("created_time",DESCENDING)])
preload_url_index6 = IndexModel([("channel_code",ASCENDING)])
preload_url_index7 = IndexModel([("created_time",DESCENDING)])
db.preload_url.create_indexes([eval("preload_url_index%s" %i) for i in range(1,8)])
print('preload_url add ok')

#preload_user
db.preload_user.create_index('user_id')
print('preload_user add ok')

#ref_err
ref_err_index1 = IndexModel([("datetime",DESCENDING)], expireAfterSeconds=604800)
ref_err_index2 = IndexModel([("uid",ASCENDING)])
ref_err_index3 = IndexModel([("username",ASCENDING)])
ref_err_index4 = IndexModel([("failed.code",ASCENDING)])
ref_err_index5 = IndexModel([("channel_code",ASCENDING)])
db.ref_err.create_indexes([eval("ref_err_index%s" %i) for i in range(1,6)])
print('ref_err add ok')

#request
request_index1 = IndexModel([("username",ASCENDING)])
request_index2 = IndexModel([("username",ASCENDING),("created_time",DESCENDING)])
request_index3 = IndexModel([("created_time",DESCENDING)], expireAfterSeconds=604800)
request_index4 = IndexModel([("parent",ASCENDING),("created_time",DESCENDING)])
db.request.create_indexes([eval("request_index%s" %i) for i in range(1,5)])
print('request add ok')

#statistical_preload
db.statistical_preload.create_index('date')
print('statistical_preload add ok')

#url
url_index1 = IndexModel([("username",ASCENDING)])
url_index2 = IndexModel([("r_id",ASCENDING)])
url_index3 = IndexModel([("url",ASCENDING)])
url_index4 = IndexModel([("status",ASCENDING)])
url_index5 = IndexModel([("isdir",ASCENDING)])
url_index6 = IndexModel([("dev_id",ASCENDING)])
url_index7 = IndexModel([("channel_code",ASCENDING)])
url_index7 = IndexModel([("channel_name",ASCENDING)])
url_index8 = IndexModel([("username",ASCENDING),("created_time",DESCENDING)])
url_index9 = IndexModel([("parent",ASCENDING)])
url_index10 = IndexModel([("created_time",DESCENDING)],expireAfterSeconds=432000)
db.url.create_indexes([eval("url_index%s" %i) for i in range(1,11)])
print('url ok')


#device_urls_day
device_urls_day_index1 = IndexModel([("hostname", ASCENDING),("datetime",DESCENDING)], expireAfterSeconds=604800)
db.device_urls_day.create_indexes([device_urls_day_index1])

#refresh_high_priority
db.refresh_high_priority.create_index('channel_code', unique=True)

#email_management
db.email_management.create_index([('failed_type',ASCENDING),('devices',ASCENDING),], unique=True)

#retry_branch_xml
retry_branch_xml_index1 = IndexModel([("create_time",DESCENDING)], expireAfterSeconds=432000)
db.retry_branch_xml.create_indexes([retry_branch_xml_index1])

#retry_device_branch
retry_device_branch_index1 = IndexModel([("create_time",DESCENDING)], expireAfterSeconds=432000)
retry_device_branch_index2 = IndexModel([("rid",ASCENDING)])
db.retry_device_branch.create_indexes([retry_device_branch_index1, retry_device_branch_index2])

