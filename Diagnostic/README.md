# Linux Diagnostic Extension (LAD)

Allow the owner of a Linux-based Azure Virtual Machine to obtain diagnostic data.

Current version is 3.0.111.

Linux Azure Diagnostic (LAD) extension version 3.0 is released with the following changes:

- Fully configurable Azure Portal metrics, including a broader set of metrics to choose from.
- Syslog message collection is now opt-in (off by default), and customers can selectively pick and choose syslog facilities and minimum severities of their interests.
- Customers can now use CLI to configure their Azure Linux VMs for Azure Portal VM metrics charting experiences.
- Customers can now send any metrics and logs as Azure EventHubs events (additional Azure EventHubs charges may apply).
- Customers can also store any metrics and logs in Azure Storage JSON blobs (additional Azure Storage charges may apply).

LAD 3.0 is NOT compatible with LAD 2.3. Users of LAD 2.3 must first uninstall that extension before installing LAD 3.0.

LAD 3.0 is installed and configured via Azure CLI, Azure PowerShell cmdlets, or Azure Resource Manager templates. The Azure Portal controls installation and configuration of LAD 2.3 only. The Azure Metrics UI can display performance counters collected by either version of LAD.

Please refer to [this document](https://docs.microsoft.com/azure/virtual-machines/linux/diagnostic-extension) for more details on configuring and using LAD 3.0. The tests folder contains [a sample JSON configuration](https://raw.githubusercontent.com/Azure/azure-linux-extensions/master/Diagnostic/tests/lad_2_3_compatible_portal_pub_settings.json) which sets LAD 3.0 to collecting exactly the same metrics and logs as the default configuration for LAD 2.3 collected. 

## Supported Linux Distributions

Please note that the distros/versions listed below apply only to Azure-endorsed Linux vendor
images. 3rd party BYOL/BYOS images (e.g., appliances) are not generally supported for the
Linux Diagnostic extension.

- Ubuntu 14.04 and higher.
- CentOS 6.5 and higher
- Oracle Linux 6.4.0.0.0 and higher
- OpenSUSE 13.1 and higher
- SUSE Linux Enterprise Server 11 and higher
- Debian 7 and higher (7 is now supported with static mdsd build)
- RHEL 6.7 and higher

## Debug

- The status of the extension is reported back to Azure so that user can see the status on Azure Portal
- The operation log of the extension is `/var/log/azure/Microsoft.Azure.Diagnostics.LinuxDiagnostic/<version>/` directory.

[azure-powershell]: https://azure.microsoft.com/en-us/documentation/articles/powershell-install-configure/
[azure-cli]: https://azure.microsoft.com/en-us/documentation/articles/xplat-cli/
[arm-template]: http://azure.microsoft.com/en-us/documentation/templates/ 
[arm-overview]: https://azure.microsoft.com/en-us/documentation/articles/resource-group-overview/
