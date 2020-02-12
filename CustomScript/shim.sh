#!/usr/bin/env bash

# The shim scripts provide a single entry point for CSE and will invoke the customscript.py entry point using the
# appropriate python interpreter version.
# Arguments passed to the shim layer are redirected to the invoked script without any validation.

COMMAND="./customscript.py"
PYTHON=""
ARG="$@"

function find_python(){
    local python_exec_command=$1

    # Check if there is python defined.
    if command -v python >/dev/null 2>&1 ; then
        eval ${python_exec_command}="python"
    else
        # Python was not found. Searching for Python3 now.
        if command -v python3 >/dev/null 2>&1 ; then
            eval ${python_exec_command}="python3"
        fi
    fi
}

find_python PYTHON

if [ -z "$PYTHON" ]
then
   echo "No Python interpreter found on the box" >&2
   exit 51 # Not Supported
else
    echo "Found: `${PYTHON} --version`"
fi

${PYTHON} ${COMMAND} ${ARG}
exit $?

# DONE