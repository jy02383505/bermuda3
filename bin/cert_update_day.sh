#!/bin/bash
cd /Application/bermuda3


# file="/Application/bermuda3/logs/count_device_status_all.log"
# NOW=$(date  '+%Y-%m-%d %T')
# mtime=`stat -c %Y $file`
# current=`date '+%s'`
# ((halt=$current - $mtime))


if ps -ef | grep cert_update_dayd | grep -v grep; then
     pid1=`ps -ef | grep cert_update_dayd | grep -v grep | head -1 | awk '{print $2}'`
     echo "cert_update_dayd is running!  main process id = $pid1"
else
    echo "cert_update_dayd is running ..."
    ./bin/cert_update_dayd
fi