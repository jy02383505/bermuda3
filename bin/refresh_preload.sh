#!/bin/bash
cd /Application/bermuda3

# file="/Application/bermuda3/logs/refresh_preload_update.log"
# NOW=$(date  '+%Y-%m-%d %T')
# mtime=`stat -c %Y $file`
# current=`date '+%s'`
# ((halt=$current - $mtime))


if ps -ef | grep refresh_preload_updated | grep -v grep; then
     pid1=`ps -ef | grep refresh_preload_updated| grep -v grep | head -1 | awk '{print $2}'`
     echo "refresh_preload_updated is running!  main process id = $pid1"
else
    echo "refresh_failed_emaild will be running ..."
    ./bin/refresh_preload_updated
fi