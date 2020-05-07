#!/usr/bin/env bash
# must run with sudo permissions
# this file copies the local changes to /var/lib/waagent/Microsoft.OSTCExtensions.VMAccessForLinux-<version>

# remember to update the version number to what you have
destdir="/var/lib/waagent/Microsoft.OSTCExtensions.VMAccessForLinux-1.5.4"
utilsDest="$destdir/Utils"
vmaccessDest="$destdir/vmaccess.py"

currentDir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

utilsSource="$currentDir/.."
vmaccessSource="$currentDir/../../VMAccess/vmaccess.py"

cp -r -f $utilsSource $utilsDest
cp -f $vmaccessSource $vmaccessDest
find $destdir -name '*.pyc' | xargs rm
