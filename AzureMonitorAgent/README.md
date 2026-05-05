# AzureMonitorLinuxAgent Extension
Allow the owner of the Azure Virtual Machines to install the Azure Monitor Linux Agent

You can read the User Guide below.
* [Learn more: Azure Virtual Machine Extensions](https://azure.microsoft.com/en-us/documentation/articles/virtual-machines-extensions-features/)

Azure Monitor Linux Agent Extension can:
* Install the agent and pull configs 

# User Guide

## 1. Deploying the Extension to a VM

You can deploy it using Azure CLI


 
### 1.1. Using Azure CLI Resource Manager

You can view the availability of the Azure Monitor Linux Agent extension versions in each region by running:

```
az vm extension image list-versions -l <region> --name AzureMonitorLinuxAgent -p Microsoft.Azure.Monitor
```

You can deploy the Azure Monitor Linux Agent Extension by running:
```
az vm extension set --name AzureMonitorLinuxAgent --publisher Microsoft.Azure.Monitor --version <version> --resource-group <My Resource Group> --vm-name <My VM Name>
```

To update the version of the esisting installation of Azure Monitor Linux Agent extension on a VM, please add "--force-update" flag to the above command. (Currenty Waagent only supports this way of upgrading. Will update once we have more info from them.)


## Supported Linux Distributions 
* [Azure Monitor Agent Supported Operating Systems](https://learn.microsoft.com/en-us/azure/azure-monitor/agents/azure-monitor-agent-supported-operating-systems#linux-operating-systems)
