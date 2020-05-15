LibDir = "/var/lib/waagent"

Openssl = "openssl"
os_release = "/etc/os-release"


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
