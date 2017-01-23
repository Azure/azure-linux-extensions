#!/bin/bash
instance=$1

# variables used for returning the status of the scripts
success=0
error=1
warning=2

retVal=$success

log_path="/etc/preScript.log"   #path of log file
printf  "Instance: $instance \n" > $log_path

csession $instance -U%SYS "##Class(Backup.General).ExternalFreeze()"
status=$?
printf  "Freeze status: $status\n" >> $log_path
if [ $status -eq 5 ]; then
echo "SYSTEM IS FROZEN"
printf  "SYSTEM IS FROZEN\n" >> $log_path
elif [ $status -eq 3 ]; then
echo "SYSTEM FREEZE FAILED"
printf  "SYSTEM FREEZE FAILED\n" >> $log_path
retVal=$error
csession $instance -U%SYS "##Class(Backup.General).ExternalThaw()"
else
echo "ERROR IN SYSTEM FREEZE"
printf  "ERROR IN SYSTEM FREEZE\n" >> $log_path
retVal=$error
csession $instance -U%SYS "##Class(Backup.General).ExternalThaw()"
fi

exit $retVal

