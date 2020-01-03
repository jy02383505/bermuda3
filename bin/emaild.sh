#!/bin/bash
cd /Application/bermuda3

if ps ax |grep -v 'grep'|grep  -c 'emaild'; then
            echo "$NOW - killing emaild"
            echo "`date  '+%Y-%m-%d %T'` killing emaild"
            pid=`ps -eo pid,cmd|grep emaild | grep -v 'grep' |awk '{print $1}'`
            echo kill -9 $pid
            kill -9 $pid
            echo "$NOW - starting emaild"
            ./bin/emaild
else
    echo "emaild will be running ..."
    ./bin/emaild
fi