import urllib2
import json
import os

def stop_metrics_service():
    metrics_service_path = "/lib/systemd/system/metrics-extension.service"
     
    code = 1
    if os.path.isfile(metrics_service_path):
        code = os.system("sudo systemctl stop metrics-extension")
    else:
        raise Exception("Metrics Extension service file does not exist. Failed to stop ME service: metrics-extension.service .")
        return code
    
    if code != 0:
        raise Exception("Unable to stop Metrics Extension service: metrics-extension.service .")

    return code

def remove_metrics_service():

    _, configFolder = get_handler_vars()
    metrics_service_path = "/lib/systemd/system/metrics-extension.service"
     
    code = 1
    if os.path.isfile(metrics_service_path):
        code = os.remove(metrics_service_path)
    else:
        #Service file doesnt exist or is already removed, exit the method with exit code 0
        return 0
    
    if code != 0:
        raise Exception("Unable to remove metrics service: metrics-extension.service .")

    return code


def setup_me_service(configFolder, monitoringAccount):

    me_service_path = "/lib/systemd/system/metrics-extension.service"
    metrics_ext_bin = "/usr/local/lad/bin/MetricsExtension"
    daemon_reload_status = 1
    service_restart_status = 1

    if not os.path.exists(configFolder):
        raise Exception("Metrics extension config directory does not exist. Failed to setup ME service.")
        return False
   
    if not os.path.isfile(metrics_ext_bin):
        raise Exception("Metrics Extension binary does not exist. Failed to setup ME service.")
        return False       

    if os.path.isfile(me_service_path):
        os.system(r"sed -i 's+%ME_BIN%+{1}+' {0}".format(me_service_path, metrics_ext_bin)) 
        os.system(r"sed -i 's+%ME_DATA_DIRECTORY%+{1}+' {0}".format(me_service_path, configFolder))
        os.system(r"sed -i 's+%ME_MONITORING_ACCOUNT%+{1}+' {0}".format(me_service_path, monitoringAccount))
        daemon_reload_status = os.system("sudo systemctl daemon-reload")
        if daemon_reload_status != 0:
            raise Exception("Unable to reload systemd after ME service file change. Failed to setup ME service.")
            return False
        service_restart_status = os.system("sudo systemctl start metrics-extension")
        if service_restart_status != 0:
            raise Exception("Unable to start Metrics Extension service. Failed to setup ME service.")
            return False
    else:
        raise Exception("Metrics extension service file does not exist. Failed to setup ME service.")
        return False
    return True

def create_metrics_extension_conf(az_resource_id, aad_url):
    conf_json = '''{ 
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
  "enableMetricMetadataPublication": true, 
  "enableDimensionTrimming": true, 
  "shutdownRequestedThreshold": 5, 
  "internalMetricProductionLevel": 0, 
  "maxPublicationWithoutResponseTimeoutInSec": 300, 
  "maxConfigQueryWithoutResponseTimeoutInSec": 300, 
  "maxThumbprintsPerAccountToLoad": 100, 
  "maxPacketsToCaptureLocally": 0, 
  "maxNumberOfRawEventsPerCycle": 1000000, 
  "publicationSimulated": false, 
  "maxAggregationTimeoutPerCycleInSec": 20, 
  "maxRawEventInputQueueSize": 2000000, 
  "publicationIntervalInSec": 60, 
  "interningSwapPeriodInMin": 240, 
  "interningClearPeriodInMin": 5, 
  "enableParallelization": true, 
  "enableDimensionSortingOnIngestion": true, 
  "rawEtwEventProcessingParallelizationFactor": 1, 
  "maxRandomConfigurationLoadingDelayInSec": 120, 
  "aggregationProcessingParallelizationFactor": 1, 
  "aggregationProcessingPerPartitionPeriodInSec": 20, 
  "aggregationProcessingParallelizationVolumeThreshold": 500000, 
  "useSharedHttpClients": true, 
  "loadFromConfigurationCache": true, 
  "restartByDateTimeUtc": "0001-01-01T00:00:00", 
  "restartStableIdTarget": "", 
  "enableIpV6": false, 
  "disableCustomMetricAgeSupport": false, 
  "globalPublicationCertificateThumbprint": "", 
  "maxHllSerializationVersion": 2, 
  "enableNodeOwnerMode": false, 
  "performAdditionalAzureHostIpV6Checks": false, 
  "compressMetricData": false, 
  "publishMinMaxByDefault": true, 
  "azureResourceId": "'''+ az_resource_id +'''", 
  "aadAuthority": "'''+ aad_url +'''", 
  "aadTokenEnvVariable": "MSIAuthToken"
} '''   #can ME handle the MSITOKEN?
    return conf_json

def create_custom_metrics_conf(mds_gig_endpoint_region):
    conf_json = '''{ 
        "version": 17, 
        "maxMetricAgeInSeconds": 0, 
        "endpointsForClientForking": [], 
        "homeStampGslbHostname": "''' + mds_gig_endpoint_region + '''.monitoring.azure.com", 
        "endpointsForClientPublication": [ 
            "https://''' + mds_gig_endpoint_region + '''.monitoring.azure.com/api/v1/ingestion/ingest" 
        ] 
    } ''' 
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


def setup_me(is_lad):

    imdsurl = "http://169.254.169.254/metadata/instance?api-version=2019-03-11"
    #query imds to get the required information 
    req = urllib2.Request(imdsurl, headers={'Metadata':'true'})
    res = urllib2.urlopen(req)
    data = json.loads(res.read())
    if "compute" not in data:
        raise Exception("Unable to find 'compute' key in imds query response. Failed to setup ME.")
        return False

    if "resourceId" not in data["compute"]:
        raise Exception("Unable to find 'resourceId' key in imds query response. Failed to setup ME.")
        return False   

    az_resource_id = data["compute"]["resourceId"]
    
    if "subscriptionId" not in data["compute"]:
        raise Exception("Unable to find 'subscriptionId' key in imds query response. Failed to setup ME.")
        return False

    subscription_id = data["compute"]["subscriptionId"]
    
    if "location" not in data["compute"]:
        raise Exception("Unable to find 'location' key in imds query response. Failed to setup ME.")
        return False

    location= data["compute"]["location"]


    #get tenantID 
    #The url request will fail due to missing authentication header, but we get the auth url from the header of the request fail exception
    aad_auth_url = ""
    amrurl = "https://management.azure.com/subscriptions/" + subscription_id + "?api-version=2014-04-01"
    try:
        req = urllib2.Request(amrurl, headers={'Content-Type':'application/json'})
        res = urllib2.urlopen(req)
    except Exception as e:
        err_res = e.headers["WWW-Authenticate"]
        for line in err_res.split(","):
                if "Bearer authorization_uri" in line:
                        data = line.split("=")
                        aad_auth_url = data[1][1:-1] #Removing the quotes from the front and back
                        break
    
    if aad_auth_url == "":
        raise Exception("Unable to find AAD Authentication URL in the request error response. Failed to setup ME.")
        return False

    #create metrics conf
    me_conf = create_metrics_extension_conf(az_resource_id, aad_auth_url)  

    #create custom metrics conf
    custom_conf = create_custom_metrics_conf(location)

    #write configs to disk
    logFolder, configFolder = get_handler_vars()
    me_config_dir = configFolder + "/metrics_configs/"
    if not os.path.exists(me_config_dir):
        os.mkdir(me_config_dir)
    
    
    me_conf_path = me_config_dir + "MetricsExtensionV1_Configuration.json"
    with open(me_conf_path, "w") as f:
        f.write(me_conf)


    me_monitoring_account = "CUSTOMMETRIC_"+ subscription_id
    custom_conf_path = me_config_dir + "CUSTOMMETRIC_"+ subscription_id +"_MonitoringAccount_Configuration.json"
    with open(custom_conf_path, "w") as f:
        f.write(custom_conf)

    #setup metrics extension service
    setup_me_service(me_config_dir, me_monitoring_account)
    