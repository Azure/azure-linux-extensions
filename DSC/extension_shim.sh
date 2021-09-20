#!/usr/bin/env bash

# Keeping the default command
COMMAND=""
PYTHON=""

# Default variables for OMI Package Upgrade
REQUIRED_OMI_VERSION="1.6.8.1"
INSTALLED_OMI_VERSION=""
UPGRADED_OMI_VERSION=""
OPENSSL_VERSION=""
OMI_PACKAGE_PREFIX='packages/omi-1.6.8-1.ssl_'
OMI_PACKAGE_PATH=""
OMI_SERVICE_STATE=""

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

    # Check if there is python2 defined.
    if command -v python2 >/dev/null 2>&1 ; then
        eval ${python_exec_command}="python2"
    else
        # Python2 was not found. Searching for Python3 now.
        if command -v python3 >/dev/null 2>&1 ; then
            eval ${python_exec_command}="python3"
        fi
    fi
}

function get_openssl_version(){
    openssl=`openssl version | awk '{print $2}'`
    if [[ ${openssl} =~ ^1.0.* ]]; then
        OPENSSL_VERSION="100"
    else
        if [[ ${openssl} =~ ^1.1.* ]]; then
            OPENSSL_VERSION="110"
        else
            if [[ ${openssl} =~ ^0.9.8* ]]; then
                OPENSSL_VERSION="098"
            fi
        fi
    fi
}

function start_omiservice(){
    echo "Attempting to start OMI service"
    RESULT=`/opt/omi/bin/service_control start >/dev/null 2>&1`
    RESULT=`service omid status >/dev/null 2>&1`
    if [ $? -eq 0 ]; then
        echo "OMI service succesfully started."
    else
        echo "OMI service could not be started."
    fi
}

function stop_omiservice(){
    echo "Attempting to stop OMI service"
    RESULT=`/opt/omi/bin/service_control stop >/dev/null 2>&1`
    RESULT=`service omid status >/dev/null 2>&1`
    if [ $? -eq 3 ]; then
        echo "OMI service succesfully stopped."
    else
        echo "OMI service could not be stopped."
    fi
}

function ensure_required_omi_version_exists(){
    # Populate SSL Version
    get_openssl_version

    echo "Checking if OMI is installed. Required OMI version: ${REQUIRED_OMI_VERSION}"

    # Check if RPM exists
    if command -v rpm >/dev/null 2>&1 ; then
        echo "Package Manager Type: RPM"
        INSTALLED_OMI_VERSION=`rpm -q --queryformat "%{VERSION}.%{RELEASE}" omi 2>&1` 
        if [ -z "$INSTALLED_OMI_VERSION" ]; then
            echo "OMI is not installed on the machine."
        else
            RESULT=`service omid status >/dev/null 2>&1`
            OMI_SERVICE_STATE=$?
            echo "OMI is already installed. Installed OMI version: ${INSTALLED_OMI_VERSION}; OMI Service State: ${OMI_SERVICE_STATE}" # Add current running status
            if [ ${INSTALLED_OMI_VERSION} = ${REQUIRED_OMI_VERSION} ]; then
                echo "Installed OMI version is same as Required OMI version. No action needed."
            else
                OMI_PACKAGE_PATH="${OMI_PACKAGE_PREFIX}${OPENSSL_VERSION}.x64.rpm"
                echo "Installed OMI version is not same as Required OMI version. Trying to upgrade."
                if [ -f ${OMI_PACKAGE_PATH} ]; then
                    echo "The OMI package exists at ${OMI_PACKAGE_PATH}. Using this to upgrade."
                    stop_omiservice
                    RESULT=`rpm -Uvh ${OMI_PACKAGE_PATH} >/dev/null 2>&1`
                    if [ $? -eq 0 ]; then
                        UPGRADED_OMI_VERSION=`rpm -q --queryformat "%{VERSION}.%{RELEASE}" omi 2>&1`
                        echo "Succesfully upgraded the OMI. Installed: ${INSTALLED_OMI_VERSION} Required: ${REQUIRED_OMI_VERSION} Upgraded: ${UPGRADED_OMI_VERSION}"
                    else
                        echo "Failed to upgrade the OMI. Installed: ${INSTALLED_OMI_VERSION} Required: ${REQUIRED_OMI_VERSION}"
                    fi
                    # Start OMI only if previous state was running
                    if [ $OMI_SERVICE_STATE -eq 0 ]; then
                        start_omiservice
                    fi
                else          
                    echo "The OMI package does not exists at ${OMI_PACKAGE_PATH}. Skipping upgrade."
                fi  
            fi
        fi
        INSTALLED_OMI_VERSION=`rpm -q --queryformat "%{VERSION}.%{RELEASE}" omi 2>&1`
        RESULT=`service omid status >/dev/null 2>&1`
        OMI_SERVICE_STATE=$?
        echo "OMI upgrade is complete. Installed OMI version: ${INSTALLED_OMI_VERSION}; OMI Service State: ${OMI_SERVICE_STATE}"
    else 
        # Check if DPKG exists
        if command -v dpkg >/dev/null 2>&1 ; then
            echo "Package Manager Type: DPKG"
            INSTALLED_OMI_VERSION=`dpkg -s omi 2>&1 | grep Version: | awk '{print $2}'`
            if [ -z "$INSTALLED_OMI_VERSION" ]; then
                echo "OMI is not installed on the machine."
            else
                RESULT=`service omid status >/dev/null 2>&1`
                OMI_SERVICE_STATE=$?
                echo "OMI is already installed. Installed OMI version: ${INSTALLED_OMI_VERSION}; OMI Service State: ${OMI_SERVICE_STATE}"
                if [ ${INSTALLED_OMI_VERSION} = ${REQUIRED_OMI_VERSION} ]; then
                    echo "Installed OMI version is same as Required OMI version. No action needed..."
                else
                    OMI_PACKAGE_PATH="${OMI_PACKAGE_PREFIX}${OPENSSL_VERSION}.x64.deb"
                    echo "Installed OMI version is not same as Required OMI version. Trying to upgrade."
                    if [ -f ${OMI_PACKAGE_PATH} ]; then
                        echo "The OMI package exists at ${OMI_PACKAGE_PATH}. Using this to upgrade."
                        stop_omiservice
                        RESULT=`dpkg -i --force-confold --force-confdef --refuse-downgrade ${OMI_PACKAGE_PATH} >/dev/null 2>&1`
                        if [ $? -eq 0 ]; then
                            UPGRADED_OMI_VERSION=`dpkg -s omi 2>&1 | grep Version: | awk '{print $2}'`
                            echo "Succesfully upgraded the OMI. Installed: ${INSTALLED_OMI_VERSION} Required: ${REQUIRED_OMI_VERSION} Upgraded: ${UPGRADED_OMI_VERSION}"
                        else
                            echo "Failed to upgrade the OMI. Installed: ${INSTALLED_OMI_VERSION} Required: ${REQUIRED_OMI_VERSION}"
                        fi
                        # Start OMI only if previous state was running
                        if [ $OMI_SERVICE_STATE -eq 0 ]; then
                            start_omiservice
                        fi
                    else          
                        echo "The OMI package does not exists at ${OMI_PACKAGE_PATH}. Skipping upgrade."                    
                    fi 
                fi
            fi
            INSTALLED_OMI_VERSION=`dpkg -s omi 2>&1 | grep Version: | awk '{print $2}'`
            RESULT=`service omid status >/dev/null 2>&1`
            OMI_SERVICE_STATE=$?
            echo "OMI upgrade is complete. Installed OMI version: ${INSTALLED_OMI_VERSION}; OMI Service State: ${OMI_SERVICE_STATE}"
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

# Ensure OMI package if exists is of required version.
ensure_required_omi_version_exists

# If find_python is not able to find a python installed, $PYTHON will be null.
find_python PYTHON

if [ -z "$PYTHON" ]; then
   echo "No Python interpreter found on the box" >&2
   exit 51 # Not Supported
else
    `python2 --version`
fi

${PYTHON} ${COMMAND} ${operation}
# DONE