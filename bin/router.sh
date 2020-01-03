#!/bin/bash
cd /Application/bermuda3

# file="/Application/bermuda3/logs/router.log"
# NOW=$(date  '+%Y-%m-%d %T')
# mtime=`stat -c %Y $file`
# current=`date '+%s'`
# ((halt=$current - $mtime))


if ps -ef | grep routerd | grep -v grep; then 
     pid1=`ps -ef | grep routerd | grep -v grep | head -1 | awk '{print $2}'`
     echo "routerd is running!  main process id = $pid1"
else
    echo "routerd is running ..."
    nohup ./bin/routerd &
fi