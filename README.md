# Linux extensions for Microsoft Azure IaaS

This project provides the source code of Linux extensions for Microsoft Azure IaaS

# Extension List

* Custom Script Extension
  Allow the owner of the Azure VM to run script Azure storage during or after VM provisioning
  * it can be installed thru Azure RESTFUL API for extension
  * it supports major Linux and FreeBSD distro
  * it leverage the Azure SDK for python to download the custom script from the Azure storage with storage account and key given
  * bash and python script are supported
  * the execution result of the custom script is report back to Azure
  * status of the extension is reported back to Azure so that you can see the status on Azure Portal
  
* VM Access Extension
  Allow the owner of get back the SSH access to the VM 
  * it can be installed thru Azure RESTFUL API for extension
  * it supports major Linux and FreeBSD distro
  * it can reset the password of the original sudo user. Password is encrypted before transmission and decrypted by the extension in VM.
  * it can create a new sudo user
  * it can set the public host key with the key given or it can reset the public host key provided during VM provisioning 
  * it can open the SSH port   
  * status of the extension is reported back to Azure so that you can see the status on Azure Portal
  
* Test Handler Extension
  This extension is an extension example  
