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

cp -p /boot/luks/osluksheader ${DESTDIR}/osluksheader

