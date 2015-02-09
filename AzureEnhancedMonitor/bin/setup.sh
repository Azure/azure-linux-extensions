#!/bin/bash

install_log=`pwd`/install.log
root=$(dirname $0)
cd $root
root=`pwd`

set -e

if [[ $EUID -ne 0 ]]; then
    echo "[ERROR]This script must be run as root" 1>&2
    exit 1
fi

function install_pkg()
{
    pkg_display_name=$1
    apt_pkg_name=$2
    yum_pkg_name=$3
    echo "[INFO]Installing $pkg_display_name"
    if [ "$(type apt-get 2>/dev/null)" != "" ] ; then
        apt-get -y install $apt_pkg_name 1>>$install_log 2>&1
    elif [ "$(type yum 2>/dev/null)" != "" ] ; then
        yum -y install $yum_pkg_name 1>>$install_log 2>&1
    else
        echo "[ERROR]Neither apt-get or yum is found, you need to install \"$pkg_display_name\" manually."
        exit 1
    fi
    if [ ! $? ]; then
        echo "[ERROR]Install $pkg_display_name failed. See $install_log."
        exit 1
    fi
}

echo "[INFO]Checking dependency..."
echo "" > $install_log
if [ "$(type node 2>/dev/null)" == "" ]; then
    install_pkg "node.js" "nodejs-legacy"  "nodejs"
fi
echo "[INFO]  nodejs version: $(node --version)"

if [ "$(type npm 2>/dev/null)" == "" ]; then
    install_pkg "npm" "npm" "npm"
fi
echo "[INFO]  npm version: $(npm -version)"

if [ "$(type azure 2> /dev/null)" == "" ]; then
    npm install -g azure-cli 1>>$install_log 2>&1
fi
echo "[INFO]  azure-cli version: $(azure --version)"

npm_pkg="azure-linux-tools-1.0.0.tgz"
echo "[INFO]Installing commands."
if [ -f ./$npm_pkg ]; then
    npm install -g ./$npm_pkg 1>>$install_log 2>&1
else
    echo "[ERROR] Couldn't find npm package $npm_pkg"
    exit 1
fi

echo "[INFO]Finished."
