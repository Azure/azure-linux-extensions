#!/usr/bin/env bash

# This is the main driver file for LAD extension. This file first checks if Python 2 is available on the VM and exits early if not
# Control arguments passed to the shim are redirected to diagnostic.py without validation.

COMMAND="./diagnostic.py"
PYTHON=""
ARG="$@"

function find_python() {
    local python_exec_command=$1

    if command -v python2 >/dev/null 2>&1 ; then
        eval ${python_exec_command}="python2"
    fi
}

find_python PYTHON

if [ -z "$PYTHON" ] # If python2 is not installed, we will fail the install with the following error, requiring cx to have python pre-installed
then
    echo "No Python 2 interpreter found, which is an LAD extension dependency. Please install Python 2 before retrying LAD extension deployment." >&2
    exit 52 # Missing Dependency
else
    ${PYTHON} --version 2>&1
fi

${PYTHON} ${COMMAND} ${ARG}
exit $?