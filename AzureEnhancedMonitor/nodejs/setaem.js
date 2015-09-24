#!/usr/bin/env node

//
// Copyright (c) Microsoft and contributors.  All rights reserved.
// 
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//   http://www.apache.org/licenses/LICENSE-2.0
// 
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// 
// See the License for the specific language governing permissions and
// limitations under the License.
// 
'use strict';

var fs = require('fs');
var path = require('path');
var Promise = require('promise');
var common = require('azure-common');
var storage = require('azure-storage');
var storageMgmt = require('azure-mgmt-storage');
var computeMgmt = require('azure-mgmt-compute');
var readFile = Promise.denodeify(fs.readFile); 

var debug = 0;

/*Const*/
var CurrentScriptVersion = "1.0.0.0";

var aemExtPublisher = "Microsoft.OSTCExtensions";
var aemExtName = "AzureEnhancedMonitorForLinux";
var aemExtVersion = "1.0";

var ladExtName = "LinuxDiagnostic";
var ladExtPublisher = "Microsoft.OSTCExtensions";
var ladExtVersion = "2.0";

var ROLECONTENT = "IaaS";
var AzureEndpoint = "windows.net";
var BlobMetricsMinuteTable= "$MetricsMinutePrimaryTransactionsBlob";
var BlobMetricsHourTable= "$MetricsMinutePrimaryTransactionsBlob";
var ladMetricesTable= "";
/*End of Const*/

var AemConfig = function(){
    this.prv = [];
    this.pub = [];
};

AemConfig.prototype.setPublic = function(key, value){
    this.pub.push({
        'key' : key,
        'value' : value
    });
};


AemConfig.prototype.setPrivate = function(key, value){
    this.prv.push({
        'key' : key,
        'value' : value
    });
};

AemConfig.prototype.getPublic = function(){
    return {
        'key' : aemExtName + "PublicConfigParameter",
        'value' : JSON.stringify({'cfg' : this.pub}),
        'type':'Public'
    }
};

AemConfig.prototype.getPrivate = function(){
    return {
        'key' : aemExtName + "PrivateConfigParameter",
        'value' : JSON.stringify({'cfg' : this.prv}),
        'type':'Private'
    }
};

var setAzureVMEnhancedMonitorForLinux = function(svcName, vmName){
    var azureProfile;
    var currSubscription;
    var computeClient;
    var storageClient;
    var selectedVM;
    var osdiskAccount;
    var accounts = [];
    var aemConfig = new AemConfig();

    return getAzureProfile().then(function(profile){
        azureProfile = profile;
        return getDefaultSubscription(profile);
    }).then(function(subscription){
        console.log("[INFO]Using subscription: " + subscription.name);
        debug && console.log(JSON.stringify(subscription, null, 4));
        currSubscription = subscription;
        var cred = getCloudCredential(subscription);
        var baseUri = subscription.managementEndpointUrl
        computeClient = computeMgmt.createComputeManagementClient(cred, baseUri);
        storageClient = storageMgmt.createStorageManagementClient(cred, baseUri);
    }).then(function(){
        return getVirtualMachine(computeClient, svcName, vmName);
    }).then(function(vm){
        //Set vm role basic config
        console.log("[INFO]Found VM: " + vm.roleName);
        debug && console.log(JSON.stringify(vm, null, 4));
        selectedVM = vm;
        var cpuOverCommitted = 0;
        if(selectedVM.roleSize === 'ExtralSmall'){
            cpuOverCommitted = 1
        }
        aemConfig.setPublic('vmsize', selectedVM.roleSize);
        aemConfig.setPublic('vm.roleinstance', selectedVM.roleName);
        aemConfig.setPublic('vm.role', 'IaaS');
        aemConfig.setPublic('vm.memory.isovercommitted', 0);
        aemConfig.setPublic('vm.cpu.isovercommitted', cpuOverCommitted);
        aemConfig.setPublic('script.version', CurrentScriptVersion);
        aemConfig.setPublic('verbose', '0');
    }).then(function(){
        //Set vm disk config
        var osdisk = selectedVM.oSVirtualHardDisk;
        osdiskAccount = getStorageAccountFromUri(osdisk.mediaLink);
        console.log("[INFO]Adding configure for OS disk.");
        aemConfig.setPublic('osdisk.account', osdiskAccount);
        aemConfig.setPublic('osdisk.name', selectedVM.oSVirtualHardDisk.name);
        aemConfig.setPublic('osdisk.connminute', osdiskAccount + ".minute");
        aemConfig.setPublic('osdisk.connhour', osdiskAccount + ".hour");
        accounts.push({
            name: osdiskAccount,
        });
        for(var i = 0; i < selectedVM.dataVirtualHardDisks.length; i++){
            var dataDisk = selectedVM.dataVirtualHardDisks[i];
            console.log("[INFO]Adding configure for data disk: " + 
                        dataDisk.name);
            var datadiskAccount = getStorageAccountFromUri(dataDisk.mediaLink);
            accounts.push({
                name:datadiskAccount
            });
            //The default lun value is 0
            var lun = dataDisk.logicalUnitNumber || 0;
            aemConfig.setPublic('disk.lun.' + i, lun);
            aemConfig.setPublic('disk.name.' + i, dataDisk.name);
            aemConfig.setPublic('disk.account.' + i, datadiskAccount);
            aemConfig.setPublic('disk.connminute.' + i, 
                                datadiskAccount + ".minute");
            aemConfig.setPublic('disk.connhour.' + i, datadiskAccount + ".hour");
        }
    }).then(function(){
        //Set storage account config
        var promises = [];
        Object(accounts).forEach(function(account){
            var promise = getStorageAccountKey(storageClient, account.name)
              .then(function(accountKey){
                account.key = accountKey
                aemConfig.setPrivate(account.name + ".minute.key", accountKey);
                aemConfig.setPrivate(account.name + ".hour.key", accountKey);
                return getStorageAccountEndpoints(storageClient, account.name);
            }).then(function(endpoints){
                var tableEndpoint;
                var blobEndpoint;
                endpoints.forEach(function(endpoint){
                    if(endpoint.match(/.*table.*/)){
                        tableEndpoint = endpoint;
                    }else if(endpoint.match(/.*blob.*/)){
                        blobEndpoint = endpoint;
                    }
                });
                account.tableEndpoint = tableEndpoint;
                account.blobEndpoint = blobEndpoint;
                var minuteUri = tableEndpoint + BlobMetricsMinuteTable;
                var hourUri = tableEndpoint + BlobMetricsHourTable;
                account.minuteUri = minuteUri
                aemConfig.setPublic(account.name + ".minute.uri", minuteUri);
                aemConfig.setPublic(account.name + ".hour.uri", hourUri);
                aemConfig.setPublic(account.name + ".minute.name", account.name);
                aemConfig.setPublic(account.name + ".hour.name", account.name);
            }).then(function(){
                return checkStorageAccountAnalytics(account.name, 
                                                    account.key,
                                                    account.blobEndpoint);
            });
            promises.push(promise);
        });
        return Promise.all(promises);
    }).then(function(){
        //Set Linux diagnostic config
        aemConfig.setPublic("wad.isenabled", 1);
        aemConfig.setPublic("wad.name", accounts[0].name);
        aemConfig.setPrivate("wad.key", accounts[0].key);
        var ladUri = accounts[0].tableEndpoint + ladMetricesTable;
        console.log("[INFO]Your endpoint is: "+accounts[0].tableEndpoint);
        aemConfig.setPublic("wad.uri", ladUri);
    }).then(function(){
        //Update vm
        var extensions = [];
        var ladExtConfig = {
            'name' : ladExtName,
            'referenceName' : ladExtName,
            'publisher' : ladExtPublisher,
            'version' : ladExtVersion,
            'state': 'Enable',
            'resourceExtensionParameterValues' : [{
                'key' : ladExtName + "PrivateConfigParameter",
                'value' : JSON.stringify({
                    'storageAccountName' : accounts[0].name,
                    'storageAccountKey' : accounts[0].key,
                    'endpoint' : accounts[0].tableEndpoint.substring((accounts[0].tableEndpoint.search(/\./)) + 1, accounts[0].tableEndpoint.length)
                }),
                'type':'Private'
            }]
        };
        var aemExtConfig = {
            'name' : aemExtName,
            'referenceName' : aemExtName,
            'publisher' : aemExtPublisher,
            'version' : aemExtVersion,
            'state': 'Enable',
            'resourceExtensionParameterValues' : [
                aemConfig.getPublic(), 
                aemConfig.getPrivate()
            ]
        };
        extensions.push(ladExtConfig);
        extensions.push(aemExtConfig);
        selectedVM.provisionGuestAgent = true;
        selectedVM.resourceExtensionReferences = extensions;
        console.log("[INFO]Updating configuration for VM: " + selectedVM.roleName);
        console.log("[INFO]This could take a few minutes. Please wait.")
        debug && console.log(JSON.stringify(selectedVM, null, 4)) 
        return updateVirtualMachine(computeClient, svcName, vmName, selectedVM);
    });
}

var updateVirtualMachine = function (client, svcName, vmName, parameters){
    return new Promise(function(fullfill, reject){
        client.virtualMachines.update(svcName, vmName, vmName, parameters, 
                                      function(err, ret){
            if(err){
                reject(err)
            } else {
                fullfill(ret);
            } 
        });
    });
}

var getDeployment = function(computeClient, svcName){
    return  new Promise(function(fullfill, reject){
        computeClient.deployments.getBySlot(svcName, "Production", 
                                            function(err, ret){
            if(err){
                reject(err)
            } else {
                fullfill(ret);
            }
        });
    });
};

var getStorageAccountEndpoints = function(storageClient, accountName){
    return new Promise(function(fullfill, reject){
        storageClient.storageAccounts.get(accountName, function(err, account){
            if(err){
                reject(err);
            } else {
                fullfill(account.storageAccount.properties.endpoints);
            }
        });
    });
};

var getStorageAccountKey = function(storageClient, accountName){
    return new Promise(function(fullfill, reject){
        storageClient.storageAccounts.getKeys(accountName, function(err, keys){
            if(err){
                reject(err);
            } else {
                fullfill(keys.primaryKey);
            } 
        });
    });
};

var getStorageAccountAnalytics = function(accountName, accountKey, host){
    return new Promise(function(fullfill, reject){
        var blobService = storage.createBlobService(accountName, accountKey, 
                                                    host); 
        blobService.getServiceProperties(null, function(err, properties, resp){
            if(err){
                reject(err)
            } else {
                fullfill(properties);
            }
        });
    });
};

var analyticsSettings = {
    Logging:{ 
        Version: '1.0',
        Delete: true,
        Read: true,
        Write: true,
        RetentionPolicy: { Enabled: true, Days: 13 } },
    HourMetrics:{ 
        Version: '1.0',
        Enabled: true,
        IncludeAPIs: true,
        RetentionPolicy: { Enabled: true, Days: 13 } },
    MinuteMetrics:{ 
        Version: '1.0',
        Enabled: true,
        IncludeAPIs: true,
        RetentionPolicy: { Enabled: true, Days: 13 } 
    } 
};

var checkStorageAccountAnalytics = function(accountName, accountKey, host){
   return getStorageAccountAnalytics(accountName, accountKey, host)
     .then(function(properties){
        if(!properties 
                || !properties.Logging
                || !properties.Logging.Read 
                || !properties.Logging.Write
                || !properties.Logging.Delete
                || !properties.MinuteMetrics
                || !properties.MinuteMetrics.Enabled
                || !properties.MinuteMetrics.RetentionPolicy
                || !properties.MinuteMetrics.RetentionPolicy.Enabled
                || !properties.MinuteMetrics.RetentionPolicy.Days
                || properties.MinuteMetrics.RetentionPolicy.Days == 0
                ){
            console.log("[INFO] Turn on storage analytics for: " + accountName)
            return setStorageAccountAnalytics(accountName, accountKey, host,
                                              analyticsSettings);
        }
   });
}

var setStorageAccountAnalytics = function(accountName, accountKey, 
                                          host, properties){
    return new Promise(function(fullfill, reject){
        var blobService = storage.createBlobService(accountName, accountKey,
                                                    host); 
        blobService.setServiceProperties(properties, null, 
                                         function(err, properties, resp){
            if(err){
                reject(err)
            } else {
                fullfill(properties);
            }
        });
    });
};

var getStorageAccountFromUri = function(uri){
    var match = /https:\/\/(.+?)\..*/.exec(uri);
    if(match){
        return match[1];
    }
}

var getVirtualMachine = function(computeClient, svcName, vmName){
    return new Promise(function(fullfill, reject){
        computeClient.deployments.getBySlot(svcName, "Production", 
                                            function(err, deployments){
            if(err){
                reject(err);
            } else {
                var vm;
                deployments.roles.every(function(role){
                    if(role.roleName == vmName){
                        vm = role;
                        return false; 
                    }else{
                        return true; 
                    }
                });
                if(vm){
                    fullfill(vm);
                }else{
                    reject("VM not found."); 
                }
            }
        });
    });
}

var getCloudCredential = function(subscription){
    var cred;
    if(subscription.credential.type === 'cert'){
        cred = computeMgmt.createCertificateCloudCredentials({
            subscriptionId:subscription.id ,
            cert:subscription.managementCertificate.cert,
            key:subscription.managementCertificate.key,
        });
    }else{//if(subscription.credential.type === 'token'){
       cred = new common.TokenCloudCredentials({
            subscriptionId : subscription.id,
            token : subscription.credential.token  
       });
    } 
    return cred;
}

var getAzureProfile = function(){
    var profileJSON = path.join(getUserHome(), ".azure/azureProfile.json");
    return readFile(profileJSON).then(function(result){
        var profile = JSON.parse(result);
        return profile;
    });
}

var getDefaultSubscription = function(profile){
    debug && console.log(JSON.stringify(profile, null, 4))
    if(profile == null || profile.subscriptions == null 
            || profile.subscriptions.length == 0){
        throw "No subscription found."
    }
    console.log("[INFO]Found available subscriptions:");
    console.log("");
    console.log("    Id\t\t\t\t\t\tName");
    console.log("    --------------------------------------------------------");
    profile.subscriptions.forEach(function(subscription){
        console.log("    " + subscription.id + "\t" + subscription.name);
    });
    console.log("");
    var defaultSubscription;
    profile.subscriptions.every(function(subscription, index, arr){
        if(subscription.isDefault){
            defaultSubscription = subscription;
            return false;
        } else {
            return true;
        }
    });

    if(defaultSubscription == null){
        console.log("[WARN]No subscription is selected.");
        defaultSubscription = profile.subscriptions[0];
        console.log("[INFO]The first subscription will be used.");
        console.log("[INFO]You could use the following command to select " + 
                    "another subscription.");
        console.log("");
        console.log("    azure account set [<subscript_id>|<subscript_name>]");
        console.log("");
    }
    if(defaultSubscription.user){
        return getTokenCredential(defaultSubscription);
    } else if(defaultSubscription.managementCertificate){
        return getCertCredential(defaultSubscription);
    } else {
        throw "Unknown subscription type.";
    }
}

var getTokenCredential = function(subscription){
    var tokensJSON = path.join(getUserHome(), ".azure/accessTokens.json");
    return readFile(tokensJSON).then(function(result){
        var tokens = JSON.parse(result);
        tokens.every(function(token, index, arr){
            if(token.userId === subscription.user.name){
                subscription.credential = {
                    type : 'token',
                    token : token.accessToken
                };
                return false
            }
        });
        return subscription;
    });
}

var getCertCredential = function(subscription){
    subscription.credential = {
        type : 'cert',
        cert : subscription.managementCertificate
    };
    return subscription;
}

function getUserHome() {
  return process.env[(process.platform == 'win32') ? 'USERPROFILE' : 'HOME'];
}

var main = function(){
    var svcName = null;
    var vmName = null;
    if(process.argv.length === 4){
        vmName = process.argv[3];
        svcName = process.argv[2];
    } else if(process.argv.length === 3){
        if(process.argv[2] === "--help" || process.argv[2] === "-h"){
            usage();
            process.exit(0);
        } else if(process.argv[2] === "--version" || process.argv[2] === "-v"){
            console.log(CurrentScriptVersion);
            process.exit(0);
        }
        vmName = process.argv[2];
        svcName = vmName;
    } else{
        usage();
        process.exit(1);
    }

    setAzureVMEnhancedMonitorForLinux(svcName, vmName).done(function(){
        console.log("[INFO]Azure Enhanced Monitoring Extension " + 
                    "configuration updated.");
        console.log("[INFO]It can take up to 15 Minutes for the " + 
                    "monitoring data to appear in the system.");
        process.exit(0);
    }, function(err){
        if(err && err.statusCode == 401){
            console.error("[ERROR]Token expired. " + 
                          "Please run the following command to login.");
            console.log("    ");
            console.log("    azure login -u <user_name>");
            console.log("or");
            console.log("    azure account import <pem_file>");
            process.exit(-1);
        }else{
            console.log(err);
            console.log(err.stack);
            process.exit(-1);
        }
    });
}

var usage = function(){
    console.log("");
    console.log("Usage:");
    console.log("    setaem <service_name> <vm_name>");
    console.log("or");
    console.log("    setaem <vm_name>");
    console.log("");
    console.log("  *if service_name and vm_name are the same, " + 
                "service_name could be omitted.");
    console.log("");
    console.log("    ");
    console.log("    -h, --help ");
    console.log("        Print help.");
    console.log("    ");
    console.log("    -v, --version");
    console.log("        Print version.");
    console.log("    ");
}

main();
