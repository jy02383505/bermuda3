#!/bin/bash
cd /Application/bermuda3
# file="/Application/bermuda3/logs/postal_r.log"
# NOW=$(date  '+%Y-%m-%d %T')
# mtime=`stat -c %Y $file`
# current=`date '+%s'`
# ((halt=$current - $mtime))

if ps ax |grep -v 'grep'|grep  -c 'postal_rd'; then
            echo "$NOW - killing postal_rd"
            echo "`date  '+%Y-%m-%d %T'` killing postal_rd"
            pid=`ps -eo pid,cmd|grep postal_rd | grep -v 'grep' |awk '{print $1}'`
            echo kill -9 $pid
            kill -9 $pid
            echo "$NOW - starting timer"
            ./bin/postal_rd
else
    echo "postal_rd will be running ..."
    ./bin/postal_rd
fi