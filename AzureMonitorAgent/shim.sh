#!/usr/bin/env bash

# This is the main driver file for AMA extension. This file first checks if Python 3 or 2 is available on the VM 
# and if yes then uses that Python (if both are available then, default is set to python3) to run extension operations in agent.py
# Control arguments passed to the shim are redirected to agent.py without validation.

COMMAND="./agent.py"
PYTHON=""
ARG="$@"

function find_python() {
    local python_exec_command=$1
    if command -v /usr/libexec/platform-python >/dev/null 2>&1 ; then
        # Prefer platform-python when available — this is the python waagent uses (RHEL 8+)
        # and ensures AMA uses the same interpreter with the same installed modules.
        eval ${python_exec_command}="/usr/libexec/platform-python"
    elif command -v python3 >/dev/null 2>&1 ; then
        eval ${python_exec_command}="python3"
    elif command -v python2 >/dev/null 2>&1 ; then
        eval ${python_exec_command}="python2"
    fi
    
}

find_python PYTHON

if [ -z "$PYTHON" ] # If python is not installed, we will fail the install with the following error, requiring cx to have python pre-installed
then
    echo "No Python interpreter found, which is an AMA extension dependency. Please install Python 3, or Python 2 if the former is unavailable." >&2
    exit 52 # Missing Dependency
else
    ${PYTHON} --version 2>&1
fi

export NO_PROXY="169.254.169.254"
PYTHONPATH=${PYTHONPATH} ${PYTHON} ${COMMAND} ${ARG}
exit $?
