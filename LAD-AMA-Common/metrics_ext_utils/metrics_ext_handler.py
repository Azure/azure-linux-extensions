#!/usr/bin/env python
#
# Azure Linux extension
#
# Copyright (c) Microsoft Corporation
# All rights reserved.
# MIT License
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the ""Software""), to deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit
# persons to whom the Software is furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the
# Software.
# THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
# WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
# OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import urllib2
import json
import os
from shutil import copyfile, rmtree
import stat
import filecmp
import metrics_ext_utils.metrics_constants as metrics_constants
import subprocess
import time
import signal
import metrics_ext_utils.metrics_common_utils as metrics_utils


def is_running(is_lad):
    """
    This method is used to check if metrics binary is currently running on the system or not.
    In order to check whether it needs to be restarted from the watcher daemon
    """
    if is_lad:
        metrics_bin = metrics_constants.lad_metrics_extension_bin
    else:
        metrics_bin = metrics_constants.ama_metrics_extension_bin

    proc = subprocess.Popen(["ps  aux | grep MetricsExtension | grep -v grep"], stdout=subprocess.PIPE, shell=True)
    output = proc.communicate()[0]
    if metrics_bin in output:
        return True
    else:
        return False


def stop_metrics_service(is_lad):
    """
    Stop the metrics service if VM is using is systemd, otherwise check if the pid_file exists,
    and if the pid belongs to the MetricsExtension process, if yes, then kill the process
    This method is called before remove_metrics_service by the main extension code
    :param is_lad: boolean whether the extension is LAD or not (AMA)
    """

    if is_lad:
        metrics_ext_bin = metrics_constants.lad_metrics_extension_bin
    else:
        metrics_ext_bin = metrics_constants.ama_metrics_extension_bin

    # If the VM has systemd, then we will use that to stop
    if metrics_utils.is_systemd():
        code = 1
        metrics_service_path = get_metrics_extension_service_path()

        if os.path.isfile(metrics_service_path):
            code = os.system("sudo systemctl stop metrics-extension")
        else:
            return False, "Metrics Extension service file does not exist. Failed to stop ME service: metrics-extension.service ."

        if code != 0:
            return False, "Unable to stop Metrics Extension service: metrics-extension.service. Failed with code {0}".format(code)
    else:
        #This VM does not have systemd, So we will use the pid from the last ran metrics process and terminate it
        _, configFolder = get_handler_vars()
        metrics_conf_dir = configFolder + "/metrics_configs/"
        metrics_pid_path = metrics_conf_dir + "metrics_pid.txt"

        if os.path.isfile(metrics_pid_path):
            pid = ""
            with open(metrics_pid_path, "r") as f:
                pid = f.read()
            if pid != "":
                # Check if the process running is indeed MetricsExtension, ignore if the process output doesn't contain MetricsExtension
                proc = subprocess.Popen(["ps -o cmd= {0}".format(pid)], stdout=subprocess.PIPE, shell=True)
                output = proc.communicate()[0]
                if metrics_ext_bin in output:
                    os.kill(int(pid), signal.SIGKILL)
                else:
                    return False, "Found a different process running with PID {0}. Failed to stop MetricsExtension.".format(pid)
            else:
                return False, "No pid found for a currently running Metrics Extension process in {0}. Failed to stop Metrics Extension.".format(metrics_pid_path)
        else:
            return False, "File containing the pid for the running Metrics Extension process at {0} does not exit. Failed to stop Metrics Extension".format(metrics_pid_path)

    return True, "Successfully stopped metrics-extension service"

def remove_metrics_service(is_lad):
    """
    Remove the metrics service if the VM is using systemd as well as the MetricsExtension Binary
    This method is called after stop_metrics_service by the main extension code during Extension uninstall
    :param is_lad: boolean whether the extension is LAD or not (AMA)
    """

    metrics_service_path = get_metrics_extension_service_path()

    if os.path.isfile(metrics_service_path):
        code = os.remove(metrics_service_path)

    if is_lad:
        metrics_ext_bin = metrics_constants.lad_metrics_extension_bin
    else:
        metrics_ext_bin = metrics_constants.ama_metrics_extension_bin

    # Checking To see if the files were successfully removed, since os.remove doesn't return an error code
    if os.path.isfile(metrics_ext_bin):
        remove_code = os.remove(metrics_ext_bin)

    return True, "Successfully removed metrics-extensions service and MetricsExtension binary."

def generate_Arc_MSI_token():
    """
    This method is used to query the Hyrbid metdadata service of Arc to get the MSI Auth token for the VM and write it to the ME config location
    This is called from the main extension code after config setup is complete
    """
    _, configFolder = get_handler_vars()
    me_config_dir = configFolder + "/metrics_configs/"
    me_auth_file_path = me_config_dir + "AuthToken-MSI.json"
    expiry_epoch_time = ""
    log_messages = ""
    retries = 1
    max_retries = 3
    sleep_time = 5

    if not os.path.exists(me_config_dir):
        log_messages += "Metrics extension config directory - {0} does not exist. Failed to generate MSI auth token fo ME.\n".format(me_config_dir)
        return False, expiry_epoch_time, log_messages
    try:
        data = None
        while retries <= max_retries:
            arc_endpoint = metrics_utils.get_arc_endpoint()
            try:
                msiauthurl = arc_endpoint + "/metadata/identity/oauth2/token?api-version=2019-11-01&resource=https://management.azure.com/"
                req = urllib2.Request(msiauthurl, headers={'Metadata':'true'})
                res = urllib2.urlopen(req)
            except:
                # The above request is expected to fail and add a key to the path - 
                authkey_dir = "/var/opt/azcmagent/tokens/"
                if not os.path.exists(authkey_dir):
                    log_messages += "Unable to find the auth key file at {0} returned from the arc msi auth request.".format(authkey_dir)
                    return False, expiry_epoch_time, log_messages
                keys_dir = []
                for filename in os.listdir(authkey_dir):
                    keys_dir.append(filename)

                authkey_path = authkey_dir + keys_dir[-1]
                auth = "basic "
                with open(authkey_path, "r") as f:
                    key = f.read()
                auth += key
                req = urllib2.Request(msiauthurl, headers={'Metadata':'true', 'authorization':auth})
                res = urllib2.urlopen(req)
                data = json.loads(res.read())

            if not data or "access_token" not in data:
                retries += 1
            else:
                break

            log_messages += "Failed to fetch MSI Auth url. Retrying in {2} seconds. Retry Count - {0} out of Mmax Retries - {1}\n".format(retries, max_retries, sleep_time)
            time.sleep(sleep_time)


        if retries > max_retries:
            log_messages += "Unable to generate a valid MSI auth token at {0}.\n".format(me_auth_file_path)
            return False, expiry_epoch_time, log_messages

        with open(me_auth_file_path, "w") as f:
            f.write(json.dumps(data))

        if "expires_on" in data:
            expiry_epoch_time  = data["expires_on"]
        else:
            log_messages += "Error parsing the msi token at {0} for the token expiry time. Failed to generate the correct token\n".format(me_auth_file_path)
            return False, expiry_epoch_time, log_messages

    except Exception as e:
        log_messages += "Failed to get msi auth token. Please check if VM's system assigned Identity is enabled Failed with error {0}\n".format(e)
        return False, expiry_epoch_time, log_messages

    return True, expiry_epoch_time, log_messages


def generate_MSI_token():
    """
    This method is used to query the metdadata service to get the MSI Auth token for the VM and write it to the ME config location
    This is called from the main extension code after config setup is complete
    """

    if metrics_utils.is_arc_installed():
        return generate_Arc_MSI_token()
    else:
        _, configFolder = get_handler_vars()
        me_config_dir = configFolder + "/metrics_configs/"
        me_auth_file_path = me_config_dir + "AuthToken-MSI.json"
        expiry_epoch_time = ""
        log_messages = ""
        retries = 1
        max_retries = 3
        sleep_time = 5

        if not os.path.exists(me_config_dir):
            log_messages += "Metrics extension config directory - {0} does not exist. Failed to generate MSI auth token fo ME.\n".format(me_config_dir)
            return False, expiry_epoch_time, log_messages
        try:
            data = None
            while retries <= max_retries:
                msiauthurl = "http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01&resource=https://ingestion.monitor.azure.com/"
                req = urllib2.Request(msiauthurl, headers={'Metadata':'true', 'Content-Type':'application/json'})
                res = urllib2.urlopen(req)
                data = json.loads(res.read())

                if not data or "access_token" not in data:
                    retries += 1
                else:
                    break

                log_messages += "Failed to fetch MSI Auth url. Retrying in {2} seconds. Retry Count - {0} out of Mmax Retries - {1}\n".format(retries, max_retries, sleep_time)
                time.sleep(sleep_time)


            if retries > max_retries:
                log_messages += "Unable to generate a valid MSI auth token at {0}.\n".format(me_auth_file_path)
                return False, expiry_epoch_time, log_messages

            with open(me_auth_file_path, "w") as f:
                f.write(json.dumps(data))

            if "expires_on" in data:
                expiry_epoch_time  = data["expires_on"]
            else:
                log_messages += "Error parsing the msi token at {0} for the token expiry time. Failed to generate the correct token\n".format(me_auth_file_path)
                return False, expiry_epoch_time, log_messages

        except Exception as e:
            log_messages += "Failed to get msi auth token. Please check if VM's system assigned Identity is enabled Failed with error {0}\n".format(e)
            return False, expiry_epoch_time, log_messages

        return True, expiry_epoch_time, log_messages


def setup_me_service(configFolder, monitoringAccount, metrics_ext_bin, me_influx_port):
    """
    Setup the metrics service if VM is using systemd
    :param configFolder: Path for the config folder for metrics extension
    :param monitoringAccount: Monitoring Account name that ME will upload data to
    :param metrics_ext_bin: Path for the binary for metrics extension
    :param me_influx_port: Influxdb port that metrics extension will listen on
    """

    me_service_path = get_metrics_extension_service_path()
    me_service_template_path = os.getcwd() + "/services/metrics-extension.service"
    daemon_reload_status = 1

    if not os.path.exists(configFolder):
        raise Exception("Metrics extension config directory does not exist. Failed to setup ME service.")
        return False

    if os.path.isfile(me_service_template_path):
        copyfile(me_service_template_path, me_service_path)

        if os.path.isfile(me_service_path):
            os.system(r"sed -i 's+%ME_BIN%+{1}+' {0}".format(me_service_path, metrics_ext_bin))
            os.system(r"sed -i 's+%ME_INFLUX_PORT%+{1}+' {0}".format(me_service_path, me_influx_port))
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
        raise Exception("Metrics extension service template file does not exist at {0}. Failed to setup ME service.".format(me_service_template_path))
        return False
    return True



def start_metrics(is_lad):
    """
    Start the metrics service if VM is using is systemd, otherwise start the binary as a process and store the pid,
    to a file in the MetricsExtension config directory,
    This method is called after config setup is completed by the main extension code
    :param is_lad: boolean whether the extension is LAD or not (AMA)
    """

    # Re using the code to grab the config directories and imds values because start will be called from Enable process outside this script
    log_messages = ""

    if is_lad:
        metrics_ext_bin = metrics_constants.lad_metrics_extension_bin
    else:
        metrics_ext_bin = metrics_constants.ama_metrics_extension_bin
    if not os.path.isfile(metrics_ext_bin):
        log_messages += "Metrics Extension binary does not exist. Failed to start ME service."
        return False, log_messages

    if is_lad:
        me_influx_port = metrics_constants.lad_metrics_extension_udp_port
    else:
        me_influx_port = metrics_constants.ama_metrics_extension_udp_port


    # If the VM has systemd, then we use that to start/stop
    if metrics_utils.is_systemd():
        service_restart_status = os.system("sudo systemctl restart metrics-extension")
        if service_restart_status != 0:
            log_messages += "Unable to start metrics-extension.service. Failed to start ME service."
            return False, log_messages

    #Else start ME as a process and save the pid to a file so that we can terminate it while disabling/uninstalling
    else:
        _, configFolder = get_handler_vars()
        me_config_dir = configFolder + "/metrics_configs/"
        #query imds to get the subscription id
        az_resource_id, subscription_id, location, data = get_imds_values(is_lad)

        if is_lad:
            monitoringAccount = "CUSTOMMETRIC_"+ subscription_id
        else:
            monitoringAccount = "CUSTOMMETRIC_"+ subscription_id + "_" + location

        metrics_pid_path = me_config_dir + "metrics_pid.txt"

        binary_exec_command = "{0} -TokenSource MSI -Input influxdb_udp -InfluxDbUdpPort {1} -DataDirectory {2} -LocalControlChannel -MonitoringAccount {3} -LogLevel Error".format(metrics_ext_bin, me_influx_port, me_config_dir, monitoringAccount)
        proc = subprocess.Popen(binary_exec_command.split(" "), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(3) #sleeping for 3 seconds before checking if the process is still running, to give it ample time to relay crash info
        p = proc.poll()

        if p is None: #Process is running successfully
            metrics_pid = proc.pid

            #write this pid to a file for future use
            with open(metrics_pid_path, "w+") as f:
                f.write(str(metrics_pid))
        else:
            out, err = proc.communicate()
            log_messages += "Unable to run MetricsExtension binary as a process due to error - {0}. Failed to start MetricsExtension.".format(err)
            return False, log_messages
    return True, log_messages


def create_metrics_extension_conf(az_resource_id, aad_url):
    """
    Create the metrics extension config
    :param az_resource_id: Azure Resource ID for the VM
    :param aad_url: AAD auth url for the VM
    """
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
} '''
    return conf_json

def create_custom_metrics_conf(mds_gig_endpoint_region):
    """
    Create the metrics extension config
    :param mds_gig_endpoint_region: mds gig endpoint region for the VM
    """
    # Note : mds gig endpoint url is only for 3rd party customers. 1st party endpoint is different

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
    """
    This method is taken from the Waagent code. This is used to grab the log and config file location from the json public setting for the Extension
    """

    logFolder = ""
    configFolder = ""
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


def get_imds_values(is_lad):
    """
    Query imds to get required values for MetricsExtension config for this VM
    """
    retries = 1
    max_retries = 3
    sleep_time = 5
    imdsurl = ""
    is_arc = False

    if is_lad:
        imdsurl = "http://169.254.169.254/metadata/instance?api-version=2019-03-11"
    else:
        if metrics_utils.is_arc_installed():
            imdsurl = metrics_utils.get_arc_endpoint()
            imdsurl += "/metadata/instance?api-version=2019-11-01"
            is_arc = True
        else:
            imdsurl = "http://169.254.169.254/metadata/instance?api-version=2019-03-11"


    data = None
    while retries <= max_retries:

        #query imds to get the required information
        req = urllib2.Request(imdsurl, headers={'Metadata':'true'})
        res = urllib2.urlopen(req)
        data = json.loads(res.read())

        if "compute" not in data:
            retries += 1
        else:
            break

        time.sleep(sleep_time)

    if retries > max_retries:
        raise Exception("Unable to find 'compute' key in imds query response. Reached max retry limit of - {0} times. Failed to setup ME.".format(max_retries))
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


def get_metrics_extension_service_path():
    """
    Utility method to get the service path in case /lib/systemd/system doesnt exist on the OS
    """
    if os.path.exists("/lib/systemd/system/"):
        return metrics_constants.metrics_extension_service_path
    elif os.path.exists("/usr/lib/systemd/system/"):
        return metrics_constants.metrics_extension_service_path_usr_lib
    else:
        raise Exception("Systemd unit files do not exist at /lib/systemd/system or /usr/lib/systemd/system/. Failed to setup Metrics Extension service.")




def setup_me(is_lad):
    """
    The main method for creating and writing MetricsExtension configuration as well as service setup
    :param is_lad: Boolean value for whether the extension is Lad or not (AMA)
    """

    # query imds to get the required information
    az_resource_id, subscription_id, location, data = get_imds_values(is_lad)

    # get tenantID
    # The url request will fail due to missing authentication header, but we get the auth url from the header of the request fail exception
    # The armurl is only for Public Cloud. Needs verification in Sovereign clouds
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

    # Clear older config directory if exists. 
    if os.path.exists(me_config_dir):
        rmtree(me_config_dir)    
    os.mkdir(me_config_dir)


    me_conf_path = me_config_dir + "MetricsExtensionV1_Configuration.json"
    with open(me_conf_path, "w") as f:
        f.write(me_conf)

    if is_lad:
        me_monitoring_account = "CUSTOMMETRIC_"+ subscription_id
    else:
        me_monitoring_account = "CUSTOMMETRIC_"+ subscription_id + "_" +location

    custom_conf_path = me_config_dir + me_monitoring_account +"_MonitoringAccount_Configuration.json"
    with open(custom_conf_path, "w") as f:
        f.write(custom_conf)

    # Copy MetricsExtension Binary to the bin location
    me_bin_local_path = os.getcwd() + "/MetricsExtensionBin/MetricsExtension"
    if is_lad:
        metrics_ext_bin = metrics_constants.lad_metrics_extension_bin
    else:
        metrics_ext_bin = metrics_constants.ama_metrics_extension_bin

    if is_lad:
        lad_bin_path = "/usr/local/lad/bin/"
        # Checking if directory exists before copying ME bin over to /usr/local/lad/bin/
        if not os.path.exists(lad_bin_path):
            os.makedirs(lad_bin_path)

    # Check if previous file exist at the location, compare the two binaries,
    # If the files are not same, remove the older file, and copy the new one
    # If they are the same, then we ignore it and don't copy
    if os.path.isfile(me_bin_local_path):
        if os.path.isfile(metrics_ext_bin):
            if not filecmp.cmp(me_bin_local_path, metrics_ext_bin):
                # Removing the file in case it is already being run in a process,
                # in which case we can get an error "text file busy" while copying
                os.remove(metrics_ext_bin)
                copyfile(me_bin_local_path, metrics_ext_bin)
                os.chmod(metrics_ext_bin, stat.S_IXGRP | stat.S_IRGRP | stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR | stat.S_IXOTH | stat.S_IROTH)

        else:
            # No previous binary exist, simply copy it and make it executable
            copyfile(me_bin_local_path, metrics_ext_bin)
            os.chmod(metrics_ext_bin, stat.S_IXGRP | stat.S_IRGRP | stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR | stat.S_IXOTH | stat.S_IROTH)
    else:
        raise Exception("Unable to copy MetricsExtension Binary, could not find file at the location {0} . Failed to setup ME.".format(me_bin_local_path))
        return False

    if is_lad:
        me_influx_port = metrics_constants.lad_metrics_extension_udp_port
    else:
        me_influx_port = metrics_constants.ama_metrics_extension_udp_port

    # setup metrics extension service
    # If the VM has systemd, then we use that to start/stop
    if metrics_utils.is_systemd():
        setup_me_service(me_config_dir, me_monitoring_account, metrics_ext_bin, me_influx_port)

    return True
