#!/usr/bin/env bash

# The entry point for the OMS extension through which the correct python version (if any) is used to invoke omsagent.py.
# We default to python2 and always invoke with the versioned python command to accomodate the RHEL 8+ python strategy.
# Control arguments passed to the shim are redirected to omsagent.py without validation.

COMMAND="./omsagent.py"
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

if [ -z "$PYTHON" ]
then
    echo "No Python interpreter found, which is an OMS extension dependency. Please install either Python 2 or 3." >&2
    exit 52 # Missing Dependency
else
    ${PYTHON} --version
fi

PYTHONPATH=${FUTURE_PATH}${PYTHONPATH} ${PYTHON} ${COMMAND} ${ARG}
exit $?
