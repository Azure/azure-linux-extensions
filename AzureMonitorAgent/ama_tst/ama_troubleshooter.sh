#!/usr/bin/env bash

COMMAND="./modules/main.py"
PYTHON=""
FUTURE_PATH=""
TST_VERSION="1.1"  # update when changes are made to TST

find_python() {
    local python_exec_command=$1
    local future_path=$2

    if command -v python3 >/dev/null 2>&1 ; then
        eval ${python_exec_command}="python3"
        # do not set future_path; future seems to cause interference with preexisting packages in python 3 environment
    elif command -v python2 >/dev/null 2>&1 ; then
        eval ${python_exec_command}="python2"
        eval ${future_path}="${PWD}/ext/future:"
    elif command -v /usr/libexec/platform-python >/dev/null 2>&1 ; then
        # If a user-installed python isn't available, check for a platform-python. This is typically only used in RHEL 8.0.
        echo "User-installed python not found. Using /usr/libexec/platform-python as the python interpreter."
        eval ${python_exec_command}="/usr/libexec/platform-python"
        # do not set future_path; future seems to cause interference with preexisting packages in python 3 environment
    fi
}

find_python PYTHON FUTURE_PATH

if [ -z "$PYTHON" ] # If python is not installed, we will fail the install with the following error, requiring cx to have python pre-installed
then
    echo "No Python interpreter found, which is an AMA extension dependency. Please install Python 3, or Python 2 if the former is unavailable." >&2
    exit 1
else
    echo "Python version being used is:"
    ${PYTHON} --version 2>&1
    echo ""
fi

echo "Starting AMA Troubleshooting Tool v.$TST_VERSION..."
echo ""
if [ -z $1 ]
then
    PYTHONPATH=${FUTURE_PATH}${PYTHONPATH} ${PYTHON} ${COMMAND}
else
    PYTHONPATH=${FUTURE_PATH}${PYTHONPATH} ${PYTHON} ${COMMAND} $1
fi
exit $?
