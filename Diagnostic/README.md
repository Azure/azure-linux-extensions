# Diagnostic Extension

Allow the owner of the Azure Virtual Machines to obtain diagnostic data for a Linux virtual machine.

Latest version is 3.0.103.

Linux Azure Diagnostic (LAD) extension version 3.0 is released with the following changes:

- Fully configurable Azure Portal metrics: Currently only available through CLI. Azure Portal configuration support will be coming soon.
- Syslog message collection is now opt-in (off by default), and customers can selectively pick and choose syslog facilities and minimum severities of their interests.
- Customers can now use CLI to configure their Azure Linux VMs for Azure Portal VM metrics charting experiences.
- Customers can now send any metrics and logs as Azure EventHubs events (additional Azure EventHubs charges may apply).
- Customers can also store any metrics and logs in Azure Storage JSON blobs (additional Azure Storage charges may apply).

Please note that LAD 3.0 is NOT compatible with LAD 2.3. Therefore, if you'd like to use LAD 3.0, you must first uninstall existing LAD 2.3 on your VMs and reinstall LAD 3.0. Please note that LAD 2.3 will be deprecated soon, so please do upgrade to LAD 3.0 as soon as possible. Currently only CLI-based installation is available, and the Azure Portal installation/configuration of LAD 3.0 will be coming soon.

This README.md file will be finalized very soon with the official documentation. In the meantime, please refer to [this document](virtual-machines-linux-diagnostic-extension-v3.md) for more details on LAD 3.0.

## Supported Linux Distributions

Please note that the distros/versions listed below apply only to Azure-endorsed Linux vendor
images. 3rd party BYOL/BYOS images (e.g., appliances) are not generally supported for the
Linux Diagnostic extension.

- Ubuntu 12.04 and higher.
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
