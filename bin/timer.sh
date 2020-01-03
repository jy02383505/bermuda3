#!/bin/bash
cd /Application/bermuda3
if ps ax |grep -v 'grep'|grep  -c 'timerd'; then
            echo "$NOW - killing timerd"
            echo "`date  '+%Y-%m-%d %T'` killing timerd"
            pid=`ps -eo pid,cmd|grep timerd | grep -v 'grep' |awk '{print $1}'`
            echo kill -9 $pid
            kill -9 $pid
            echo "$NOW - starting timer"
            ./bin/timerd
else
    echo "timerd will be running ..."
    ./bin/timerd
fi