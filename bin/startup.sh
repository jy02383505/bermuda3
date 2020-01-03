#!/bin/sh

current_user=`whoami`
py_version='py366'
pyenv_path="/home/${current_user}/.pyenv/versions/${py_version}/bin"

cd /Application/bermuda3
start_receiver() {
    echo "receiverd is running ..."
    nohup ${pyenv_path}/receiverd > /dev/null 2>&1 &
}

stop_receiver() {
	echo "`date  '+%Y-%m-%d %T'` killing receiverd"
	pid=`ps -eo pid,cmd|grep -v grep|grep receiverd|awk '{print $1}'`
	echo kill -9 $pid
	kill -9 $pid
}


start_rep() {
    echo "rep is running ..."
    nohup ${pyenv_path}/gunicorn receiverd_g:app -c /Application/bermuda3/conf/gunicorn_config.py > /dev/null 2>&1 &
}


stop_rep() {
    echo "`date  '+%Y-%m-%d %T'` killing rep"
    pid=`ps -eo pid,cmd|grep -v grep|grep gunicorn|awk '{print $1}'`
    echo kill -9 $pid
    kill -9 $pid
}


start_admin() {
    echo "admin is running ..."
    nohup ${pyenv_path}/new_admind > /dev/null 2>&1 &
}

stop_admin() {
	echo "`date  '+%Y-%m-%d %T'` killing admind"
	pid=`ps -eo pid,cmd|grep -v grep|grep new_admind|awk '{print $1}'`
	echo kill -9 $pid
	kill -9 $pid
}

start_duowan_monitord() {
    echo "duowan_monitord is running ..."
    nohup ${pyenv_path}/duowan_monitord > /dev/null 2>&1 &
}

start_monitord() {
    echo "monitord is running ..."
    nohup ${pyenv_path}/monitord > /dev/null 2>&1 &
}

stop_monitord() {
	echo "`date  '+%Y-%m-%d %T'` killing monitord"
	pid=`ps -eo pid,cmd|grep -v grep|grep monitord|awk '{print $1}'`
	echo kill -9 $pid
	kill -9 $pid
}

stop_duowan_monitord() {
	echo "`date  '+%Y-%m-%d %T'` killing duowan_monitord"
	pid=`ps -eo pid,cmd|grep -v grep|grep duowan_monitord|awk '{print $1}'`
	echo kill -9 $pid
	kill -9 $pid
}

start_retry_beated() {
    echo "retry_beated is running ..."
    nohup ${pyenv_path}/retry_beated > /dev/null 2>&1 &
}

stop_retry_beated() {
	echo "`date  '+%Y-%m-%d %T'` killing retry_beated"
	pid=`ps -eo pid,cmd|grep -v grep|grep retry_beated|awk '{print $1}'`
	echo kill -9 $pid
	kill -9 $pid
}

start_celery_monitord() {
    echo "celery monitord is running ..."
    nohup ${pyenv_path}/celery_monitord > /dev/null 2>&1 &
}

stop_celery_monitord() {
	echo "`date  '+%Y-%m-%d %T'` killing celery monitord"
	pid=`ps -eo pid,cmd|grep -v grep|grep celery_monitord|awk '{print $1}'`
	echo kill -9 $pid
	kill -9 $pid
}

case "$1" in
	rep-start)
		start_rep
	;;
	
	rep-stop)
		stop_rep
	;;
	receiver-start)
		start_receiver
	;;
	
	receiver-stop)
		stop_receiver
	;;
	
	receiver-restart)
		stop_receiver
		start_receiver
	;;	
	
	admin-start)
		start_admin
	;;
	
	admin-stop)
		stop_admin
	;;
	
	admin-restart)
		stop_admin
		start_admin
	;;
	
	duowan-start)
		start_duowan_monitord
	;;
	
	duowan-stop)
		stop_duowan_monitord
	;;
	
	duowan-restart)
		stop_duowan_monitord
		start_duowan_monitord
	;;

	retryBeated-start)
		start_retry_beated
	;;
	
	retryBeated-stop)
		stop_retry_beated
	;;
	
	retryBeated-restart)
		stop_retry_beated
		start_retry_beated
	;;
	celery-monitord-start)
		start_celery_monitord
	;;
	celery-monitord-stop)
		stop_celery_monitord
	;;

	service-all-start)
		start_receiver
		start_admin
	;;

	service-all-stop)
		stop_receiver
		stop_admin
	;;

	service-all-restart)
		stop_receiver
		stop_admin
		start_receiver
		start_admin
	;;

	monitor-all-start)
		start_duowan_monitord
		start_retry_beated
		start_monitord
	;;

	monitor-all-stop)
		stop_duowan_monitord
		stop_retry_beated
		stop_monitord
	;;

	monitor-all-restart)
		stop_retry_beated
		stop_monitord
		start_retry_beated
		start_monitord
		
	;;	

	*)
        echo "Usage: /startup.sh {receiver-[start|stop|restart]} or {rep-[start|stop]} or (admin-[start|restart|stop]) or (service-all-[start|restart|stop]) or (monitor-all-[start|restart|stop]) or (celery-monitord-[start|stop])"
		exit 1
	;;  
esac

exit 0
