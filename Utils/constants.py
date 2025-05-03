LibDir = "/var/lib/waagent"

Openssl = "openssl"
os_release = "/etc/os-release"
system_release = "/etc/system-release"


class WALAEventOperation:
    HeartBeat = "HeartBeat"
    Provision = "Provision"
    Install = "Install"
    UnInstall = "UnInstall"
    Disable = "Disable"
    Enable = "Enable"
    Download = "Download"
    Upgrade = "Upgrade"
    Update = "Update"
