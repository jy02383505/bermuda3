#!/bin/bash
cd /Application/bermuda3

file="/Application/bermuda3/logs/retry.log"
NOW=$(date  '+%Y-%m-%d %T')
mtime=`stat -c %Y $file`
current=`date '+%s'`
((halt=$current - $mtime))


if ps -ef | grep retryd | grep -v grep; then 
    if [[ $halt -gt 100 ]]
    then
            echo "$NOW - retryd halted at `stat -c %y $file`"
            echo "$NOW - killing retryd"
            echo "`date  '+%Y-%m-%d %T'` killing retryd"
            pid=`ps -eo pid,cmd|grep retryd |awk '{print $1}'`
            echo kill $pid
            echo "$NOW - starting retry"
            ./bin/retryd
    else
            pid1=`ps -ef | grep retryd | grep -v grep | head -1 | awk '{print $2}'`
            echo "retryd is running!  main process id = $pid1"
    fi
else
    echo "retryd is running ..."
    #./bin/retryd
    ./bin/retryd
fi