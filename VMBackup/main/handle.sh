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

if [ $1 != "enable"]
then
	echo "The command is not enable, exiting" >> $logfile
	exit $rc

if [ -f "/usr/bin/python2.7" ]
then
    echo "`date`- python 2.7 path exists" >> $logfile
    /usr/bin/python2.7 main/handle.py -$1
    rc=$?
elif [ -f "/usr/bin/python2" ]
then
    echo "`date`- python2 path exists" >> $logfile
    /usr/bin/python2 main/handle.py -$1
    rc=$?
elif [ -f "/usr/bin/python3.6" ]
then
    echo "`date`- python3.6 path exists" >> $logfile
    /usr/bin/python3.6 main/handle.py -$1
    rc=$?
elif [ -f "/usr/bin/python3.5" ]
then
    echo "`date`- python3.5 path exists" >> $logfile
    /usr/bin/python3.5 main/handle.py -$1
    rc=$?
elif [ -f "/usr/bin/python3.4" ]
then
    echo "`date`- python3.4 path exists" >> $logfile
    /usr/bin/python3.4 main/handle.py -$1
    rc=$?
elif [ -f "/usr/bin/python3.3" ]
then
    echo "`date`- python3.3 path exists" >> $logfile
    /usr/bin/python3.3 main/handle.py -$1
    rc=$?
elif [ -f "/usr/bin/python3" ]
then
    echo "`date`- python3 path exists" >> $logfile
    /usr/bin/python3 main/handle.py -$1
    rc=$?
elif [ -f "/usr/bin/python2.6" ]
then
    echo "`date`- python2.6 path exists" >> $logfile
    /usr/bin/python2.6 main/handle.py -$1
    rc=$?
elif [ -f "/usr/bin/python" ]
then
    echo "`date`- python path exists" >> $logfile
    /usr/bin/python main/handle.py -$1
    rc=$?
elif [ -f "`which python`" ]
then
    echo "`date`- python path exists" >> $logfile
    /usr/bin/env python main/handle.py -$1
    rc=$?
else
    echo "`date`- python version unknown" >> $logfile
fi
echo "`date`- $rc returned from handle.py" >> $logfile

exit $rc
