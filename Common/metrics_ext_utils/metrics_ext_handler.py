import urllib2
import json
import os

imdsurl = "http://169.254.169.254/metadata/instance?api-version=2019-03-11"

def start_me():
    pass

def stop_me():
    pass

def setup_me_service(configFolder):

    me_service_path = "/lib/systemd/system/metrics-extension.service"
    metrics_ext_bin = "usr/sbin/MetricsExtension"

    if not os.path.exists(configFolder):
        raise Exception("Metrics extension config directory does not exist. Failed to setup ME service.")
        return False
   
    if not os.path.isfile(metrics_ext_bin):
        raise Exception("Metrics Extension binary does not exist. Failed to setup ME service.")
        return False       

    if os.path.isfile(me_service_path):
        os.system(r"sed -i 's+%ME_DATA_DIRECTORY%+{1}+' {0}".format(me_service_path, configFolder))
        daemon_reload_status = os.system("sudo systemctl daemon-reload")
    else:
        raise Exception("Metrics extension service file does not exist. Failed to setup ME service.")
        return False

def create_metrics_extension_conf(az_resource_id, aad_url):
    conf_dict = { 
        "timeToTerminateInMs": 4000, 
        "configurationExpirationPeriodInMinutes": 1440, 
        "configurationQueriesFrequencyInSec": 900, 
        "configurationQueriesTimeoutInSec": 30, 
        "maxAcceptedMetricAgeInSec": 1200, 
        "maxDataEtwDelayInSec": 3, 
        "maxPublicationAttemptsPerMinute": 5, 
        "maxPublicationBytesPerMinute": 10000000, 
        "maxPublicationMetricsPerMinute": 500000, 
        "maxPublicationPackageSizeInBytes": 2500000, 
        "maxRandomPublicationDelayInSec": 25, 
        "metricsSerializationVersion": 4, 
        "minGapBetweenPublicationAttemptsInSec": 5, 
        "publicationTimeoutInSec": 30, 
        "staleMonitoringAccountsPeriodInMinutes": 20, 
        "internalMetricPublicationTimeoutInMinutes": 20, 
        "dnsResolutionPeriodInSec": 180, 
        "maxAggregationQueueSize": 500000, 
        "initialAccountConfigurationLoadWaitPeriodInSec": 20, 
        "etwMinBuffersPerCore": 2, 
        "etwMaxBuffersPerCore": 16, 
        "etwBufferSizeInKb": 1024, 
        "internalQueueSizeManagementPeriodInSec": 900, 
        "etwLateHeartbeatAllowedCycleCount": 24, 
        "etwSampleRatio": 0, 
        "maxAcceptedMetricFutureAgeInSec": 1200, 
        "aggregatedMetricDiagnosticTracePeriod": 900, 
        "aggregatedMetricDiagnosticTraceMaxSize": 100, 
        "enableMetricMetadataPublication": True, 
        "enableDimensionTrimming": True, 
        "shutdownRequestedThreshold": 5, 
        "internalMetricProductionLevel": 0, 
        "maxPublicationWithoutResponseTimeoutInSec": 300, 
        "maxConfigQueryWithoutResponseTimeoutInSec": 300, 
        "maxThumbprintsPerAccountToLoad": 100, 
        "maxPacketsToCaptureLocally": 0, 
        "maxNumberOfRawEventsPerCycle": 1000000, 
        "publicationSimulated": False, 
        "maxAggregationTimeoutPerCycleInSec": 20, 
        "maxRawEventInputQueueSize": 2000000, 
        "publicationIntervalInSec": 60, 
        "interningSwapPeriodInMin": 240, 
        "interningClearPeriodInMin": 5, 
        "enableParallelization": True, 
        "enableDimensionSortingOnIngestion": True, 
        "rawEtwEventProcessingParallelizationFactor": 1, 
        "maxRandomConfigurationLoadingDelayInSec": 120, 
        "aggregationProcessingParallelizationFactor": 1, 
        "aggregationProcessingPerPartitionPeriodInSec": 20, 
        "aggregationProcessingParallelizationVolumeThreshold": 500000, 
        "useSharedHttpClients": True, 
        "loadFromConfigurationCache": True, 
        "restartByDateTimeUtc": "0001-01-01T00:00:00", 
        "restartStableIdTarget": "", 
        "enableIpV6": False, 
        "disableCustomMetricAgeSupport": False, 
        "globalPublicationCertificateThumbprint": "", 
        "maxHllSerializationVersion": 2, 
        "enableNodeOwnerMode": False, 
        "performAdditionalAzureHostIpV6Checks": False, 
        "compressMetricData": False, 
        "publishMinMaxByDefault": True, 
        "azureResourceId": "/SUBSCRIPTIONS/[subid]/RESOURCEGROUPS/sjomswsrg/PROVIDERS/Microsoft.Compute/virtualMachines/sjomsvm2", 
        "aadAuthority": "https://login.windows.net/db71eb40-a96d-410d-880a-e4803f311f43", 
        "aadTokenEnvVariable": "MSIAuthToken" 
    }
    conf_dict["azureResourceId"] = az_resource_id
    conf_dict["aadAuthority"] = aad_url

    conf_json = json.dumps(conf_dict)
    return conf_json

def create_custom_metrics_conf():
    conf_dict = { 
        "version": 17, 
        "maxMetricAgeInSeconds": 0, 
        "endpointsForClientForking": [], 
        "homeStampGslbHostname": "eastus.prod.hot.ingestion.msftcloudes.com", 
        "endpointsForClientPublication": [ 
            "https://eastus.prod.hot.ingestion.msftcloudes.com/api/v1/ingestion/ingest" 
        ] 
    } 
    conf_json = json.dumps(conf_dict)
    return conf_json

def get_handler_vars():
    logFolder = "./metricsext.log"
    configFolder = "./me_configs"
    handler_env_path = os.path.abspath(os.path.join(os.path.dirname( __file__ ), '..', 'HandlerEnvironment.json'))
    if os.path.exists(handler_env_path):
        with open(handler_env_path, 'r') as handler_env_file:
            handler_env_txt = handler_env_file.read()
        handler_env = json.loads(handler_env_txt)
        if type(handler_env) == list:
            handler_env = handler_env[0]
        if "handlerEnvironment" in handler_env:
            if "logFolder" in handler_env["handlerEnvironment"]:
                logFolder = handler_env["handlerEnvironment"]["logFolder"]
            if "configFolder" in handler_env["handlerEnvironment"]:
                configFolder = handler_env["handlerEnvironment"]["configFolder"]
    
    return logFolder, configFolder


def setup_me():

    #query imds to get the required information 
    # req = urllib2.Request(imdsurl, headers={'Metadata':'true'})
    # res = urllib2.urlopen(req)
    # data = json.loads(res.read())
    data = json.loads('''{"compute":{"azEnvironment":"AzurePublicCloud","customData":"","location":"eastus2","name":"ub16","offer":"UbuntuServer","osType":"Linux","placementGroupId":"","plan":{"name":"","product":"","publisher":""},"platformFaultDomain":"0","platformUpdateDomain":"0","provider":"Microsoft.Compute","publicKeys":[{"keyData":"ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQDJmcpHCPcSg+J0S7pbqj5X08iaIMulAc7qq1iLPrcSu04alVWQTFE58f3LbabDwDBhiXIgWO4W4/26l0+arTLOj6TJe9EiaabAYniUglC0ChbgMTjAvXQCbtwLc2yo30Uh4DbdFhEo9UXG/AeYdwvt7TCVYFrd/seGQ+7dENcFdyd4rRs1hZdMxKil+Tx0dBoFE+IEydY6PSm48qgq7XlteLAT6q/Gqpo4wVqboyTcal+QIZftDfSlJ2G+Asem/mjWj9U1nhJeBcRy2JWOSJeKgojCI3WZUMVly6lkxbX6c1UYHkT53w/tFxMehm9TUUiviOTZOAXIE6Yj/7KWlGmosJPTCA6VSRr3b5RS3lgRerOIwwb/FDAlaM7mQs/Qssm51+yHw4WSdDeYQ94n5wH5mUKoX8SqzLl3gAy6wHj9bi3jD1Txoscks0HSpHR9Lrxoy06TMLs8h3CygSdZr7kTkf5PXtKE3Gqbg54cyp+Wa2FGO0ijQ0paLEI2rPWRwxVUOkrs4r7i9YH0sJcEOUaoEiWMiNdeV5Zo9ciGddgCDz1EXdWoO6JPleD5r6W1dFfcsPnsaLl56fU/J/FDvwSj7et7AyKPwQvNQFQwtP6/tHoMksDUmBSadUWM0wA+Dbn0Ve7V6xdCXbqUn+Cs22EFPxqpnX7kl5xeq7XVWW+Mbw== nidhanda@microsoft.com","path":"/home/nidhanda/.ssh/authorized_keys"}],"publisher":"Canonical","resourceGroupName":"nidhanda_test","resourceId":"/subscriptions/13723929-6644-4060-a50a-cc38ebc5e8b1/resourceGroups/nidhanda_test/providers/Microsoft.Compute/virtualMachines/ub16","sku":"16.04-LTS","subscriptionId":"13723929-6644-4060-a50a-cc38ebc5e8b1","tags":"","version":"16.04.202004070","vmId":"00d58ed6-f5ae-462f-afd3-5c34a2f9a183","vmScaleSetName":"","vmSize":"Basic_A1","zone":""},"network":{"interface":[{"ipv4":{"ipAddress":[{"privateIpAddress":"172.16.43.6","publicIpAddress":"52.179.248.28"}],"subnet":[{"address":"172.16.43.0","prefix":"24"}]},"ipv6":{"ipAddress":[]},"macAddress":"000D3AE39155"}]}}''')
    az_resource_id = data["compute"]["resourceId"]
    subscription_id = data["compute"]["subscriptionId"]

    #create metrics conf
    me_conf = create_metrics_extension_conf(az_resource_id, "URL")  

    #create custom metrics conf
    custom_conf = create_custom_metrics_conf()

    #write configs to disk
    logFolder, configFolder = get_handler_vars()
    me_config_dir = configFolder + "/metrics_configs/"
    if not os.path.exists(me_config_dir):
        os.mkdir(me_config_dir)
    
    
    me_conf_path = me_config_dir + "MetricsExtensionV1_Configuration.json"
    with open(me_conf_path, "w") as f:
        f.write(me_conf)


    custom_conf_path = me_config_dir + "CUSTOMMETRIC_"+ subscription_id +"_MonitoringAccount_Configuration.json"
    with open(custom_conf_path, "w") as f:
        f.write(custom_conf)

    #setup metrics extension service
    setup_me_service(configFolder)
    
    #start metrics extension
    start_me()
