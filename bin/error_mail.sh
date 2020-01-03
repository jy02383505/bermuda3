#!/bin/bash
cd /Application/bermuda3

if ps ax |grep -v 'grep'|grep  -c 'error_maild'; then
            echo "$NOW - killing error_maild"
            echo "`date  '+%Y-%m-%d %T'` killing error_maild"
            pid=`ps -eo pid,cmd|grep error_maild | grep -v 'grep' |awk '{print $1}'`
            echo kill -9 $pid
            kill -9 $pid
            echo "$NOW - starting error_maild"
            ./bin/error_maild
else
    echo "error_maild will be running ..."
    ./bin/error_maild
fi