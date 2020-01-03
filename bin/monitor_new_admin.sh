#!/bin/bash

a=`ps -ef|grep new_admind|grep -v grep |awk '{print $2}'`x

if [ $a != x ];
then
    echo "`date  '+%Y-%m-%d %T'` new_admin is active!"
else
    echo "`date  '+%Y-%m-%d %T'` new_admin is down!"
    echo "`date  '+%Y-%m-%d %T'` start new_admin"
    nohup /Application/bermuda3/bin/new_admind > /dev/nell 2>&1 &
fi
