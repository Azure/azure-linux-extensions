# How to enable Azure Enhanced Monitoring on Linux VM

This is an instruction about how to enable Azure Enhanced Monitoring on Azure Linux VM.

## Prepare your develop machine

First of all, you need to prepare your develop machine to manipulate Linux VM on Azure. We have provided a script to automate this process. The script will install nodejs, npm and azure-cli on your develop machine. Then, it will install a nodejs package for configuring Azure Enhanced Monitoring Extension. Currently, the script supports Ubuntu, CentOS, SUSE etc. If you want to use other Linux distribution as your develop machine, you may need to [install nodejs manually](https://github.com/joyent/node/wiki/installing-node.js-via-package-manager).

```
curl -LO https://github.com/Azure/azure-linux-extensions/releases/download/azure-enhanced-monitor-1.0-alpha2/install.sh
sudo sh install.sh
```
## Configure Azure Enhanced Monitoring

1. After previous step, you should be able to use the command `setaem`. You could check this by running the following commands.

    ```
    sudo setaem -h
    sudo setaem -v 
    ```
2. Then, you need to configure your Azure Account with the following command.

    ```
    #If you are using an org. id.
    sudo azure login -u <user_name>
    ```
    Or

    ```
    sudo azure account import <publish_settings_file>
    ```
3. Now, you should be able to use the following command to enable Azure Enhanced Monitoring on your Azure Linux VM.

    ```
    sudo setaem <service_name> <vm_name>
    ```
    Or
    ```  
    #If service name is the same with vm.
    sudo setaem <vm_name>
    ```
4. Verify that the Enhanced Monitoring is active on the Azure Linux VM. Check if the file  /var/lib/AzureEnhancedMonitor/PerfCounters exists. If exists, display information collected by AEM with:

    ```
    cat /var/lib/AzureEnhancedMonitor/PerfCounters
    ```
    Then you will got some texts like:
    
    ```
    2;cpu;Current Hw Frequency;;0;2194.659;MHz;60;1444036656;saplnxmon;
    2;cpu;Max Hw Frequency;;0;2194.659;MHz;0;1444036656;saplnxmon;
    …
    …
    ```

Note: after the initial configuration it can take up to 10-15 minutes until the metrics file materializes in the VM.


## Build c lib for reading performance counters

We also provided a lib written in c for reading performance counters.

```
curl -LO https://github.com/Azure/azure-linux-extensions/releases/download/azure-enhanced-monitor-1.0-alpha2/clib.tar.gz
tar zxf clib.tar.gz
cd clib
make
```

You may also run 'sudo make install' to install the lib, then 'make test' to run some checks on your build.
