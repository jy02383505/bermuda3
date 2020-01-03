#!/bin/bash
cd /Application/bermuda3


# file="/Application/bermuda3/logs/count_device_status_all.log"
# NOW=$(date  '+%Y-%m-%d %T')
# mtime=`stat -c %Y $file`
# current=`date '+%s'`
# ((halt=$current - $mtime))


if ps -ef | grep count_devicesd | grep -v grep; then
     pid1=`ps -ef | grep count_devicesd | grep -v grep | head -1 | awk '{print $2}'`
     echo "count_devicesd is running!  main process id = $pid1"
else
    echo "count_devicesd is running ..."
    ./bin/count_devicesd
fi