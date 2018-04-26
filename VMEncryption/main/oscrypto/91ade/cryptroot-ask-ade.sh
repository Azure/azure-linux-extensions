#!/bin/sh
# -*- mode: shell-script; indent-tabs-mode: nil; sh-basic-offset: 4; -*-
# ex: ts=8 sw=4 sts=4 et filetype=sh

set -x

PATH=/usr/sbin:/usr/bin:/sbin:/bin
NEWROOT=${NEWROOT:-"/sysroot"}

# do not ask, if we already have root
[ -f $NEWROOT/proc ] && exit 0

# check if destination already exists
[ -b /dev/mapper/$2 ] && exit 0

# we already asked for this device
[ -f /tmp/cryptroot-asked-$2 ] && exit 0

# load dm_crypt if it is not already loaded
[ -d /sys/module/dm_crypt ] || modprobe dm_crypt

. /lib/dracut-crypt-lib.sh

# default luksname - luks-UUID
luksname=$2

# fallback to passphrase
ask_passphrase=1

# if device name is /dev/dm-X, convert to /dev/mapper/name
if [ "${1##/dev/dm-}" != "$1" ]; then
    device="/dev/mapper/$(dmsetup info -c --noheadings -o name "$1")"
else
    device="$1"
fi

numtries=${3:-10}

#
# Open LUKS device
#

info "luksOpen $device $luksname"

ls /mnt/azure_bek_disk/LinuxPassPhraseFileName* || (mkdir -p /mnt/azure_bek_disk/ && mount -L "BEK VOLUME" /mnt/azure_bek_disk/)

for luksfile in $(ls /mnt/azure_bek_disk/LinuxPassPhraseFileName*); do
    break;
done

cryptsetupopts="--header /osluksheader"

if [ -n "$luksfile" -a "$luksfile" != "none" -a -e "$luksfile" ]; then
    if cryptsetup --key-file "$luksfile" $cryptsetupopts luksOpen "$device" "$luksname"; then
        ask_passphrase=0
    fi
else
	if [ $numtries -eq 0 ]; then
		warn "No key found for $device.  Fallback to passphrase mode."
	else
		sleep 1
		info "No key found for $device.  Will try $numtries time(s) more later."
		initqueue --unique --onetime --settled \
			--name cryptroot-ask-$luksname \
			$(command -v cryptroot-ask) "$device" "$luksname" "$(($numtries-1))"
		exit 0
	fi
fi

if [ $ask_passphrase -ne 0 ]; then
    luks_open="$(command -v cryptsetup) $cryptsetupopts luksOpen"
    ask_for_password --ply-tries 5 \
        --ply-cmd "$luks_open -T1 $device $luksname" \
        --ply-prompt "Password ($device)" \
        --tty-tries 1 \
        --tty-cmd "$luks_open -T5 $device $luksname"
    unset luks_open
fi

umount /mnt/azure_bek_disk

unset device luksname luksfile

# mark device as asked
>> /tmp/cryptroot-asked-$2

need_shutdown
udevsettle

exit 0
