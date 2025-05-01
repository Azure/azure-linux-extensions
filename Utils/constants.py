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

supported_dists_x86_64 = {'redhat' : ['7', '8', '9'], # Rhel
                       'rhel' : ['7', '8', '9'], # Rhel
                       'centos' : ['7', '8'], # CentOS
                       'red hat' : ['7', '8', '9'], # Oracle, RHEL
                       'oracle' : ['7', '8', '9'], # Oracle
                       'ol' : ['7', '8', '9'], # Oracle Linux
                       'debian' : ['9', '10', '11', '12'], # Debian
                       'ubuntu' : ['16.04', '18.04', '20.04', '22.04', '24.04'], # Ubuntu
                       'suse' : ['12', '15'], 'sles' : ['12', '15'], # SLES
                       'mariner' : ['2'], # Mariner
                       'azurelinux' : ['3'], # Azure Linux / Mariner 3
                       'rocky' : ['8', '9'], # Rocky
                       'alma' : ['8', '9'], # Alma
                       'opensuse' : ['15'], # openSUSE
                       'amzn' : ['2', '2023'] # Amazon Linux 2
}

supported_dists_aarch64 = {'red hat' : ['8'], # Rhel
                    'ubuntu' : ['18.04', '20.04', '22.04', '24.04'], # Ubuntu
                    'alma' : ['8'], # Alma
                    'centos' : ['7'], # CentOS
                    'mariner' : ['2'], # Mariner 2
                    'azurelinux' : ['3'], # Azure Linux / Mariner 3
                    'sles' : ['15'], # SLES
                    'debian' : ['11'], # Debian
                    'rocky linux' : ['8', '9'], # Rocky
                    'rocky' : ['8', '9'] # Rocky
}
