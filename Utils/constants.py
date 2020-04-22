LibDir = "/var/lib/waagent"
WaagentConf = """\
#
# Azure Linux Agent Configuration
#

Role.StateConsumer=None                 # Specified program is invoked with the argument "Ready" when we report ready status
                                        # to the endpoint server.
Role.ConfigurationConsumer=None         # Specified program is invoked with XML file argument specifying role configuration.
Role.TopologyConsumer=None              # Specified program is invoked with XML file argument specifying role topology.

Provisioning.Enabled=y                  #
Provisioning.DeleteRootPassword=y       # Password authentication for root account will be unavailable.
Provisioning.RegenerateSshHostKeyPair=y # Generate fresh host key pair.
Provisioning.SshHostKeyPairType=rsa     # Supported values are "rsa", "dsa" and "ecdsa".
Provisioning.MonitorHostName=y          # Monitor host name changes and publish changes via DHCP requests.

ResourceDisk.Format=y                   # Format if unformatted. If 'n', resource disk will not be mounted.
ResourceDisk.Filesystem=ext4            # Typically ext3 or ext4. FreeBSD images should use 'ufs2' here.
ResourceDisk.MountPoint=/mnt/resource   #
ResourceDisk.EnableSwap=n               # Create and use swapfile on resource disk.
ResourceDisk.SwapSizeMB=0               # Size of the swapfile.

LBProbeResponder=y                      # Respond to load balancer probes if requested by Azure.

Logs.Verbose=n                          # Enable verbose logs

OS.RootDeviceScsiTimeout=300            # Root device timeout in seconds.
OS.OpensslPath=None                     # If "None", the system default version is used.
"""

waagent_config_path = "/etc/waagent.conf"
Openssl = "openssl"


class WALAEventOperation:
    HeartBeat = "HeartBeat"
    Provision = "Provision"
    Install = "Install"
    UnIsntall = "UnInstall"
    Disable = "Disable"
    Enable = "Enable"
    Download = "Download"
    Upgrade = "Upgrade"
    Update = "Update"
