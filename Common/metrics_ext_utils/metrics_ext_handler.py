import urllib2
import json
import os
from shutil import copyfile

def stop_metrics_service():

    # If the VM has systemd, then we will use that to stop
    check_systemd = os.system("pidof systemd 1>/dev/null 2>&1")
    if check_systemd == 0:
        code = 1
        metrics_service_path = "/lib/systemd/system/metrics-extension.service"

        if os.path.isfile(metrics_service_path):
            code = os.system("sudo systemctl stop metrics-extension")
        else:
            return False, "Metrics Extension service file does not exist. Failed to stop ME service: metrics-extension.service ."

        if code != 0:
            return False, "Unable to stop Metrics Extension service: metrics-extension.service ."
    else:
        #This VM does not have systemd, So we will use the pid from the last ran metrics process and terminate it
        _, configFolder = get_handler_vars()
        metrics_conf_dir = configFolder + "/metrics_configs/"
        metrics_pid_path = me_config_dir + "metrics_pid.txt"

        if os.path.isfile(metrics_pid_path):
            pid = ""
            with open(metrics_pid_path, "r") as f:
                pid = f.read()
            if pid != "":
                os.kill(pid, signal.SIGKILL)
            else:
                return False, "No pid found for a currently running Metrics Extension process in {0}. Failed to stop Metrics Extension.".format(metrics_pid_path)
        else:
            return False, "File containing the pid for the running Metrics Extension process at {0} does not exit. Failed to stop Metrics Extension".format(metrics_pid_path)

    return True, "Successfully stopped metrics-extension service"

def remove_metrics_service():

    _, configFolder = get_handler_vars()
    metrics_service_path = "/lib/systemd/system/metrics-extension.service"

    code = 1
    if os.path.isfile(metrics_service_path):
        code = os.remove(metrics_service_path)
    else:
        #Service file doesnt exist or is already removed, exit the method with exit code 0
        return True, "Metrics Extension service file doesnt exist or is already removed"

    if code != 0:
        return False, "Unable to remove metrics-extension service: metrics-extension.service."

    return True, "Successfully removed metrics-extensions service"


def setup_me_service(configFolder, monitoringAccount):

    me_service_path = "/lib/systemd/system/metrics-extension.service"
    metrics_ext_bin = "/usr/local/lad/bin/MetricsExtension"
    me_service_template_path = os.getcwd() + "/services/metrics-extension.service"
    daemon_reload_status = 1

    if not os.path.exists(configFolder):
        raise Exception("Metrics extension config directory does not exist. Failed to setup ME service.")
        return False

    if os.path.isfile(me_service_template_path):
        copyfile(me_service_template_path, me_service_path)

        if os.path.isfile(me_service_path):
            os.system(r"sed -i 's+%ME_BIN%+{1}+' {0}".format(me_service_path, metrics_ext_bin))
            os.system(r"sed -i 's+%ME_DATA_DIRECTORY%+{1}+' {0}".format(me_service_path, configFolder))
            os.system(r"sed -i 's+%ME_MONITORING_ACCOUNT%+{1}+' {0}".format(me_service_path, monitoringAccount))
            daemon_reload_status = os.system("sudo systemctl daemon-reload")
            if daemon_reload_status != 0:
                raise Exception("Unable to reload systemd after ME service file change. Failed to setup ME service.")
                return False
        else:
            raise Exception("Unable to copy Metrics extension service file to {0}. Failed to setup ME service.".format(me_service_path))
            return False
    else:
        raise Exception("Metrics extension service file does not exist at {0}. Failed to setup ME service.".format(me_service_template_path))
        return False
    return True



def start_metrics():
    #Re using the code to grab the config directories and imds values because start will be called from Enable process outside this script

    metrics_ext_bin = "/usr/local/lad/bin/MetricsExtension"
    if not os.path.isfile(metrics_ext_bin):
        raise Exception("Metrics Extension binary does not exist. Failed to start ME service.")
        return False


    # If the VM has systemd, then we use that to start/stop
    check_systemd = os.system("pidof systemd 1>/dev/null 2>&1")
    if check_systemd == 0:
        service_restart_status = os.system("sudo systemctl restart metrics-extension")
        if service_restart_status != 0:
            raise Exception("Unable to start metrics-extension.service. Failed to start ME service.")
            return False

    #Else start ME as a process and save the pid to a file so that we can terminate it while disabling/uninstalling
    else:
        _, configFolder = get_handler_vars()
        me_config_dir = configFolder + "/metrics_configs/"
        #query imds to get the subscription id
        az_resource_id, subscription_id, location, data = get_imds_values()
        monitoringAccount = "CUSTOMMETRIC_"+ subscription_id
        metrics_pid_path = me_config_dir + "metrics_pid.txt"

        binary_exec_command = "{0} -TokenSource HOBO -Input influxdb_udp -InfluxDbUdpPort 8139 -DataDirectory {1} -LocalControlChannel -MonitoringAccount {2}".format(metrics_ext_bin, me_config_dir, monitoringAccount)
        proc = subprocess.Popen(binary_exec_command.split(" "), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(3) #sleeping for 3 seconds before checking if the process is still running, to give it ample time to relay crash info
        p = proc.poll()

        if p is None: #Process is running successfully
            metrics_pid = proc.pid

            #write this pid to a file for future use
            with open(metrics_pid_path, "w+") as f:
                f.write(metrics_pid)
        else:
            out, err = proc.communicate()
            raise Exception("Unable to run MetricsExtension binary as a process due to error - {0}. Failed to start MetricsExtension.".format(err))
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


def get_imds_values():

    # imdsurl = "http://169.254.169.254/metadata/instance?api-version=2019-03-11"
    # #query imds to get the required information
    # req = urllib2.Request(imdsurl, headers={'Metadata':'true'})
    # res = urllib2.urlopen(req)
    # data = json.loads(res.read())
    data = {"compute":{"azEnvironment":"AzurePublicCloud","customData":"","location":"eastus","name":"ubtest-16","offer":"UbuntuServer","osType":"Linux","placementGroupId":"","plan":{"name":"","product":"","publisher":""},"platformFaultDomain":"0","platformUpdateDomain":"0","provider":"Microsoft.Compute","publicKeys":[{"keyData":"ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQDJmcpHCPcSg+J0S7pbqj5X08iaIMulAc7qq1iLPrcSu04alVWQTFE58f3LbabDwDBhiXIgWO4W4/26l0+arTLOj6TJe9EiaabAYniUglC0ChbgMTjAvXQCbtwLc2yo30Uh4DbdFhEo9UXG/AeYdwvt7TCVYFrd/seGQ+7dENcFdyd4rRs1hZdMxKil+Tx0dBoFE+IEydY6PSm48qgq7XlteLAT6q/Gqpo4wVqboyTcal+QIZftDfSlJ2G+Asem/mjWj9U1nhJeBcRy2JWOSJeKgojCI3WZUMVly6lkxbX6c1UYHkT53w/tFxMehm9TUUiviOTZOAXIE6Yj/7KWlGmosJPTCA6VSRr3b5RS3lgRerOIwwb/FDAlaM7mQs/Qssm51+yHw4WSdDeYQ94n5wH5mUKoX8SqzLl3gAy6wHj9bi3jD1Txoscks0HSpHR9Lrxoy06TMLs8h3CygSdZr7kTkf5PXtKE3Gqbg54cyp+Wa2FGO0ijQ0paLEI2rPWRwxVUOkrs4r7i9YH0sJcEOUaoEiWMiNdeV5Zo9ciGddgCDz1EXdWoO6JPleD5r6W1dFfcsPnsaLl56fU/J/FDvwSj7et7AyKPwQvNQFQwtP6/tHoMksDUmBSadUWM0wA+Dbn0Ve7V6xdCXbqUn+Cs22EFPxqpnX7kl5xeq7XVWW+Mbw== nidhanda@microsoft.com","path":"/home/nidhanda/.ssh/authorized_keys"}],"publisher":"Canonical","resourceGroupName":"nidhanda_test","resourceId":"/subscriptions/13723929-6644-4060-a50a-cc38ebc5e8b1/resourceGroups/nidhanda_test/providers/Microsoft.Compute/virtualMachines/ubtest-16","sku":"16.04-LTS","subscriptionId":"13723929-6644-4060-a50a-cc38ebc5e8b1","tags":"","version":"16.04.202004290","vmId":"4bb331fc-2320-49d5-bb5e-bcdff8ab9e74","vmScaleSetName":"","vmSize":"Basic_A1","zone":""},"network":{"interface":[{"ipv4":{"ipAddress":[{"privateIpAddress":"172.16.16.6","publicIpAddress":"13.68.157.2"}],"subnet":[{"address":"172.16.16.0","prefix":"24"}]},"ipv6":{"ipAddress":[]},"macAddress":"000D3A4DDE5F"}]}}

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

    return az_resource_id, subscription_id, location, data


def setup_me(is_lad):


    #query imds to get the required information
    az_resource_id, subscription_id, location, data = get_imds_values()

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
    # If the VM has systemd, then we use that to start/stop
    check_systemd = os.system("pidof systemd 1>/dev/null 2>&1")
    if check_systemd == 0:
        setup_me_service(me_config_dir, me_monitoring_account)
