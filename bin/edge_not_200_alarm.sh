#!/bin/bash
cd /Application/bermuda3

if ps ax |grep -v 'grep'|grep  -c 'edge_not_200_alarmd'; then
            echo "$NOW - killing edge_not_200_alarmd"
            echo "`date  '+%Y-%m-%d %T'` killing edge_not_200_alarm"
            pid=`ps -eo pid,cmd|grep edge_not_200_alarmd | grep -v 'grep' |awk '{print $1}'`
            echo kill -9 $pid
            kill -9 $pid
            echo "$NOW - starting edge_not_200_alarmd"
            ./bin/edge_not_200_alarmd
else
    echo "edge_not_200_alarmd will be running ..."
    ./bin/edge_not_200_alarmd
fi