#!/bin/bash
cd /Application/bermuda3


file="/Application/bermuda3/logs/device_type.log"
NOW=$(date  '+%Y-%m-%d %T')
mtime=`stat -c %Y $file`
current=`date '+%s'`
((halt=$current - $mtime))


if ps -ef | grep device_typed | grep -v grep; then
    if [[ $halt -gt 100 ]]
    then
            echo "$NOW - device_typed halted at `stat -c %y $file`"
            echo "$NOW - killing device_typed"
            echo "`date  '+%Y-%m-%d %T'` killing retryd"
            pid=`ps -eo pid,cmd|grep device_typed |awk '{print $1}'`
            echo kill $pid
            echo "$NOW - starting retry"
            ./bin/device_typed
    else
            pid1=`ps -ef | grep device_typed | grep -v grep | head -1 | awk '{print $2}'`
            echo "device_typed is running!  main process id = $pid1"
    fi
else
    echo "device_typed is running ..."
    #./bin/retryd
    ./bin/device_typed
fi