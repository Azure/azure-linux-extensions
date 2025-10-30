#!/usr/bin/env bash

COMMAND="./modules/main.py"
PYTHON=""
TST_VERSION="1.6"  # update when changes are made to TST
ARG="$@"

display_help() {
    echo "OPTIONS"
    echo "  -A              Run All Troubleshooting Tool checks"
    echo "  -L              Run Log Collector"
    echo "  -v, --version   Print Troubleshooting Tool version"
}

find_python() {
    local python_exec_command=$1

    if command -v python3 >/dev/null 2>&1 ; then
        eval ${python_exec_command}="python3"
    elif command -v python2 >/dev/null 2>&1 ; then
        eval ${python_exec_command}="python2"
    elif command -v /usr/libexec/platform-python >/dev/null 2>&1 ; then
        # If a user-installed python isn't available, check for a platform-python. This is typically only used in RHEL 8.0.
        echo "User-installed python not found. Using /usr/libexec/platform-python as the python interpreter."
        eval ${python_exec_command}="/usr/libexec/platform-python"
    fi
}

find_python PYTHON

if [ -z "$PYTHON" ] # If python is not installed, we will fail the install with the following error, requiring cx to have python pre-installed
then
    echo "No Python interpreter found, which is an AMA extension dependency. Please install Python 3, or Python 2 if the former is unavailable." >&2
    exit 1
else
    echo "Python version being used is:"
    ${PYTHON} --version 2>&1
    echo ""
fi

if [ "$1" = "--help" ] || [ "$1" = "-h" ]
then
    display_help
elif [ "$1" = "--version" ] || [ "$1" = "-v" ]
then
    echo "AMA Troubleshooting Tool v.$TST_VERSION"
else
    echo "Starting AMA Troubleshooting Tool v.$TST_VERSION..."
    echo ""
    PYTHONPATH=${PYTHONPATH} ${PYTHON} ${COMMAND} ${ARG}
fi
exit $?
