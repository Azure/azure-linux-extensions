#!/bin/bash

root=$(dirname $0)
cd $root
root=`pwd`

set -e

if [[ $EUID -ne 0 ]]; then
    echo "This script must be run as root" 1>&2
    exit 1
fi

echo "Unpacking..."
echo "Installing dependencies:"
echo "  azure-cli"
npm install -g azure-cli
echo "Installing commands"
npm install -g ./azure-linux-tools-1.0.0.tgz
