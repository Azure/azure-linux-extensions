# How to enable Azure Enhanced Monitoring on Linux VM

This is an instruction about how to enable Azure Enhanced Monitoring(AEM) on Azure Linux VM. 

## Install Azure CLI

First of all, you need to to install [Azure CLI][azure-cli]

**NOTE** This feature is currently on developing. You need to install it from github by running the following command.
```
npm -g install git+https://github.com/yuezh/azure-xplat-cli.git#dev
```

## Configure Azure Enhanced Monitoring

1. Login with your Azure account

    ```
    azure login
    ```
2. Switch to azure resource management mode

    ```
    azure config mode arm
    ```
3. Enable Azure Enhanced Monitoring

    ```
    azure vm enable-aem <resource-group-name> <vm-name>
    ```  
4. Verify that the Azure Enhanced Monitoring is active on the Azure Linux VM. Check if the file  /var/lib/AzureEnhancedMonitor/PerfCounters exists. If exists, display information collected by AEM with:

    ```
    cat /var/lib/AzureEnhancedMonitor/PerfCounters
    ```
    Then you will get output like:
    
    ```
    2;cpu;Current Hw Frequency;;0;2194.659;MHz;60;1444036656;saplnxmon;
    2;cpu;Max Hw Frequency;;0;2194.659;MHz;0;1444036656;saplnxmon;
    …
    …
    ```

[azure-cli]: https://azure.microsoft.com/en-us/documentation/articles/xplat-cli/
