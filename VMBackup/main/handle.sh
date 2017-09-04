#!/bin/bash
##/var/log/azure/Microsoft.Azure.RecoveryServices.VMSnapshotLinux/
pwdcommand=`pwd`
pwdstr="$pwdcommand"
logfile='/var/log/azure/Microsoft.Azure.RecoveryServices.VMSnapshotLinux/'${pwdstr#*-}'/shell.log'
if [ "$1" == "enable" ]; then
    echo "`date`- kill existing process if exists" >> $logfile
    kill $(ps aux | grep 'main/handle.py' | awk '{print $2}')
fi
if [ -f "/usr/bin/python2" ]
then
    echo "`date`- python 2 path exists" >> $logfile
    /usr/bin/python2 main/handle.py -$1
    rc=$?
    if [[ $rc != 0 ]]
    then
        echo "`date`- $rc returned from handle.py" >> $logfile
        exit $rc
    else
        echo "`date`- status returned is 0" >> $logfile
    fi
elif [ -f "/usr/bin/python" ]
then
    echo "`date`- python path exists" >> $logfile
    /usr/bin/python main/handle.py -$1
    rc=$?
    if [[ $rc != 0 ]]
    then
        echo "`date`- $rc returned from handle.py" >> $logfile
        exit $rc
    else
        echo "`date`- status returned is 0" >> $logfile
    fi
else
    echo "`date`- python 3 default" >> $logfile
    exit 3
fi
exit
