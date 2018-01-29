#!/bin/bash

ps -ef | grep diagnostic.py | grep -v grep
if [ "$?" = "0" ]; then
    cd /var/lib/waagent/Microsoft.OSTCExtensions.LinuxDiagnostic-2.3.9027
    ./diagnostic.py -disable
    ./diagnostic.py -enable
fi
