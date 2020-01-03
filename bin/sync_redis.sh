#!/bin/sh
cd /Application/bermuda3

NOW=$(date  '+%Y-%m-%d %T')
kill_ps() {
    if ps ax |grep -v 'grep'|grep  -c 'sync_redis.sh';
    then
        echo "$NOW - killing sync_redis.sh $1"
        if [ $1 = 'rcms' ];then
          echo 'rcms'
          pid=`ps -eo pid,cmd|grep 'sync_redis.sh rcms'|grep -v 'grep' |awk '{print $1}'`
        else
          echo 'portal'
          pid=`ps -eo pid,cmd|grep 'sync_redis.sh portal'|grep -v 'grep' |awk '{print $1}'`
        fi
        echo kill -9 $pid
        #kill -9 $pid
    fi
}
start_sync_from_rcms() {
	echo "$NOW starting start_sync_from_rcms"
	./bin/sync_rcmsd
}
start_sync_from_rcms_all() {
	echo "$NOW starting start_sync_from_rcms"
	./bin/sync_all_rcmsd
}
start_sync_from_portal() {
	echo "$NOW starting start_sync_from_portal"
	./bin/sync_portald
}

case "$1" in
	rcms)
	    if ps ax |grep -v 'grep'|grep  -c 'sync_rcmsd';
        then
            pid=`ps -eo pid,cmd|grep 'sync_rcmsd'| grep -v 'grep' |awk '{print $1}'`
            echo "$NOW -kill -9 before sync_rcmsd"
            kill -9 $pid
        fi
		start_sync_from_rcms
	;;
	rcms_all)
	    if ps ax |grep -v 'grep'|grep  -c 'sync_all_rcmsd';
        then
            pid=`ps -eo pid,cmd|grep 'sync_all_rcmsd'| grep -v 'grep' |awk '{print $1}'`
            echo "$NOW -kill -9 before sync_all_rcmsd"
            kill -9 $pid
        fi
		start_sync_from_rcms_all
	;;
	portal)
	    if ps ax |grep -v 'grep'|grep  -c 'sync_portald';
        then
            pid=`ps -eo pid,cmd|grep 'sync_portald'| grep -v 'grep' |awk '{print $1}'`
            echo "$NOW -kill -9 before sync_portald"
            kill -9 $pid
        fi
		start_sync_from_portal
	;;

	*)
		echo "Usage: /sync_redis.sh (rcms) or (portal)"
		exit 1
	;;  
esac

exit 0
