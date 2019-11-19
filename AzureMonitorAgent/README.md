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


 
### 1.1. Using Azure CLI Resource Manager

You can deploy the OmsAgent Extension by running:
```
az vm extension set --name AzureMonitorLinuxAgent --publisher Microsoft.Azure.Monitor --version <version> --resource-group <My Resource Group> --vm-name <My VM Name>
```

To update the version of the esisting installation of Azure Monitor Linux Agent extension on a VM, please add "--force-update" flag to the above command. (Currenty Waagent only supports this way of upgrading. Will update once we have more info from them.)


## Supported Linux Distributions 
 Currently Manually tested only on -
* CentOS Linux 6, and 7 (x64)
* Red Hat Enterprise Linux Server 6 and 7 (x64)
* Ubuntu 16.04 LTS, 18.04 LTS(x64)

Will Add more distros once they are tested

## Troubleshooting

* The status of the extension is reported back to Azure so that user can
see the status on Azure Portal
* All the extension installation and config files are unzipped into - 
`/var/lib/waagent/Microsoft.Azure.Monitor.AzureMonitorLinuxAgent-<version>/packages/`
and the tail of the output is logged into the log directory specified
in HandlerEnvironment.json and reported back to Azure
* The operation log of the extension is `/var/log/azure/Microsoft.Azure.Monitor.AzureMonitorLinuxAgent-<version>/extension.log` file.
