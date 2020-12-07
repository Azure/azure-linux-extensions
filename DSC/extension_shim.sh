#!/usr/bin/env bash

# Keeping the default command
COMMAND=""
PYTHON=""

USAGE="$(basename "$0") [-h] [-i|--install] [-u|--uninstall] [-d|--disable] [-e|--enable] [-p|--update]

Program to find the installed python on the box and invoke a Python extension script.

where:
    -h|--help       show this help text
    -i|--install    install the extension
    -u|--uninstall  uninstall the extension
    -d|--disable    disable the extension
    -e|--enable     enable the extension
    -p|--update     update the extension
    -c|--command    command to run

example:
# Install usage
$ bash extension_shim.sh -i
python ./vmaccess.py -install

# Custom executable python file
$ bash extension_shim.sh -c ""hello.py"" -i
python hello.py -install

# Custom executable python file with arguments
$ bash extension_shim.sh -c ""hello.py --install""
python hello.py --install
"

function find_python(){
    local python_exec_command=$1

    # Check if there is python defined.
    if command -v python >/dev/null 2>&1 ; then
        eval ${python_exec_command}="python"
    else
        # Python was not found. Searching for Python3 now.
        if command -v python >/dev/null 2>&1 ; then
            eval ${python_exec_command}="python3"
        fi
    fi
}

# Transform long options to short ones for getopts support (getopts doesn't support long args)
for arg in "$@"; do
  shift
  case "$arg" in
    "--help")       set -- "$@" "-h" ;;
    "--install")    set -- "$@" "-i" ;;
    "--update")     set -- "$@" "-p" ;;
    "--enable")     set -- "$@" "-e" ;;
    "--disable")    set -- "$@" "-d" ;;
    "--uninstall")  set -- "$@" "-u" ;;
    *)              set -- "$@" "$arg"
  esac
done

if [ -z "$arg" ]
then
   echo "$USAGE" >&2
   exit 1
fi

# Get the arguments
while getopts "iudephc:?" o; do
    case "${o}" in
        h|\?)
            echo "$USAGE"
            exit 0
            ;;
        i)
            operation="-install"
            ;;
        u)
            operation="-uninstall"
            ;;
        d)
            operation="-disable"
            ;;
        e)
            operation="-enable"
            ;;
        p)
            operation="-update"
            ;;
        c)
            COMMAND="$OPTARG"
            ;;
        *)
            echo "$USAGE" >&2
            exit 1
            ;;
    esac
done

shift $((OPTIND-1))

# If find_python is not able to find a python installed, $PYTHON will be null.
find_python PYTHON


if [ -z "$PYTHON" ]; then
   echo "No Python interpreter found on the box" >&2
   exit 51 # Not Supported
else
    `${PYTHON} --version`
fi

${PYTHON} ${COMMAND} ${operation}
# DONE