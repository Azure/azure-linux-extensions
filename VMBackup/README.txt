VMBackup extension is used by Azure Backup service to provide application consistent backup for Linux VMs running in Azure. 

**Note:** This extension is not recommended to be installed outside Azure Backup service context. 

Configuration
-------------

The VMBackup extension reads optional configuration from /etc/azure/vmbackup.conf.
Below are the available options under the [SnapshotThread] section:

  fsfreeze (default: True)
    Whether to freeze filesystems (fsfreeze/thaw) before taking a snapshot.
    Freezing ensures application-consistent backups by flushing pending I/O.
    Set to False only if fsfreeze causes issues (e.g., unresponsive mounts).

  onlyLocalFilesystems (default: False)
    When set to True, the extension uses 'df -kl' instead of 'df -k' for size
    calculation, restricting the listing to local filesystems only. This prevents
    the df command from hanging when network mounts (NFS, CIFS, FUSE, etc.) are
    unreachable or slow to respond. Recommended for VMs with network-mounted
    filesystems.

  MountsToSkip (default: empty)
    Comma-separated list of mount points to exclude from filesystem freeze.
    Useful when specific mounts should not be frozen during backup (e.g., large
    shared storage that cannot be safely frozen).

  seqsnapshot (default: 0)
    Controls snapshot ordering. 0 = parallel snapshots, 1 = sequential (set
    programmatically), 2 = sequential (set by customer). Use 2 to force
    sequential disk snapshots if parallel snapshots cause issues.

Example /etc/azure/vmbackup.conf:

  [SnapshotThread]
  fsfreeze = True
  onlyLocalFilesystems = True
  MountsToSkip = /mnt/nfs_share,/mnt/cifs_share

Deploying the extension to a VM
This extension gets deployed as part of first scheduled backup of the VM post you configure VM for backup. You can configure VM to be backed up using [Azure Portal](https://docs.microsoft.com/azure/backup/quick-backup-vm-portal), [Azure PowerShell](https://docs.microsoft.com/azure/backup/quick-backup-vm-powershell) or Azure CLI(https://docs.microsoft.com/azure/backup/quick-backup-vm-cli). 

