#!/bin/bash
cd /Application/bermuda3
file="/Application/bermuda3/logs/report.log"
NOW=$(date  '+%Y-%m-%d %T')
mtime=`stat -c %Y $file`
current=`date '+%s'`
((halt=$current - $mtime))


if ps -ef | grep reportd | grep -v grep; then
    if [[ $halt -gt 300 ]]
    then
            echo "$NOW - reportd halted at `stat -c %y $file`"
            echo "$NOW - killing reportd"
            echo "`date  '+%Y-%m-%d %T'` killing reportd"
            pid=`ps -eo pid,cmd|grep reportd |awk '{print $1}'`
            echo kill $pid
            echo "$NOW - starting reportd"
            ./bin/reportd
    else
            pid1=`ps -ef | grep reportd | grep -v grep | head -1 | awk '{print $2}'`
    		echo "reportd is running!  main process id = $pid1"
    fi
else
    echo "reportd is running ..."
    ./bin/reportd
fi