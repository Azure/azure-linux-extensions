#!/bin/bash
# vim: set tabstop=8 shiftwidth=4 softtabstop=4 expandtab smarttab colorcolumn=80:
#

depends() {
    echo crypt systemd
    return 0
}

install() {
    inst_script "$moddir"/cryptroot-ask-ade.sh /sbin/cryptroot-ask-ade

    inst_hook cmdline 30 "$moddir/parse-crypt-ade.sh"

    inst_rules "$moddir/50-udev-ade.rules"

    inst_multiple /etc/services
        
    inst /boot/luks/osluksheader /osluksheader
   
    dracut_need_initqueue
}

