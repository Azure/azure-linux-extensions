#!/usr/bin/env bash

# The entry point for the OMS extension through which the correct python version (if any) is used to invoke omsagent.py.
# We default to python2 and always invoke with the versioned python command to accomodate the RHEL 8+ python strategy.
# Control arguments passed to the shim are redirected to omsagent.py without validation.

COMMAND="./omsagent.py"
PYTHON=""
PIP=""
PACKAGES=""
ARG="$@"

# Usage: run_command "shell command" "description of action"
function run_command() {
    eval $1
    if [ $? != 0 ]; then
        echo "$2 failed, command: $1" >&2
        exit 52
    else
        echo "$2 succeeded"
    fi
}

function find_python_env() {
    local python_exec_command=$1
    local pip_exec_command=$2
    local pip_packages=$3

    if command -v python2 >/dev/null 2>&1 ; then
        eval ${python_exec_command}="python2"
        eval ${pip_exec_command}="pip2"
        if [ -x "$(command -v python2.6 >/dev/null 2>&1)" ]; then # get-pip script differs for 2.6
            eval ${pip_packages}="future importlib"
            run_command "curl https://bootstrap.pypa.io/2.6/get-pip.py -o get-pip.py" "pip download"
        else
            eval ${pip_packages}="future"
            run_command "curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py" "pip download"
        fi
    elif command -v python3 >/dev/null 2>&1 ; then
        eval ${python_exec_command}="python3"
        eval ${pip_exec_command}="pip3"
        eval ${pip_packages}="future importlib"
        run_command "curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py" "pip download"
    fi
}

find_python_env PYTHON PIP PACKAGES

if [ -z "$PYTHON" ]
then
    echo "No Python interpreter found, which is an OMS extension dependency. Please install either Python 2 or 3." >&2
    exit 52 # Missing Dependency
else
    ${PYTHON} --version
fi

# Install pip
if [ -z "$PIP" ]; then
    run_command "${PYTHON} get-pip.py" "Install pip"
fi

# Install future
run_command "${PIP} install ${PACKAGES}" "Install python-future, importlib"

${PYTHON} ${COMMAND} ${ARG}
exit $?