# Diagnostic Extension

Allow the owner of the Azure Virtual Machines to obtain diagnostic data for a Linux virtual machine.

Latest version is 3.0.101.

Linux Azure Diagnostic extension ver. 3.0 documentation is currently in development and will be updated here very soon.

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
