#!/usr/bin/env sh

logfile="shell.log"

rc=3

arr="python3.6 python3.5 python3.4 python3.3 python3 python2.7 python2.6 python2"


for i in ${arr};
do
        cmnd="/usr/bin/${i}"
        if [ -f "${cmnd}" ]
        then
                echo "`date`- ${i} path exists" >> $logfile
                $cmnd handle.py -$1
                rc=$?
        fi
        if [ $rc -eq 0 ]
        then
                break
        fi
done

if [ $rc -ne 0 ]
then
	if [ -f "`which python`" ]
	then
		echo "`date`- python path exists" >> $logfile
		/usr/bin/env python main/handle.py -$1
		rc=$?
	else
		echo "`date`- python version unknown" >> $logfile
	fi
fi

exit $rc
