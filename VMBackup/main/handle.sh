#!/usr/bin/env sh
pwdcommand=`pwd`
pwdstr="$pwdcommand"
output=`cat $pwdstr'/HandlerEnvironment.json'`
outputstr="$output"
poststr=${outputstr#*logFolder\"}
postsubstr=${poststr#*\"}
postsubstr1=${postsubstr#*\"}
resultstrlen=`expr ${#postsubstr} - 1 - ${#postsubstr1}`
logfolder=$(echo $postsubstr | cut -b 1-$resultstrlen)
logfile=$logfolder'/shell.log'

rc=3
arc=0

pythonProcess=$(ps -ef | grep waagent | grep python)
pythonPath=$(echo "${pythonProcess}" | head -n1 | awk '{print $8;}')

if [ "$1" = "install" ]
then
    if [ -f "/etc/azure/workload.conf" ]
    then
		WorkloadConfEdited=`awk '/(workload_name)([ ]*[=])([ ]*[(^|\")a-zA-Z(^|\")])/' /etc/azure/workload.conf`
		if [ "$WorkloadConfEdited" != "" ]
			then
				#Workload.conf is edited
				echo "`date -u`- The command is $1, exiting without conf file copy" >> $logfile
			else
				#workload.conf is not edited
				cp main/workloadPatch/WorkloadUtils/workload.conf /etc/azure/workload.conf
				echo "`date -u`- The command is $1, exiting with conf file copy" >> $logfile	
		fi
    else
        mkdir -p /etc/azure
        cp main/workloadPatch/WorkloadUtils/workload.conf /etc/azure/workload.conf
        echo "`date -u`- The command is $1, exiting with conf file copy" >> $logfile
    fi

	python3Loc=`command -v python3`
	if [ ! -z $python3Loc ]; then
		echo "$(date -u) - Python3 found" >> $logfile
		sed -i "s#ExecStart=/usr/bin/python.*#ExecStart=/usr/bin/python3 $(pwd)/main/handle.py lrdaemon#g" \
			main/systemd/MsftAzureSnapshotExt.service
	else
		sed -i "s#ExecStart=/usr/bin/python.*#ExecStart=/usr/bin/python $(pwd)/main/handle.py lrdaemon#g" \
			main/systemd/MsftAzureSnapshotExt.service
	fi

	mkdir -p "/etc/systemd/system"
	if [ -f "/etc/systemd/system/MsftAzureSnapshotExt.service" ]; then
		systemd stop MsftAzureSnapshotExt.service
		cp "main/systemd/MsftAzureSnapshotExt.service" "/etc/systemd/system/MsftAzureSnapshotExt.service"
		systemd daemon-reload
	else
		cp "main/systemd/MsftAzureSnapshotExt.service" "/etc/systemd/system/MsftAzureSnapshotExt.service"
		systemd daemon-reload
	fi
    exit $arc

elif [ "$1" = "lrdaemon" ]; then
	systemctl stop MsftAzureSnapshotExt.service
	systemctl start MsftAzureSnapshotExt.service
	rc=$?
	exit $rc

elif [ "$1" != "enable"  ] && [ "$1" != "daemon" ]
then
    echo "`date -u`- The command is $1, exiting" >> $logfile
    exit $arc
fi

configSeqNo="$(echo `printenv ConfigSequenceNumber`)"
if [ -z ${configSeqNo} ]
then
	configSeqNo='seqNo:-1'
	echo "`date -u`- ConfigSequenceNumber not found in environment variable ${configSeqNo}" >> $logfile
else
	configSeqNo='seqNo:'$configSeqNo
	echo "`date -u`- ConfigSequenceNumber from environment variable ${configSeqNo}" >> $logfile
fi

pythonVersionList="python3.8 python3.7 python3.6 python3.5 python3.4 python3.3 python3 python2.7 python2.6 python2 python"

for pythonVersion in ${pythonVersionList};
do
	cmnd="/usr/bin/${pythonVersion}"
	if [ -f "${cmnd}" ]
    then
		echo "`date -u`- ${pythonVersion} path exists" >> $logfile
		$cmnd main/handle.py -$configSeqNo -$1
		rc=$?
	fi
	if [ $rc -eq 0 ]
	then
		break
	fi
done

if [ $rc -ne 0 ] && [ -f "`which python`" ]
then
	echo "`date -u`- python path exists" >> $logfile
	/usr/bin/env python main/handle.py -$configSeqNo -$1
	rc=$?
fi

if [ $rc -ne 0 ] && [ -f "${pythonPath}" ]
then
	echo "`date -u`- python path exists" >> $logfile
	$pythonPath main/handle.py -$configSeqNo -$1
	rc=$?
fi
	
if [ $rc -eq 3 ]
then
	echo "`date -u`- python version unknown" >> $logfile
fi

echo "`date -u`- $rc returned from handle.py" >> $logfile

exit $rc
