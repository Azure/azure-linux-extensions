#!/usr/bin/env bash

# The entry point for the OMS extension through which the correct python version (if any) is used to invoke omsagent.py. 
# We default to python2 and always invoke with the versioned python command to accomodate the RHEL 8+ python strategy.
# Control arguments passed to the shim are redirected to omsagent.py without validation.

COMMAND="./omsagent.py"
PYTHON=""
ARG="$@"

function find_python() {
    local python_exec_command=$1

    if command -v python2 >/dev/null 2>&1 ; then
        eval ${python_exec_command}="python2"
    elif command -v python3 >/dev/null 2>&1 ; then
        eval ${python_exec_command}="python3"
    fi
}

find_python PYTHON

if [ -z "$PYTHON" ]
then
    echo "No Python interpreter found, which is an OMS extension dependency. Please install either Python 2 or 3." >&2
    exit 52 # Missing Dependency
else
    echo "Found `${PYTHON} --version`"
fi

# Install python-future dependency required for omsagent.py
if [ -f "/etc/debian_version" ]; then # Ubuntu, Debian
    dpkg-query -l python-future | grep ^ii
    if [ $? != 0 ]; then
        apt-get update
        apt-get install -y python-future
    fi
elif [ -f "/etc/redhat-release" ]; then # RHEL, CentOS, Oracle
    rpm -qi python-future
    if [ $? != 0 ]; then
        yum install -y python-future
    fi
elif [ -f "/etc/os-release" ]; then # Possibly SLES, openSUSE
    grep PRETTY_NAME /etc/os-release | sed 's/PRETTY_NAME=//g' | tr -d '="' | grep -i suse
    if [ $? != 0 ]; then
        echo "Unsupported or indeterminable operating system" >&2
        exit 51
    fi
    rpm -qi python-future
    if [ $? != 0 ]; then
        zypper --non-interactive install python-future
    fi
else
    echo "Unsupported or indeterminable operating system" >&2
    exit 51
fi

${PYTHON} ${COMMAND} ${ARG}
exit $?
