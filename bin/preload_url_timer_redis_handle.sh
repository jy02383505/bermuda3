#!/bin/bash
cd /Application/bermuda3
# file="/Application/bermuda3/logs/preload_url_timer.log"
# NOW=$(date  '+%Y-%m-%d %T')
# mtime=`stat -c %Y $file`
# current=`date '+%s'`
# ((halt=$current - $mtime))

if ps ax |grep -v 'grep'|grep  -c 'preload_url_timer_redis_handled'; then
            echo "$NOW - killing preload_url_timer_redis_handled"
            echo "`date  '+%Y-%m-%d %T'` killing preload_url_timer_redis_handled"
            pid=`ps -eo pid,cmd|grep preload_url_timer_redis_handled | grep -v 'grep' |awk '{print $1}'`
            echo kill -9 $pid
            kill -9 $pid
            echo "$NOW - starting preload_url_timer_redis_handle"
            ./bin/preload_url_timer_redis_handled
else
    echo "preload_url_timer_redis_handled will be running ..."
    ./bin/preload_url_timer_redis_handled
fi