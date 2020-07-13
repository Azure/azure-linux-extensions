#!/bin/sh

. /lib/dracut-lib.sh
type crypttab_contains >/dev/null 2>&1 || . /lib/dracut-crypt-lib.sh

set -x

dev=$1
luks=$2

allowdiscards="discard"

crypttab_contains "$luks" "$dev" && exit 0
echo "$luks $dev /bek/LinuxPassPhraseFileName timeout=10,$allowdiscards,header=/osluksheader" >> /etc/crypttab

if command -v systemctl >/dev/null; then
    systemctl daemon-reload
    systemctl start cryptsetup.target
fi
exit 0
