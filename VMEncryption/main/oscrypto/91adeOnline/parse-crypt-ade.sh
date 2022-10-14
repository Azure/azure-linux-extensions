#!/bin/sh
# -*- mode: shell-script; indent-tabs-mode: nil; sh-basic-offset: 4; -*-
# ex: ts=8 sw=4 sts=4 et filetype=sh
set -x

if ! getargbool 1 rd.ade -d -n rd_NO_ADE; then
    info "rd.ade=0: removing cryptoluks activation"
    rm -f -- /etc/udev/rules.d/70-luks-ade.rules
else
    {
        echo 'SUBSYSTEM!="block", GOTO="luks_ade_end"'
        echo 'ACTION!="add|change", GOTO="luks_ade_end"'
    } > /etc/udev/rules.d/70-luks-ade.rules.new

    PARTUUID=$(getarg rd.luks.ade.partuuid -d rd_LUKS_PARTUUID)
    BOOTUUID=$(getarg rd.luks.ade.bootuuid -d rd_LUKS_BOOTUUID)

    {
        printf -- 'ENV{ID_PART_ENTRY_UUID}=="*%s*", ' "$PARTUUID"
        printf -- 'RUN+="%s ' "$(command -v initqueue)"
        printf -- '--unique --settled --onetime --name crypt-run-generator-ade-%%k '
        printf -- '%s $env{DEVNAME} osencrypt ' "$(command -v crypt-run-generator-ade)"
        printf -- '%s"\n' "$BOOTUUID"
    } >> /etc/udev/rules.d/70-luks-ade.rules.new
    echo 'LABEL="luks_ade_end"' >> /etc/udev/rules.d/70-luks-ade.rules.new
    mv /etc/udev/rules.d/70-luks-ade.rules.new /etc/udev/rules.d/70-luks-ade.rules
fi
