#!/bin/bash # vim: set tabstop=8 shiftwidth=4 softtabstop=4 expandtab smarttab:
#

depends() {
    echo crypt systemd
    return 0
}

# called by dracut
installkernel() {
    hostonly="" instmods drbg
    arch=$(arch)
    [[ $arch == x86_64 ]] && arch=x86
    [[ $arch == s390x ]] && arch=s390
    instmods dm_crypt =crypto =drivers/crypto =arch/$arch/crypto
}

install() {
    inst_hook cmdline 30 "$moddir/parse-crypt-ade.sh"
    inst_script "$moddir"/crypt-run-generator-ade.sh /sbin/crypt-run-generator-ade
    dracut_need_initqueue
}

