#!/bin/bash
cd /Application/bermuda3


# file="/Application/bermuda3/logs/check_url_autodesk.log"
# NOW=$(date  '+%Y-%m-%d %T')
# mtime=`stat -c %Y $file`
# current=`date '+%s'`
# ((halt=$current - $mtime))


if ps -ef | grep autodesk_failed_emaild | grep -v grep; then
     pid1=`ps -ef | grep autodesk_failed_emaild | grep -v grep | head -1 | awk '{print $2}'`
     echo "autodesk_failed_emaild is running!  main process id = $pid1"
else
    echo "autodesk_failed_emaild will be running ..."
    ./bin/autodesk_failed_emaild
fi