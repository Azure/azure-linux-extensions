#!/usr/bin/env sh
pwdstr=`pwd`
output=`cat $pwdstr'/HandlerEnvironment.json'`
outputstr="$output"
poststr=${outputstr#*logFolder\"}
postsubstr=${poststr#*\"}
postsubstr1=${postsubstr#*\"}
resultstrlen=`expr ${#postsubstr} - 1 - ${#postsubstr1}`
logfolder=$(echo $postsubstr | cut -b 1-$resultstrlen)
logfile=$logfolder'/shell.log'
rc=3
PIDFILE="directsnapshot.pid"

if [ -e $PIDFILE ]; then
	pid=`cat $PIDFILE`
	pid=$(ps --pid $pid | tail -1 | awk '{ print $1 }')
	# echo $pid
	if echo $pid | grep -Eq '^[0-9]+$'; then
		echo "Process already exists"
		exit 0
	else
		rm $PIDFILE
	fi
fi

pythonVersionList="python3.8 python3.7 python3.6 python3.5 python3.4 python3.3 python3 python2.7 python2.6 python2 python"

for pythonVersion in ${pythonVersionList};
do
	cmnd="/usr/bin/${pythonVersion}"
	if [ -f "${cmnd}" ]; then
		echo "[$(date -u +"%F %H:%M:%S:%N")] ${pythonVersion} path exists" >> $logfile
		nohup $cmnd main/handle_host_daemon.py &
		pid=$(ps --pid $! | tail -1 | awk '{ print $1 }')
		echo $pid | tee $PIDFILE
		if echo $pid | grep -Eq '^[0-9]+$'; then
			rc=0
		fi
	fi
	if [ $rc -eq 0 ]
	then
		break
	fi
done

if [ $rc -ne 0 ] && [ -f "`which python`" ]
then
	echo "[$(date -u +"%F %H:%M:%S:%N")] python path exists" >> $logfile
	nohup /usr/bin/env python main/handle_host_daemon.py &
	pid=$(ps --pid $! | tail -1 | awk '{ print $1 }')
	echo $pid | tee $PIDFILE
	if echo $pid | grep -Eq '^[0-9]+$'; then
		rc=0
	fi
fi

if [ $rc -ne 0 ] && [ -f "${pythonPath}" ]
then
	echo "[$(date -u +"%F %H:%M:%S:%N")] python path exists" >> $logfile
	nohup $pythonPath main/handle_host_daemon.py &
	pid=$(ps --pid $! | tail -1 | awk '{ print $1 }')
	echo $pid | tee $PIDFILE
	if echo $pid | grep -Eq '^[0-9]+$'; then
		rc=0
	fi
fi
	
if [ $rc -eq 3 ]
then
	echo "[$(date -u +"%F %H:%M:%S:%N")] python version unknown" >> $logfile
fi

echo "[$(date -u +"%F %H:%M:%S:%N")] $rc returned from handle_host_daemon.py" >> $logfile

exit $rc