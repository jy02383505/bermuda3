#!/bin/bash
cd /Application/bermuda3
if ps ax |grep -v 'grep'|grep  -c 'preload_url_timer_pulld'; then
            echo "$NOW - killing preload_url_timer_pulld"
            echo "`date  '+%Y-%m-%d %T'` killing preload_url_timer_pull"
            pid=`ps -eo pid,cmd|grep preload_url_timer_pulld | grep -v 'grep' |awk '{print $1}'`
            echo kill -9 $pid
            kill -9 $pid
            echo "$NOW - starting preload_url_timer_pulld"
            ./bin/preload_url_timer_pulld
else
    echo "preload_url_timer_pulld will be running ..."
    ./bin/preload_url_timer_pulld
fi