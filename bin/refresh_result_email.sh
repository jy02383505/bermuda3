#!/bin/bash
cd /Application/bermuda3

# file="/Application/bermuda3/logs/refresh_result.log"
# NOW=$(date  '+%Y-%m-%d %T')
# mtime=`stat -c %Y $file`
# current=`date '+%s'`
# ((halt=$current - $mtime))


if ps -ef | grep refresh_result_emaild | grep -v grep; then
     pid1=`ps -ef | grep refresh_result_emaild | grep -v grep | head -1 | awk '{print $2}'`
     echo "refresh_result_email is running!  main process id = $pid1"
else
    echo "refresh_result_email is running ..."
    ./bin/refresh_result_emaild
fi