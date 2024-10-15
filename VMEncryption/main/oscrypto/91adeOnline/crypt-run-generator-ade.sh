#!/bin/sh

. /lib/dracut-lib.sh
type crypttab_contains >/dev/null 2>&1 || . /lib/dracut-crypt-lib.sh

set -x

dev=$1
luks=$2
bootuuid=$3

crypttab_contains "$luks" "$dev" && exit 0
echo "Adding $luks to crypttab and updating fstab..." >> /var/log/boot_decrypt.log
echo "$luks $dev /bek/LinuxPassPhraseFileName timeout=10,discard,header=/boot/luks/osluksheader" >> /etc/crypttab
echo "UUID=$bootuuid /boot auto defaults 0 0" >> /etc/fstab
echo "LABEL=BEK\040VOLUME /bek auto defaults,nofail 0 0" >> /etc/fstab

if command -v systemctl >/dev/null; then
    echo "Reloading systemd daemon and starting services..." >> /var/log/boot_decrypt.log
    systemctl daemon-reload
    systemctl start bek.mount
    systemctl start boot.mount
    systemctl start cryptsetup.target
fi

# Wait for the encrypted disk to be unlocked
echo "Waiting for /dev/mapper/osencrypt to become available..." >> /var/log/boot_decrypt.log
while ! [ -b /dev/mapper/osencrypt ]; do
    sleep 1
done

if [ -b /dev/mapper/osencrypt ]; then
    echo "/dev/mapper/osencrypt is available, unmounting /boot and /bek..." >> /var/log/boot_decrypt.log
    umount /boot
    umount /bek
fi

echo "Script completed at $(date)" >> /var/log/boot_decrypt.log
exit 0
