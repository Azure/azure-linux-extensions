VMBackup extension is used by Azure Backup service to provide application consistent backup for Linux VMs running in Azure. 

**Note:** This extension is not recommended to be installed outside Azure Backup service context. 

## Deploying the extension to a VM
This extension gets deployed as part of first scheduled backup of the VM post you configure VM for backup. You can configure VM to be backed up using [Azure Portal](https://docs.microsoft.com/azure/backup/quick-backup-vm-portal), [Azure PowerShell](https://docs.microsoft.com/azure/backup/quick-backup-vm-powershell) or Azure CLI(https://docs.microsoft.com/azure/backup/quick-backup-vm-cli). 

