#!/usr/bin/env sh

arc=0

comand="$2"
cred_string="$3"
timeout="$4"
scriptPath="$5"

sleep $timeout

if [ "$1" = "oracle" ]
then
    cmd="$comand/sqlplus -S -R 2 /nolog @$scriptPath/postOracleMaster.sql"
    exec $cmd
elif [ "$1" = "postgres" ]
then
    cmd="$comand/psql $cred_string -f $scriptPath/postPostgresMaster.sql"
    exec $cmd
else
    echo "`date`- incorrect workload name"
fi

exit $arc