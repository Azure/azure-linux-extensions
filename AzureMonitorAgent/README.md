# AzureMonitorLinuxAgent Extension
Allow the owner of the Azure Virtual Machines to install the Azure Monitor Linux Agent

The extension is currently in test versions 0.*

You can read the User Guide below.
* [Learn more: Azure Virtual Machine Extensions](https://azure.microsoft.com/en-us/documentation/articles/virtual-machines-extensions-features/)

Azure Monitor Linux Agent Extension can:
* Install the agent and pull configs from MCS

# User Guide

## 1. Deploying the Extension to a VM

You can deploy it using Azure CLI


 
### 1.1. Using [**Azure CLI**][azure-cli]

#### 1.1.1 Resource Manager

You can deploy the OmsAgent Extension by running:
```
az vm extension set \
  --resource-group myResourceGroup \
  --vm-name myVM \
  --name AzureMonitorLinuxAgent \
  --publisher Microsoft.Azure.Monitor \
  --version <version> \
```


## Supported Linux Distributions
* CentOS Linux 5,6, and 7 (x86/x64)
* Oracle Linux 5,6, and 7 (x86/x64)
* Red Hat Enterprise Linux Server 5,6 and 7 (x86/x64)
* Debian GNU/Linux 6, 7, and 8 (x86/x64)
* Ubuntu 12.04 LTS, 14.04 LTS, 15.04, 15.10, 16.04 LTS (x86/x64)
* SUSE Linux Enteprise Server 11 and 12 (x86/x64)

## Troubleshooting

* The status of the extension is reported back to Azure so that user can
see the status on Azure Portal
* All the extension installation and config files are unzipped into - 
`/var/lib/waagent/Microsoft.Azure.Monitor.AzureMonitorLinuxAgent-<version>/packages/`
and the tail of the output is logged into the log directory specified
in HandlerEnvironment.json and reported back to Azure
* The operation log of the extension is `/var/log/azure/Microsoft.Azure.Monitor.AzureMonitorLinuxAgent-<version>/extension.log` file.
