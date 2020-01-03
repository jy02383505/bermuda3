#!/bin/bash
cd /Application/bermuda3
# file="/Application/bermuda3/logs/subcenter_result.log"
# NOW=$(date  '+%Y-%m-%d %T')
# mtime=`stat -c %Y $file`
# current=`date '+%s'`
# ((halt=$current - $mtime))

if ps ax |grep -v 'grep'|grep  -c 'subcenter_resultd'; then
            echo "$NOW - killing postal_rd"
            echo "`date  '+%Y-%m-%d %T'` killing subcenter_resultd"
            pid=`ps -eo pid,cmd|grep subcenter_resultd | grep -v 'grep' |awk '{print $1}'`
            echo kill -9 $pid
            kill -9 $pid
            echo "$NOW - starting subcenter update"
            ./bin/subcenter_resultd
else
    echo "subcenter update will be running ..."
    ./bin/subcenter_resultd
fi