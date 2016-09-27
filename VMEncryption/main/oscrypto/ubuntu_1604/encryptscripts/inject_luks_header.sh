#!/bin/sh -e

PREREQS=""

prereqs() { echo "$PREREQS"; }

case "$1" in
    prereqs)
    prereqs
    exit 0
    ;;
esac

. /usr/share/initramfs-tools/hook-functions

mkdir -p ${DESTDIR}/boot/luks
copy_exec /boot/luks/osluksheader /boot/luks
