#!/bin/bash
cd /Application/bermuda3

# file="/Application/bermuda3/logs/staticsitc_preload_urld.log"
# NOW=$(date  '+%Y-%m-%d %T')
# mtime=`stat -c %Y $file`
# current=`date '+%s'`
# ((halt=$current - $mtime))


if ps -ef | grep staticsitc_preload_urld | grep -v grep; then
     pid1=`ps -ef | grep staticsitc_preload_urld | grep -v grep | head -1 | awk '{print $2}'`
     echo "staticsitc_preload_urld is running!  main process id = $pid1"
else
    echo "staticsitc_preload_urld is running ..."
    ./bin/staticsitc_preload_urld
fi