#!/bin/sh
# -*- mode: shell-script; indent-tabs-mode: nil; sh-basic-offset: 4; -*-
# ex: ts=8 sw=4 sts=4 et filetype=sh
set -x

{
    echo 'SUBSYSTEM!="block", GOTO="luks_ade_end"'
    echo 'ACTION!="add|change", GOTO="luks_ade_end"'
} > /etc/udev/rules.d/70-luks-ade.rules.new

{
    printf -- 'ATTRS{device_id}=="?00000000-0000-*", ENV{ID_FS_UUID}="osencrypt-locked",'
    printf -- 'RUN+="%s --settled --unique --onetime ' $(command -v initqueue)
    printf -- '--name systemd-cryptsetup-%%k %s start ' $(command -v systemctl)
    printf -- 'systemd-cryptsetup@osencrypt.service"\n'
} >> /etc/udev/rules.d/70-luks-ade.rules.new

echo 'LABEL="luks_ade_end"' >> /etc/udev/rules.d/70-luks-ade.rules.new
mv /etc/udev/rules.d/70-luks-ade.rules.new /etc/udev/rules.d/70-luks-ade.rules
