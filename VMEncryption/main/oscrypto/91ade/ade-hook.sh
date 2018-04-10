#!/bin/bash -e
# vim: set tabstop=8 shiftwidth=4 softtabstop=4 expandtab smarttab colorcolumn=80:
#

shopt -s nullglob
set -x

if [ -f /ADE-OSDisk-Unlocked ]
then
    exit 0
fi

unlockretcode=1

for question in /run/systemd/ask-password/ask.*; do
    d=
    s=

    while read line; do
        case "$line" in
            Id=cryptsetup:*) d="${line##Id=cryptsetup:}";;
            Socket=*) s="${line##Socket=}";;
        esac
    done < "$question"
    [ -z "$d" -o -z "$s" ] && continue

    ls /mnt/azure_bek_disk/LinuxPassPhraseFileName || (mkdir -p /mnt/azure_bek_disk/ && mount -L "BEK VOLUME" /mnt/azure_bek_disk/)
    pw=`cat /mnt/azure_bek_disk/LinuxPassPhraseFileName`
    umount /mnt/azure_bek_disk
    echo -n "+$pw" | nc -U -u --send-only "$s"

    echo "Unlocked" > /ADE-OSDisk-Unlocked
    unlockretcode=0
done

exit $unlockretcode
