#!/bin/bash

install_log=`pwd`/install.log
root=$(dirname $0)
cd $root
root=`pwd`

if [[ $EUID -ne 0 ]]; then
    echo "[ERROR]This script must be run as root" 1>&2
    exit 1
fi

function install_nodejs_tarball()
{
    version="v0.10.37"
    node_version="node-$version-linux-x64"
    src="$root/$node_version"
    target="/usr/local"

    echo "[INFO]Installing nodejs from http://nodejs.org/dist/$version/${node_version}.tar.gz"
    if [ -f ${src}.tar.gz ]; then
        rm ${src}.tar.gz -f
    fi
    if [ -d ${src} ]; then
        rm ${src} -rf
    fi
    wget http://nodejs.org/dist/$version/${node_version}.tar.gz 1>>$install_log 2>&1
    tar -zxf ${node_version}.tar.gz  1>>$install_log 2>&1

    echo "[INFO]Install nodejs to $target"
    if [ -f $target/bin/node ]; then
        rm $target/bin/node -f
    fi
    cp $src/bin/node $target/bin/node
    
    echo "[INFO]Create link to $target/bin/node"
    if [ -f /usr/bin/node ]; then
        rm /usr/bin/node -f
    fi
    ln -s $target/bin/node /usr/bin/node
   
    echo "[INFO]Install npm"
    curl -sL https://www.npmjs.org/install.sh | sh 1>>$install_log 2>&1

}

function install_nodejs()
{
    echo "[INFO]Installing nodejs and npm"
    if [ "$(type apt-get 2>/dev/null)" != "" ] ; then
        curl -sL https://deb.nodesource.com/setup | bash - 1>>$install_log 2>&1
        apt-get -y install nodejs 1>>$install_log 2>&1
    elif [ "$(type yum 2>/dev/null)" != "" ] ; then
        curl -sL https://rpm.nodesource.com/setup | bash - 1>>$install_log 2>&1
        yum -y install nodejs 1>>$install_log 2>&1
    else
        install_nodejs_tarball 
    fi
    if [ ! $? ]; then
        echo "[ERROR]Install nodejs and npm failed. See $install_log."
        exit 1
    fi
}

echo "[INFO]Checking dependency..."
echo "" > $install_log
if [ "$(type node 2>/dev/null)" == "" ]; then
    install_nodejs
fi
echo "[INFO]  nodejs version: $(node --version)"

if [ "$(type npm 2>/dev/null)" == "" ]; then
    install_nodejs
fi
echo "[INFO]  npm version: $(npm -version)"

if [ "$(type azure 2> /dev/null)" == "" ]; then
    echo "[INFO]Installing azure-cli"
    npm install -g azure-cli 1>>$install_log 2>&1
    if [ ! $? ]; then
        echo "[ERROR]Install azure-cli failed. See $install_log."
        exit 1
    fi
fi
echo "[INFO]  azure-cli version: $(azure --version)"

npm_pkg="azure-linux-tools-1.0.0.tgz"
echo "[INFO]Installing Azure Enhanced Monitor tools..."
if [ -f ./$npm_pkg ]; then
    npm install -g ./$npm_pkg 1>>$install_log 2>&1
    if [ ! $? ]; then
        echo "[ERROR]Install Azure Enhanced Monitor tools failed. See $install_log."
        exit 1
    fi
else
    echo "[ERROR] Couldn't find npm package $npm_pkg"
    exit 1
fi

echo "[INFO]Finished."
