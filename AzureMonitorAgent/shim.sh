#!/usr/bin/env bash

# This is the main driver file for AMA extension. This file first checks if Python 2 or 3 is available on the VM 
# and if yes then uses that Python (if both are available then, default is set to python3) to run extension operations in agent.py
# Control arguments passed to the shim are redirected to omsagent.py without validation.

COMMAND="./agent.py"
PYTHON=""
FUTURE_PATH=""
ARG="$@"

function find_python() {
    local python_exec_command=$1
    local future_path=$2

    if command -v python2 >/dev/null 2>&1 ; then
        eval ${python_exec_command}="python2"
        eval ${future_path}="${PWD}/ext/future:"
    elif command -v python3 >/dev/null 2>&1 ; then
        eval ${python_exec_command}="python3"
        # do not set future_path; future seems to cause interference with preexisting packages in python 3 environment
    fi
}

find_python PYTHON FUTURE_PATH

if [ -z "$PYTHON" ] # Need to discuss if we want to install python explicitly or ask the cx to install it
then
    echo "No Python interpreter found, which is an OMS extension dependency. Please install either Python 2 or 3." >&2
    exit 52 # Missing Dependency
else
    ${PYTHON} --version
fi

PYTHONPATH=${FUTURE_PATH}${PYTHONPATH} ${PYTHON} ${COMMAND} ${ARG}
exit $?
