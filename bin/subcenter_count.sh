#!/bin/bash
cd /Application/bermuda3

# file="/Application/bermuda3/logs/subcenter_countd.log"
# NOW=$(date  '+%Y-%m-%d %T')
# mtime=`stat -c %Y $file`
# current=`date '+%s'`
# ((halt=$current - $mtime))


if ps -ef | grep subcenter_countd | grep -v grep; then
     pid1=`ps -ef | grep subcenter_countd | grep -v grep | head -1 | awk '{print $2}'`
     echo "subcenter_countd is running!  main process id = $pid1"
else
    echo "subcenter_countd is running ..."
    ./bin/subcenter_countd
fi