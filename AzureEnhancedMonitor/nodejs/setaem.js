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
var storage = require('azure-storage')
var storageMgmt = require('azure-mgmt-storage');
var computeMgmt = require('azure-mgmt-compute');
var rl = require('readline');

var readline = rl.createInterface({
      input: process.stdin,
      output: process.stdout
});

var readFile = Promise.denodeify(fs.readFile); 

/*Const*/
var CurrentScriptVersion = "1.0.0.0"

var aemExtPublisher = "Microsoft.OSTCExtensions"
//TODO change to AzureEnhacnedMonitroForLinux
var aemExtName = "AzureEnhancedMonitorForLinux.Test"
var aemExtVersion = "1.*"

var ladExtName = "LinuxDiagnosticTest3"
var ladExtPublisher = "Microsoft.OSTCExtensions"
var ladExtVersion = "1.0"

var ROLECONTENT = "IaaS"
var AzureEndpoint = "windows.net"
var BlobMetricsTable= "$MetricsMinutePrimaryTransactionsBlob"
/*End of Const*/



var setAzureVMEnhancedMonitorForLinux = function(svcName, vmName){
    var azureProfile;
    var currSubscription;
    var computeClient;
    var storageClient;
    var selectedVM;
    var accounts = {};
    var aemConfig = {};

    return getAzureProfile().then(function(profile){
        azureProfile = profile;
        return getDefaultSubscription(profile);
    }).then(function(subscription){
        console.log("[INFO]Found Subscription:");
        console.log(JSON.stringify(subscription, null, 4));
        currSubscription = subscription;
        var cred = getCloudCredential(subscription);
        computeClient = computeMgmt.createComputeManagementClient(cred);
        storageClient = storageMgmt.createStorageManagementClient(cred);
    }).then(function(){
        return getVirtualMachine(computeClient, svcName, vmName);
    }).then(function(vm){
        console.log("[INFO]Found VM:");
        console.log(JSON.stringify(vm, null, 4));
        selectedVM = vm;

        var cpuOverCommitted = 0;
        if(selectedVM.roleSize === 'ExtralSmall'){
            cpuOverCommitted = 1
        }
        aemConfig['vm.size'] = selectedVM.roleSize;
        aemConfig['vm.roleinstance'] = selectedVM.roleName;
        aemConfig['vm.role'] = 'IaaS';
        //TODO really need this one?
        //aemConfig['vm.deploymentid'] = selectedVM.deploymentId;
        aemConfig['vm.memory.isovercommitted'] = 0;
        aemConfig['vm.cpu.isovercommitted'] = cpuOverCommitted;
        aemConfig['script.version'] = CurrentScriptVersion;
        aemConfig['verbose'] = 0;
    }).then(function(){
        var osdisk = selectedVM.oSVirtualHardDisk;
        var osdiskAccount = getStorageAccountFromUri(osdisk.mediaLink);
        aemConfig['osdisk.account'] = osdiskAccount;
        aemConfig['osdisk.name'] = selectedVM.oSVirtualHardDisk.name;
        accounts[osdiskAccount] = null;
        for(var i = 0; i < selectedVM.dataVirtualHardDisks.length; i++){
            var dataDisk = selectedVM.dataVirtualHardDisks[i];
            var datadiskAccount = getStorageAccountFromUri(dataDisk.mediaLink);
            accounts[datadiskAccount] = null;
            //The default lun value is 0
            var lun = dataDisk.logicalUnitNumber || 0;
            aemConfig['disk.lun.' + i] = lun;
            aemConfig['disk.name.' + i] = dataDisk.name;
            aemConfig['disk.account.' + i] = datadiskAccount;
        }
        var promises = [];
        Object.keys(accounts).forEach(function(accountName){
            var promise = getStorageKey(accountName).then(function(accountKey){
                //TODO not implemented
                accounts[accountName]=accountKey;
            }).then(function(){
                return setStorageStorageAnalytics(accountName);
            });
            promises.push(promise);
        });
        return Promise.all(promises);
    }).then(function(){
        //TODO remove debug output
        console.log(JSON.stringify(aemConfig, null, 4)) 
    });
}

var getStorageKey = function(accountName){
    return new Promise(function(fullfill, reject){
        //TODO not implemented
        fullfill(null);
    });
};

var setStorageStorageAnalytics = function(accountName){
    return new Promise(function(fullfill, reject){
        //TODO not implemented
        fullfill(null);
    });
};

var getStorageAccountFromUri = function(uri){
    var match = /http:\/\/(.*)\..*/.exec(uri);
    if(match){
        return match[1];
    }
}

var updateVirtualMachine = function (client, vm){

}

var getVirtualMachine = function(client, svcName, vmName){
    return new Promise(function(fullfill, reject){
        client.virtualMachines.get(svcName, vmName, vmName, function(err, vm){
            if(err){
                reject(err);
            } else {
                fullfill(vm);
            }
        });
    });
}

var getCloudCredential = function(subscription){
    var cred;
    if(subscription.credential.type === 'cert'){
        cred = compute.createCertificateCloudCredentials({
            subscriptionId:subscription.id ,
            pem:subscription.credential.cert.key + subscription.cert.cert
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
        var defaultSubscription = null;
        if(profile == null || profile.subscriptions == null 
                || profile.subscriptions.length == 0){
            throw "No subscriptions found."
        }
        return profile;
    });
}

var getDefaultSubscription = function(profile){
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
        throw "Not subscription is selected."
    }

    if(defaultSubscription.username){
        return getTokenCredential(defaultSubscription);
    } else if(subscription.managementCertificate){
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
            if(token.userId === subscription.username){
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
        vmName = process.argv[2];
        svcName = vmName;
    } else{
        usage();
        process.exit(1);
    }

    setAzureVMEnhancedMonitorForLinux(svcName, vmName).done(function(){
        console.log("[INFO] Azure Enhanced Monitoring Extension " + 
                    "configuration updated.");
        console.log("[INFO] It can take up to 15 Minutes for the " + 
                    "monitoring data to appear in the  system.");
        process.exit(0);
    }, function(err){
        console.log(err);
        console.log(err.stack);
        process.exit(-1);
    });
}

var usage = function(){
    console.log("");
    console.log("Usage:");
    console.log("    setaem <service_name> <vm_name>");
    console.log("  or");
    console.log("    setaem <vm_name>");
    console.log("");
    console.log("  *if service_name and vm_name are the same, " + 
                   "service_name could be omitted.");
    console.log("");
}

main();
