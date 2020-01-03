#!/bin/bash
cd /Application/bermuda3


# file="/Application/bermuda3/logs/check_url_autodesk.log"
# NOW=$(date  '+%Y-%m-%d %T')
# mtime=`stat -c %Y $file`
# current=`date '+%s'`
# ((halt=$current - $mtime))


if ps -ef | grep check_url_autodeskd | grep -v grep; then 
     pid1=`ps -ef | grep check_url_autodeskd | grep -v grep | head -1 | awk '{print $2}'`
     echo "check_url_autodeskd is running!  main process id = $pid1"
else
    echo "check_url_autodeskd is running ..."
    ./bin/check_url_autodeskd
fi