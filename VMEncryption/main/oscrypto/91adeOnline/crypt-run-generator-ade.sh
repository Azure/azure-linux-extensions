#!/bin/sh

. /lib/dracut-lib.sh
type crypttab_contains >/dev/null 2>&1 || . /lib/dracut-crypt-lib.sh

set -x

dev=$1
luks=$2
bootuuid=$3

crypttab_contains "$luks" "$dev" && exit 0
echo "$luks $dev /bek/LinuxPassPhraseFileName timeout=10,discard,header=/boot/luks/osluksheader" >> /etc/crypttab
echo "UUID=$bootuuid /boot auto defaults 0 0" >> /etc/fstab
echo "LABEL=BEK\040VOLUME /bek auto defaults,nofail 0 0" >> /etc/fstab

if command -v systemctl >/dev/null; then
    systemctl daemon-reload
    systemctl start bek.mount
    systemctl start boot.mount
    systemctl start cryptsetup.target
fi

if [ -b /dev/mapper/osencrypt ]; then
    umount /boot
    umount /bek
fi

exit 0
