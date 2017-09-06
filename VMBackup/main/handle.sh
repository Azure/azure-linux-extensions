#!/bin/bash
pwdcommand=`pwd`
pwdstr="$pwdcommand"
output=`cat $pwdstr'/HandlerEnvironment.json'`
outputstr="$output"

poststr=${outputstr#*logFolder\"}
postsubstr=${poststr#*\"configFolder}
resultstrlen=`expr ${#poststr} - 13 - ${#postsubstr}`
resultstr=$(echo $poststr | cut -b 1-$resultstrlen)
##parsing further to remove " : and spaces
poststr1=${resultstr#*\"}
postsubstr1=${poststr1#*\"}
resultstrlen1=`expr ${#poststr1} - 1 - ${#postsubstr1}`

logfolder=$(echo $poststr1 | cut -b 1-$resultstrlen1)
logfile=$logfolder'/shell.log'

if [ "$1" == "enable" ]; then
    echo "`date`- kill existing process if exists" >> $logfile
    kill $(ps aux | grep 'main/handle.py' | awk '{print $2}')
fi
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
