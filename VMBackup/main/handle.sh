#!/bin/bash
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

if [ -f "/usr/bin/python2" ]
then
    echo "`date`- python 2 path exists" >> $logfile
    /usr/bin/python2 main/handle.py -$1
    rc=$?
    echo "`date`- $rc returned from handle.py" >> $logfile
elif [ -f "/usr/bin/python" ]
then
    echo "`date`- python path exists" >> $logfile
    /usr/bin/python main/handle.py -$1
    rc=$?
    echo "`date`- $rc returned from handle.py" >> $logfile
else
    echo "`date`- python 3 default" >> $logfile
    exit 3
fi
exit $rc
