#!/bin/bash
cd /Application/bermuda3

# file="/Application/bermuda3/logs/update_redis_channel_customer.log"
# NOW=$(date  '+%Y-%m-%d %T')
# mtime=`stat -c %Y $file`
# current=`date '+%s'`
# ((halt=$current - $mtime))


if ps -ef | grep update_redis_channel_customerd | grep -v grep; then
     pid1=`ps -ef | grep update_redis_channel_customerd | grep -v grep | head -1 | awk '{print $2}'`
     echo "update_redis_channel_customerd is running!  main process id = $pid1"
else
    echo "update_redis_channel_customerd will be running ..."
    ./bin/update_redis_channel_customerd
fi