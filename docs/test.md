# Test

## Test Matrix

You should test your extension in the distros which you want to support.

Here is the distro list:

* Ubuntu 12.04 and higher
* CentOS 6.5 and higher
* Oracle Linux 6.4.0.0.0 and higher
* openSUSE 13.1 and higher
* SUSE Linux Enterprise Server 11 SP3 and higher
* FreeBSD
* CoreOS

You can choose some or all of them to support.

## ASM or ARM

It's important to understand that Azure currently has two deployment models: Resource Manager, and classic. Make sure you understand [deployment models and tools](https://azure.microsoft.com/en-us/documentation/articles/azure-classic-rm/) before working with any Azure resource.

## Azure Templates

If you decide to support the scenario of deploying your extension using ARM Templates, you need to test it.

## Continuous Integration

There are many tools to do the CI work, for e.g. Jenkins, Concourse and so on.
