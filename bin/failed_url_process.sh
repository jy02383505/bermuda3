#!/bin/bash
cd /Application/bermuda3

# file="/Application/bermuda3/logs/failed_url_process.log"
# NOW=$(date  '+%Y-%m-%d %T')
# mtime=`stat -c %Y $file`
# current=`date '+%s'`
# ((halt=$current - $mtime))


if ps -ef | grep failed_url_processd | grep -v grep; then
     pid1=`ps -ef | grep failed_url_processd | grep -v grep | head -1 | awk '{print $2}'`
     echo "failed_url_processd is running!  main process id = $pid1"
else
    echo "failed_url_processd will be running ..."
    ./bin/failed_url_processd
fi