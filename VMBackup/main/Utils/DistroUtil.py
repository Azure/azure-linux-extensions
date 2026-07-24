#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Shared /etc/os-release parsing for VMBackup.
#
# platform.dist() / platform.linux_distribution() were removed in Python 3.8,
# so distro detection now reads /etc/os-release directly. This helper is the
# single source of truth for that parsing (previously copy-pasted in
# HandlerUtil.get_dist_info(), WaagentLib.DistInfo(), and patch/__init__.py).

def read_os_release(path="/etc/os-release"):
    """Parse /etc/os-release into a dict of KEY -> value.

    Values have surrounding double quotes stripped. Returns an empty dict if the
    file is missing or unreadable (callers fall back to their defaults).
    """
    data = {}
    try:
        with open(path, "r") as f:
            for line in f:
                key, sep, value = line.strip().partition("=")
                if sep and key:
                    data[key] = value.strip('"')
    except Exception:
        pass
    return data
