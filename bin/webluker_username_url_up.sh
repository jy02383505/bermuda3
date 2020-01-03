#!/bin/bash
cd /Application/bermuda3

# file="/Application/bermuda3/logs/webluker_username_url_up.log"
# NOW=$(date  '+%Y-%m-%d %T')
# mtime=`stat -c %Y $file`
# current=`date '+%s'`
# ((halt=$current - $mtime))


if ps -ef | grep webluker_username_url_upd | grep -v grep; then
     pid1=`ps -ef | grep webluker_username_url_upd | grep -v grep | head -1 | awk '{print $2}'`
     echo "webluker_username_url_upd is running!  main process id = $pid1"
else
    echo "webluker_username_url_upd will be running ..."
    ./bin/webluker_username_url_upd
fi