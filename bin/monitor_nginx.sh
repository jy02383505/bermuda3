#!/bin/bash
s=`sleep 1|telnet localhost 80|awk '{print $4}'`x

if [[ $s != x ]]
then
    echo "`date  '+%Y-%m-%d %T'` Nginx is active!"
else
    echo "`date  '+%Y-%m-%d %T'` Nginx is down!"
    if ps -ef | grep nginx | grep -v grep; then
        pid=`ps -eo pid,cmd|grep nginx|awk '{print $1}'`
        echo "`date  '+%Y-%m-%d %T'` killing nginx"
        echo kill $pid
    fi
    echo "`date  '+%Y-%m-%d %T'` start nginx"
    /usr/local/nginx/sbin/nginx
fi