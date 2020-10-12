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

if [ "$1" = "install" ]
then
    if [ -f "/etc/azure/workload.conf" ]
    then
<<<<<<< HEAD
		WorkloadConfEdited=`awk '/(workload_name)([ ]*[=])([ ]*[(^|\")a-zA-Z(^|\")])/' /etc/azure/workload.conf`
		if [ "$WorkloadConfEdited" != "" ]
			then
				#Workload.conf is edited
				echo "`date`- The command is $1, exiting without conf file copy" >> $logfile
			else
				#workload.conf is not edited
				cp main/workloadPatch/WorkloadUtils/workload.conf /etc/azure/workload.conf
				echo "`date`- The command is $1, exiting with conf file copy" >> $logfile	
		fi
=======
        cat "/etc/azure/workload.conf" | while read line
        do 
            if [ $skip < 2 ]
            then
                let "skip+=1"
            elif [ $line == *"workload_name"* ]
            then
                if [ $line == *"mysql"* ] || [ $line == *"oracle"* ]
                then
                    echo "`date`- The command is $1, exiting without conf file copy" >> $logfile
                    break
                elif [ $line != *"mysql"* ] && [ $line != *"oracle"* ]
                then
                    cp main/workloadPatch/WorkloadUtils/workload.conf /etc/azure/workload.conf
                    echo "`date`- The command is $1, exiting with conf file copy" >> $logfile
                    break
                fi
            fi
        done
>>>>>>> ca05fcbdddfc7bfa96b3c6c700d38ae6738b102b
        exit $arc
    else
        mkdir -p /etc/azure
        cp main/workloadPatch/WorkloadUtils/workload.conf /etc/azure/workload.conf
        echo "`date`- The command is $1, exiting with conf file copy" >> $logfile
        exit $arc
    fi
elif [ $1 != "enable"  ] && [ $1 != "daemon" ]
then
    echo "`date`- The command is $1, exiting" >> $logfile
    exit $arc
fi

pythonVersionList="python3.8 python3.7 python3.6 python3.5 python3.4 python3.3 python3 python2.7 python2.6 python2 python"

for pythonVersion in ${pythonVersionList};
do
	cmnd="/usr/bin/${pythonVersion}"
	if [ -f "${cmnd}" ]
    then
		echo "`date`- ${pythonVersion} path exists" >> $logfile
		$cmnd main/handle.py -$1
		rc=$?
	fi
	if [ $rc -eq 0 ]
	then
		break
	fi
done

pythonProcess=$(ps -ef | grep waagent | grep python)
pythonPath=$(echo "${pythonProcess}" | head -n1 | awk '{print $8;}')

if [ $rc -ne 0 ] && [ -f "`which python`" ]
then
	echo "`date`- python path exists" >> $logfile
	/usr/bin/env python main/handle.py -$1
	rc=$?
fi

if [ $rc -ne 0 ] && [ -f "${pythonPath}" ]
then
	echo "`date`- python path exists" >> $logfile
	$pythonPath main/handle.py -$1
	rc=$?
fi
	
if [ $rc -eq 3 ]
then
	echo "`date`- python version unknown" >> $logfile
fi

echo "`date`- $rc returned from handle.py" >> $logfile

exit $rc
