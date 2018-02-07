#!/bin/bash
# vim: set tabstop=8 shiftwidth=4 softtabstop=4 expandtab smarttab colorcolumn=80:
#

depends() {
    echo crypt systemd
    return 0
}

install() {
    inst_hook initqueue/finished 60 "$moddir/ade-hook.sh"

    inst_hook cmdline 30 "$moddir/parse-crypt-ade.sh"

    inst_rules "$moddir/50-udev-ade.rules"

    inst_multiple /etc/services \
        nc
        
    inst /boot/luks/osluksheader /osluksheader
   
    if [[ $hostonly ]] && [[ -f /etc/crypttab ]]; then
        # filter /etc/crypttab for the devices we need
        while read _mapper _dev _rest; do
            [[ $_mapper = osencrypt ]] || continue
            [[ $_dev ]] || continue

            [[ $_dev == UUID=* ]] &&                 _dev="/dev/disk/by-uuid/${_dev#UUID=}"

        echo "$_mapper $_dev $_rest"

        done < /etc/crypttab >> $initdir/etc/crypttab
    fi

    dracut_need_initqueue
}

