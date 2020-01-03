#!/bin/bash
cd /Application/bermuda3


# file="/Application/bermuda3/logs/count_device_status_preload_alld.log"
# NOW=$(date  '+%Y-%m-%d %T')
# mtime=`stat -c %Y $file`
# current=`date '+%s'`
# ((halt=$current - $mtime))


if ps -ef | grep count_device_status_preload_alld | grep -v grep; then
     pid1=`ps -ef | grep count_device_status_preload_alld | grep -v grep | head -1 | awk '{print $2}'`
     echo "count_device_status_preload_alld is running!  main process id = $pid1"
else
    echo "count_device_status_preload_alld is running ..."
    ./bin/count_device_status_preload_alld
fi