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

import sys
import json
import os
from telegraf_utils.telegraf_name_map import name_map
import subprocess
import signal
from shutil import copyfile, rmtree
import time
import metrics_ext_utils.metrics_constants as metrics_constants
import metrics_ext_utils.metrics_common_utils as metrics_utils

try:
    # Python 3+
    import urllib.request as urllib
except ImportError:
    # Python 2
    import urllib2 as urllib

"""
Sample input data received by this script
[
    {
        "displayName" : "Network->Packets sent",
        "interval" : "15s",
        "sink" : ["mdsd" , "me"]
    },
    {
        "displayName" : "Network->Packets recieved",
        "interval" : "15s",
        "sink" : ["mdsd" , "me"]
    }
]
"""

def parse_config(data, me_url, mdsd_url, is_lad, az_resource_id, subscription_id, resource_group, region, virtual_machine_name):
    """
    Main parser method to convert Metrics config from extension configuration to telegraf configuration
    :param data: Parsed Metrics Configuration from which telegraf config is created
    :param me_url: The url to which telegraf will send metrics to for MetricsExtension
    :param mdsd_url: The url to which telegraf will send metrics to for MDSD
    :param is_lad: Boolean value for whether the extension is Lad or not (AMA)
    :param az_resource_id: Azure Resource ID value for the VM
    :param subscription_id: Azure Subscription ID value for the VM
    :param resource_group: Azure Resource Group value for the VM
    :param region: Azure Region value for the VM
    :param virtual_machine_name: Azure Virtual Machine Name value (Only in the case for VMSS) for the VM
    """
    storage_namepass_list = []    
    storage_namepass_str = ""

    vmi_rate_counters_list = ["LogicalDisk\\BytesPerSecond", "LogicalDisk\\ReadBytesPerSecond", "LogicalDisk\\ReadsPerSecond",  "LogicalDisk\\WriteBytesPerSecond", "LogicalDisk\\WritesPerSecond", "LogicalDisk\\TransfersPerSecond", "Network\\ReadBytesPerSecond", "Network\\WriteBytesPerSecond"]

    MetricsExtensionNamepsace = metrics_constants.metrics_extension_namespace
    has_mdsd_output = False
    has_me_output = False
    
    if len(data) == 0:
        raise Exception("Empty config data received.")

    if me_url is None or mdsd_url is None:
        raise Exception("No url provided for Influxdb output plugin to ME, AMA.")

    telegraf_json = {}
    counterConfigIdMap = {}

    for item in data:
        sink = item["sink"]
        if "mdsd" in sink:
            has_mdsd_output = True
        if "me" in sink:
            has_me_output = True
        counter = item["displayName"]
        if counter in name_map:
            plugin = name_map[counter]["plugin"]

            is_vmi = plugin.endswith("_vmi")
            telegraf_plugin = plugin
            if is_vmi:
                splitResult = plugin.split('_')
                telegraf_plugin = splitResult[0]            
                
            if counter not in counterConfigIdMap:
                counterConfigIdMap[counter] = []

            configIds = counterConfigIdMap[counter]

            configurationIds = item["configurationId"]

            for configId in configurationIds:
                if configId not in configIds:
                    configIds.append(configId)
            
            omiclass = ""
            if is_lad:
                omiclass = counter.split("->")[0]
            else:
                omiclass = name_map[counter]["module"]

            if omiclass not in telegraf_json:
                telegraf_json[omiclass] = {}
            if plugin not in telegraf_json[omiclass]:
                telegraf_json[omiclass][plugin] = {}
            telegraf_json[omiclass][plugin][name_map[counter]["field"]] = {}

            if is_lad:
                telegraf_json[omiclass][plugin][name_map[counter]["field"]]["displayName"] = counter.split("->")[1]
            else:
                telegraf_json[omiclass][plugin][name_map[counter]["field"]]["displayName"] = counter

            telegraf_json[omiclass][plugin][name_map[counter]["field"]]["interval"] = item["interval"]
            if is_lad:
                telegraf_json[omiclass][plugin][name_map[counter]["field"]]["ladtablekey"] = name_map[counter]["ladtablekey"]
            if "op" in name_map[counter]:
                telegraf_json[omiclass][plugin][name_map[counter]["field"]]["op"] = name_map[counter]["op"]

    """
    Sample converted telegraf conf dict -

    "network": {
        "net": {
            "bytes_total": {"interval": "15s","displayName": "Network total bytes","ladtablekey": "/builtin/network/bytestotal"},
            "drop_total": {"interval": "15s","displayName": "Network collisions","ladtablekey": "/builtin/network/totalcollisions"},
            "err_in": {"interval": "15s","displayName": "Packets received errors","ladtablekey": "/builtin/network/totalrxerrors"},
            "packets_sent": {"interval": "15s","displayName": "Packets sent","ladtablekey": "/builtin/network/packetstransmitted"},
        }
    },
    "filesystem": {
        "disk": {
            "used_percent": {"interval": "15s","displayName": "Filesystem % used space","ladtablekey": "/builtin/filesystem/percentusedspace"},
            "used": {"interval": "15s","displayName": "Filesystem used space","ladtablekey": "/builtin/filesystem/usedspace"},
            "free": {"interval": "15s","displayName": "Filesystem free space","ladtablekey": "/builtin/filesystem/freespace"},
            "inodes_free_percent": {"interval": "15s","displayName": "Filesystem % free inodes","ladtablekey": "/builtin/filesystem/percentfreeinodes"},
        },
        "diskio": {
            "writes_filesystem": {"interval": "15s","displayName": "Filesystem writes/sec","ladtablekey": "/builtin/filesystem/writespersecond","op": "rate"},
            "total_transfers_filesystem": {"interval": "15s","displayName": "Filesystem transfers/sec","ladtablekey": "/builtin/filesystem/transferspersecond","op": "rate"},
            "reads_filesystem": {"interval": "15s","displayName": "Filesystem reads/sec","ladtablekey": "/builtin/filesystem/readspersecond","op": "rate"},
        }
    },
        """

    if len(telegraf_json) == 0:
        raise Exception("Unable to parse telegraf config into intermediate dictionary.")

    excess_diskio_plugin_list_lad = ["total_transfers_filesystem", "read_bytes_filesystem", "total_bytes_filesystem", "write_bytes_filesystem", "reads_filesystem", "writes_filesystem"]
    excess_diskio_field_drop_list_str = ""


    int_file = {"filename":"intermediate.json", "data": json.dumps(telegraf_json)}
    output = []
    output.append(int_file)

    for omiclass in telegraf_json:
        input_str = ""
        ama_rename_str = ""
        metricsext_rename_str = ""
        lad_specific_rename_str = ""
        rate_specific_aggregator_str = ""
        aggregator_str = ""
        for plugin in telegraf_json[omiclass]:
            config_file = {"filename" : omiclass+".conf"}
            # Arbitrary max value for finding min
            min_interval = "999999999s"
            is_vmi = plugin.endswith("_vmi")
            is_vmi_rate_counter = False
            for field in telegraf_json[omiclass][plugin]:
                if not is_vmi_rate_counter:
                    is_vmi_rate_counter = telegraf_json[omiclass][plugin][field]["displayName"] in vmi_rate_counters_list
            
            # if is_vmi_rate_counter:
            #     min_interval = "1s"
                
            if is_vmi or is_vmi_rate_counter:
                splitResult = plugin.split('_')
                telegraf_plugin = splitResult[0]
                input_str += "[[inputs." + telegraf_plugin + "]]\n"
                # plugin = plugin[:-4]
            else:
                input_str += "[[inputs." + plugin + "]]\n"
            # input_str += " "*2 + "name_override = \"" + omiclass + "\"\n"

            # If it's a lad config then add the namepass fields for sending totals to storage
            # always skip lad plugin names as they should be dropped from ME
            lad_plugin_name = plugin + "_total"
            if lad_plugin_name not in storage_namepass_list:
                    storage_namepass_list.append(lad_plugin_name)
                    
            if is_lad:                
                lad_specific_rename_str += "\n[[processors.rename]]\n"
                lad_specific_rename_str += " "*2 + "namepass = [\"" + lad_plugin_name + "\"]\n"                
            elif is_vmi  or is_vmi_rate_counter:                
                if plugin not in storage_namepass_list:
                    storage_namepass_list.append(plugin + "_mdsd")
            else:
                ama_plugin_name = plugin + "_mdsd_la_perf"
                ama_rename_str += "\n[[processors.rename]]\n"
                ama_rename_str += " "*2 + "namepass = [\"" + ama_plugin_name + "\"]\n"
                if ama_plugin_name not in storage_namepass_list:
                    storage_namepass_list.append(ama_plugin_name)

            namespace = MetricsExtensionNamepsace
            if is_vmi or is_vmi_rate_counter:
                namespace = "insights.virtualmachine"

            if is_vmi_rate_counter:
                # Adding "_rated" as a substring for vmi rate metrics to avoid renaming collisions
                plugin_name = plugin + "_rated"
            else:
                plugin_name = plugin

            metricsext_rename_str += "\n[[processors.rename]]\n"
            metricsext_rename_str += " "*2 + "namepass = [\"" + plugin_name + "\"]\n"
            metricsext_rename_str += "\n" + " "*2 + "[[processors.rename.replace]]\n"
            metricsext_rename_str += " "*4 + "measurement = \"" + plugin_name + "\"\n"
            metricsext_rename_str += " "*4 + "dest = \"" + namespace + "\"\n"

            fields = ""
            ops_fields = ""
            non_ops_fields = ""
            non_rate_aggregate = False
            ops = ""
            rate_aggregate = False
            for field in telegraf_json[omiclass][plugin]:
                fields += "\"" + field + "\", "
                if is_vmi or is_vmi_rate_counter :
                    if "MB" in field:
                        fields += "\"" + field.replace('MB','Bytes') + "\", "

                #Use the shortest interval time for the whole plugin
                new_interval = telegraf_json[omiclass][plugin][field]["interval"]
                if int(new_interval[:-1]) < int(min_interval[:-1]):
                    min_interval = new_interval

                #compute values for aggregator options
                if "op" in telegraf_json[omiclass][plugin][field]:
                    if telegraf_json[omiclass][plugin][field]["op"] == "rate":
                        rate_aggregate = True
                        ops = "\"rate\", \"rate_min\", \"rate_max\", \"rate_count\", \"rate_sum\", \"rate_mean\""
                    if is_lad:
                        ops_fields += "\"" +  telegraf_json[omiclass][plugin][field]["ladtablekey"] + "\", "
                    else:
                        ops_fields += "\"" +  telegraf_json[omiclass][plugin][field]["displayName"] + "\", "
                else:
                    non_rate_aggregate = True
                    if is_lad:
                        non_ops_fields += "\"" +  telegraf_json[omiclass][plugin][field]["ladtablekey"] + "\", "
                    else:
                        non_ops_fields += "\"" +  telegraf_json[omiclass][plugin][field]["displayName"] + "\", "

                #Add respective rename processor plugin based on the displayname
                if is_lad:
                    lad_specific_rename_str += "\n" + " "*2 + "[[processors.rename.replace]]\n"
                    lad_specific_rename_str += " "*4 + "field = \"" + field + "\"\n"
                    lad_specific_rename_str += " "*4 + "dest = \"" + telegraf_json[omiclass][plugin][field]["ladtablekey"] + "\"\n"
                elif not is_vmi and not is_vmi_rate_counter:
                    # no rename of fields as they are set in telegraf directly                
                    ama_rename_str += "\n" + " "*2 + "[[processors.rename.replace]]\n"
                    ama_rename_str += " "*4 + "field = \"" + field + "\"\n"
                    ama_rename_str += " "*4 + "dest = \"" + telegraf_json[omiclass][plugin][field]["displayName"] + "\"\n"

                # Avoid adding the rename logic for the redundant *_filesystem fields for diskio which were added specifically for OMI parity in LAD
                # Had to re-use these six fields to avoid renaming issues since both Filesystem and Disk in OMI-LAD use them
                # AMA only uses them once so only need this for LAD
                if is_lad:
                    if field in excess_diskio_plugin_list_lad:
                        excess_diskio_field_drop_list_str += "\"" + field + "\", "
                    else:
                        metricsext_rename_str += "\n" + " "*2 + "[[processors.rename.replace]]\n"
                        metricsext_rename_str += " "*4 + "field = \"" + field + "\"\n"
                        metricsext_rename_str += " "*4 + "dest = \"" + plugin + "/" + field + "\"\n"
                elif not is_vmi and not is_vmi_rate_counter:
                    # no rename of fields as they are set in telegraf directly                
                    metricsext_rename_str += "\n" + " "*2 + "[[processors.rename.replace]]\n"
                    metricsext_rename_str += " "*4 + "field = \"" + field + "\"\n"
                    metricsext_rename_str += " "*4 + "dest = \"" + plugin + "/" + field + "\"\n"

            #Add respective operations for aggregators
            # if is_lad:
            if not is_vmi and not is_vmi_rate_counter:
                suffix = ""
                if is_lad:
                    suffix = "_total\"]\n"
                else:
                    suffix = "_mdsd_la_perf\"]\n"
                    
                if rate_aggregate:
                    aggregator_str += "[[aggregators.basicstats]]\n"
                    aggregator_str += " "*2 + "namepass = [\"" + plugin + suffix
                    aggregator_str += " "*2 + "period = \"" + min_interval + "\"\n"
                    aggregator_str += " "*2 + "drop_original = true\n"
                    aggregator_str += " "*2 + "fieldpass = [" + ops_fields[:-2] + "]\n" #-2 to strip the last comma and space
                    aggregator_str += " "*2 + "stats = [" + ops + "]\n"

                if non_rate_aggregate:
                    aggregator_str += "[[aggregators.basicstats]]\n"
                    aggregator_str += " "*2 + "namepass = [\"" + plugin + suffix
                    aggregator_str += " "*2 + "period = \"" + min_interval + "\"\n"
                    aggregator_str += " "*2 + "drop_original = true\n"
                    aggregator_str += " "*2 + "fieldpass = [" + non_ops_fields[:-2] + "]\n" #-2 to strip the last comma and space
                    aggregator_str += " "*2 + "stats = [\"mean\", \"max\", \"min\", \"sum\", \"count\"]\n\n"
            
            elif is_vmi_rate_counter:
                # Aggregator config for MDSD
                aggregator_str += "[[aggregators.basicstats]]\n"
                aggregator_str += " "*2 + "namepass = [\"" + plugin + "_mdsd\"]\n"
                aggregator_str += " "*2 + "period = \"" + min_interval + "\"\n"
                aggregator_str += " "*2 + "drop_original = true\n"
                aggregator_str += " "*2 + "fieldpass = [" + ops_fields[:-2].replace('\\','\\\\\\\\') + "]\n" #-2 to strip the last comma and space
                aggregator_str += " "*2 + "stats = [" + ops + "]\n\n"

                # Aggregator config for ME
                aggregator_str += "[[aggregators.mdmratemetrics]]\n"
                aggregator_str += " "*2 + "namepass = [\"" + plugin + "\"]\n"
                aggregator_str += " "*2 + "period = \"" + min_interval + "\"\n"
                aggregator_str += " "*2 + "drop_original = true\n"
                aggregator_str += " "*2 + "fieldpass = [" + ops_fields[:-2].replace('\\','\\\\\\\\') + "]\n" #-2 to strip the last comma and space
                aggregator_str += " "*2 + "stats = [\"rate\"]\n\n"

                
            if is_lad:
                lad_specific_rename_str += "\n"
            elif not is_vmi and not is_vmi_rate_counter:
                # no rename of fields as they are set in telegraf directly            
                ama_rename_str += "\n"

            # Using fields[: -2] here to get rid of the last ", " at the end of the string
            input_str += " "*2 + "fieldpass = ["+fields[:-2]+"]\n"
            if plugin == "cpu":
                input_str += " "*2 + "report_active = true\n"
            
            # Rate interval needs to be atleast twice the regular sourcing interval for aggregation to work. 
            # Since we want all the VMI metrics to be sent at the same interval as selected by the customer, To overcome the twice the min internval limitation, 
            # We are sourcing the VMI metrics that need to be aggregated at half the selected frequency 
            rated_min_interval = str(int(min_interval[:-1]) // 2) + "s" 
            input_str += " "*2 + "interval = " + "\"" + rated_min_interval + "\"\n\n"

            telegraf_plugin = plugin
            if is_vmi:
                splitResult = plugin.split('_')
                telegraf_plugin = splitResult[0]

            if not is_lad:
                configIds = counterConfigIdMap[telegraf_json[omiclass][plugin][field]["displayName"]]
                for configId in configIds:
                    input_str += "\n"
                    input_str += " "*2 + "[inputs." + telegraf_plugin + ".tags]\n"
                    input_str += " "*4 + "configurationId=\"" + configId + "\"\n\n"
                    break

            config_file["data"] = input_str + "\n" +  metricsext_rename_str + "\n" + ama_rename_str + "\n" + lad_specific_rename_str + "\n"  +aggregator_str
            output.append(config_file)
            config_file = {}

    """
    Sample telegraf TOML file output

    [[inputs.net]]

    fieldpass = ["err_out", "packets_sent", "err_in", "bytes_sent", "packets_recv"]
    interval = "5s"

    [[inputs.cpu]]

    fieldpass = ["usage_nice", "usage_user", "usage_idle", "usage_active", "usage_irq", "usage_system"]
    interval = "15s"

    [[processors.rename]]

    [[processors.rename.replace]]
        measurement = "net"
        dest = "network"

    [[processors.rename.replace]]
        field = "err_out"
        dest = "Packets sent errors"

    [[aggregators.basicstats]]
    period = "30s"
    drop_original = false
    fieldpass = ["Disk reads", "Disk writes", "Filesystem write bytes/sec"]
    stats = ["rate"]

    """

    ## Get the log folder directory from HandlerEnvironment.json and use that for the telegraf default logging
    logFolder, _ = get_handler_vars()
    for measurement in storage_namepass_list:
        storage_namepass_str += "\"" + measurement + "\", "


    # Telegraf basic agent and output config
    agentconf = "[agent]\n"
    agentconf += "  interval = \"10s\"\n"
    agentconf += "  round_interval = true\n"
    agentconf += "  metric_batch_size = 1000\n"
    agentconf += "  metric_buffer_limit = 1000000\n"
    agentconf += "  collection_jitter = \"0s\"\n"
    agentconf += "  flush_interval = \"10s\"\n"
    agentconf += "  flush_jitter = \"0s\"\n"
    agentconf += "  logtarget = \"file\"\n"
    agentconf += "  quiet = true\n"
    agentconf += "  logfile = \"" + logFolder + "/telegraf.log\"\n"
    agentconf += "  logfile_rotation_max_size = \"100MB\"\n"
    agentconf += "  logfile_rotation_max_archives = 5\n"
    agentconf += "\n# Configuration for adding gloabl tags\n"
    agentconf += "[global_tags]\n"
    if is_lad:
        agentconf += "  DeploymentId= \"${DeploymentId}\"\n"
    agentconf += "  \"microsoft.subscriptionId\"= \"" + subscription_id + "\"\n"
    agentconf += "  \"microsoft.resourceGroupName\"= \"" + resource_group + "\"\n"
    agentconf += "  \"microsoft.regionName\"= \"" + region + "\"\n"
    agentconf += "  \"microsoft.resourceId\"= \"" + az_resource_id + "\"\n"
    if virtual_machine_name != "":
        agentconf += "  \"VMInstanceId\"= \"" + virtual_machine_name + "\"\n"    
    if has_me_output or is_lad:
        agentconf += "\n# Configuration for sending metrics to MetricsExtension\n"

        # for AMA we use Sockets to write to ME but for LAD we continue using UDP
        # because we support a lot more counters in AMA path and ME is not able to handle it with UDP
        if is_lad:
            agentconf += "[[outputs.influxdb]]\n"
        else:
            agentconf += "[[outputs.socket_writer]]\n"
        agentconf += "  namedrop = [" + storage_namepass_str[:-2] + "]\n"
        if is_lad:
            agentconf += "  fielddrop = [" + excess_diskio_field_drop_list_str[:-2] + "]\n"
        
        if is_lad:
            agentconf += "  urls = [\"" + str(me_url) + "\"]\n\n"
            agentconf += "  udp_payload = \"2048B\"\n\n"
        else:
            agentconf += "  data_format = \"influx\"\n"
            agentconf += "  address = \"" + str(me_url) + "\"\n\n"
    if has_mdsd_output:
        agentconf += "\n# Configuration for sending metrics to MDSD\n"
        agentconf += "[[outputs.socket_writer]]\n"
        agentconf += "  namepass = [" + storage_namepass_str[:-2] + "]\n"
        agentconf += "  data_format = \"influx\"\n"
        agentconf += "  address = \"" + str(mdsd_url) + "\"\n\n"
    agentconf += "\n# Configuration for outputing metrics to file. Uncomment to enable.\n"
    agentconf += "#[[outputs.file]]\n"
    agentconf += "#  files = [\"./metrics_to_file.out\"]\n\n"

    agent_file = {"filename":"telegraf.conf", "data": agentconf}
    output.append(agent_file)


    return output, storage_namepass_list


def write_configs(configs, telegraf_conf_dir, telegraf_d_conf_dir):
    """
    Write the telegraf config created by config parser method to disk at the telegraf config location
    :param configs: Telegraf config data parsed by the parse_config method above
    :param telegraf_conf_dir: Path where the telegraf.conf is written to on the disk
    :param telegraf_d_conf_dir: Path where the individual module telegraf configs are written to on the disk
    """
    # Delete the older config folder to prevent telegraf from loading older configs
    if os.path.exists(telegraf_conf_dir):
        rmtree(telegraf_conf_dir)

    os.mkdir(telegraf_conf_dir)

    os.mkdir(telegraf_d_conf_dir)

    for configfile in configs:
        if configfile["filename"] == "telegraf.conf" or configfile["filename"] == "intermediate.json":
            path = telegraf_conf_dir + configfile["filename"]
        else:
            path = telegraf_d_conf_dir + configfile["filename"]
        with open(path, "w") as f:
            f.write(configfile["data"])



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


def is_running(is_lad):
    """
    This method is used to check if telegraf binary is currently running on the system or not.
    In order to check whether it needs to be restarted from the watcher daemon
    """
    if is_lad:
        telegraf_bin = metrics_constants.lad_telegraf_bin
    else:
        telegraf_bin = metrics_constants.ama_telegraf_bin

    proc = subprocess.Popen(["ps  aux | grep telegraf | grep -v grep"], stdout=subprocess.PIPE, shell=True)
    output = proc.communicate()[0]
    if telegraf_bin in output.decode('utf-8', 'ignore'):
        return True
    else:
        return False

def stop_telegraf_service(is_lad):
    """
    Stop the telegraf service if VM is using is systemd, otherwise check if the pid_file exists,
    and if the pid belongs to the Telegraf process, if yes, then kill the process
    This method is called before remove_telegraf_service by the main extension code
    :param is_lad: boolean whether the extension is LAD or not (AMA)
    """

    if is_lad:
        telegraf_bin = metrics_constants.lad_telegraf_bin
    else:
        telegraf_bin = metrics_constants.ama_telegraf_bin

    # If the VM has systemd, then we will use that to stop
    if metrics_utils.is_systemd():
        code = 1
        telegraf_service_path = get_telegraf_service_path(is_lad)
        telegraf_service_name = get_telegraf_service_name(is_lad)

        if os.path.isfile(telegraf_service_path):
            code = os.system("systemctl stop {0}".format(telegraf_service_name))              
        else:
            return False, "Telegraf service file does not exist. Failed to stop telegraf service: {0}.service.".format(telegraf_service_name)

        if code != 0:
            return False, "Unable to stop telegraf service: {0}.service. Run systemctl status {0}.service for more info.".format(telegraf_service_name)

    # Whether or not VM has systemd, let's check if we have any telegraf pids saved and if so, terminate the associated process
    _, configFolder = get_handler_vars()
    telegraf_conf_dir = configFolder + "/telegraf_configs/"
    telegraf_pid_path = telegraf_conf_dir + "telegraf_pid.txt"
    if os.path.isfile(telegraf_pid_path):
        with open(telegraf_pid_path, "r") as f:
            for pid in f.readlines():
                # Verify the pid actually belongs to telegraf
                cmd_path = os.path.join("/proc", str(pid.strip("\n")), "cmdline")
                if os.path.exists(cmd_path):
                    with open(cmd_path, "r") as cmd_f:
                        cmdline = cmd_f.readlines()
                        if cmdline[0].find(telegraf_bin) >= 0:
                            os.kill(int(pid), signal.SIGKILL)
        os.remove(telegraf_pid_path)
    elif not metrics_utils.is_systemd():
        return False, "Could not find telegraf service nor process to stop."

    return True, "Successfully stopped metrics-sourcer service"


def remove_telegraf_service(is_lad):
    """
    Remove the telegraf service if the VM is using systemd as well as the telegraf Binary
    This method is called after stop_telegraf_service by the main extension code during Extension uninstall
    :param is_lad: boolean whether the extension is LAD or not (AMA)
    """

    telegraf_service_path = get_telegraf_service_path(is_lad)
    telegraf_service_name = get_telegraf_service_name(is_lad)

    if os.path.isfile(telegraf_service_path):
        os.remove(telegraf_service_path)
    else:
        return True, "Unable to remove the Telegraf service as the file doesn't exist."

    # Checking To see if the file was successfully removed, since os.remove doesn't return an error code
    if os.path.isfile(telegraf_service_path):
        return False, "Unable to remove telegraf service: {0}.service at {1}.".format(telegraf_service_name, telegraf_service_path)

    return True, "Successfully removed {0} service".format(telegraf_service_name)


def setup_telegraf_service(is_lad, telegraf_bin, telegraf_d_conf_dir, telegraf_agent_conf, HUtilObj=None):
    """
    Add the metrics-sourcer service if the VM is using systemd
    This method is called in handle_config
    :param telegraf_bin: path to the telegraf binary
    :param telegraf_d_conf_dir: path to telegraf .d conf subdirectory
    :param telegraf_agent_conf: path to telegraf .conf file
    """
    telegraf_service_path = get_telegraf_service_path(is_lad)
    telegraf_service_template_path = os.getcwd() + "/services/metrics-sourcer.service"

    if not os.path.exists(telegraf_d_conf_dir):
        raise Exception("Telegraf config directory does not exist. Failed to setup telegraf service.")

    if not os.path.isfile(telegraf_agent_conf):
        raise Exception("Telegraf agent config does not exist. Failed to setup telegraf service.")

    if os.path.isfile(telegraf_service_template_path):

        copyfile(telegraf_service_template_path, telegraf_service_path)

        if os.path.isfile(telegraf_service_path):
            os.system(r"sed -i 's+%TELEGRAF_BIN%+{1}+' {0}".format(telegraf_service_path, telegraf_bin))
            os.system(r"sed -i 's+%TELEGRAF_AGENT_CONFIG%+{1}+' {0}".format(telegraf_service_path, telegraf_agent_conf))
            os.system(r"sed -i 's+%TELEGRAF_CONFIG_DIR%+{1}+' {0}".format(telegraf_service_path, telegraf_d_conf_dir))

            daemon_reload_status = os.system("systemctl daemon-reload")
            if daemon_reload_status != 0:
                message = "Unable to reload systemd after Telegraf service file change. Failed to setup telegraf service. Check system for hardening. Exit code:" + str(daemon_reload_status)
                if HUtilObj is not None:
                    HUtilObj.log(message)
                else:
                    print('Info: {0}'.format(message))

        else:
            raise Exception("Unable to copy Telegraf service template file to {0}. Failed to setup telegraf service.".format(telegraf_service_path))
    else:
        raise Exception("Telegraf service template file does not exist at {0}. Failed to setup telegraf service.".format(telegraf_service_template_path))

    return True


def start_telegraf(is_lad):
    """
    Start the telegraf service if VM is using is systemd, otherwise start the binary as a process and store the pid
    to a file in the telegraf config directory
    This method is called after config setup is completed by the main extension code
    :param is_lad: boolean whether the extension is LAD or not (AMA)
    """

    # Re using the code to grab the config directories and imds values because start will be called from Enable process outside this script
    log_messages = ""

    if is_lad:
        telegraf_bin = metrics_constants.lad_telegraf_bin
    else:
        telegraf_bin = metrics_constants.ama_telegraf_bin

    if not os.path.isfile(telegraf_bin):
        log_messages += "Telegraf binary does not exist. Failed to start telegraf service."
        return False, log_messages

    # Ensure that any old telegraf processes are cleaned up to avoid duplication
    stop_telegraf_service(is_lad)

    # If the VM has systemd, telegraf will be managed as a systemd service
    telegraf_service_name = get_telegraf_service_name(is_lad)
    if metrics_utils.is_systemd():
        service_restart_status = os.system("systemctl restart {0}".format(telegraf_service_name))        
        if service_restart_status != 0:
            log_messages += "Unable to start Telegraf service using systemctl. Failed to start telegraf service. Check system for hardening."
            return False, log_messages

    # Otherwise, start telegraf as a process and save the pid to a file so that we can terminate it while disabling/uninstalling
    else:
        _, configFolder = get_handler_vars()
        telegraf_conf_dir = configFolder + "/telegraf_configs/"
        telegraf_agent_conf = telegraf_conf_dir + "telegraf.conf"
        telegraf_d_conf_dir = telegraf_conf_dir + "telegraf.d/"
        telegraf_pid_path = telegraf_conf_dir + "telegraf_pid.txt"

        binary_exec_command = "{0} --config {1} --config-directory {2}".format(telegraf_bin, telegraf_agent_conf, telegraf_d_conf_dir)
        proc = subprocess.Popen(binary_exec_command.split(" "), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # Sleeping for 3 seconds before checking if the process is still running, to give it ample time to relay crash info
        time.sleep(3)
        p = proc.poll()

        # Process is running successfully
        if p is None:
            telegraf_pid = proc.pid

            # Write this pid to a file for future use
            try:
                with open(telegraf_pid_path, "a") as f:
                    f.write(str(telegraf_pid) + '\n')
            except Exception as e:
                log_messages += "Successfully started telegraf binary, but could not save telegraf pidfile."
        else:
            out, err = proc.communicate()
            log_messages += "Unable to run telegraf binary as a process due to error - {0}. Failed to start telegraf.".format(err)
            return False, log_messages
    return True, log_messages


def get_telegraf_service_path(is_lad):
    """
    Utility method to get the service path in case /lib/systemd/system doesnt exist on the OS
    """
    if is_lad:
        if os.path.exists("/lib/systemd/system/"):
            return metrics_constants.lad_telegraf_service_path
        elif os.path.exists("/usr/lib/systemd/system/"):
            return metrics_constants.lad_telegraf_service_path_usr_lib
        else:
            raise Exception("Systemd unit files do not exist at /lib/systemd/system or /usr/lib/systemd/system/. Failed to setup telegraf service.")
    else:
        if os.path.exists("/lib/systemd/system/"):
            return metrics_constants.telegraf_service_path
        elif os.path.exists("/usr/lib/systemd/system/"):
            return metrics_constants.telegraf_service_path_usr_lib
        else:
            raise Exception("Systemd unit files do not exist at /lib/systemd/system or /usr/lib/systemd/system/. Failed to setup telegraf service.")

def get_telegraf_service_name(is_lad):
    """
    Utility method to get the service name
    """
    if(is_lad):    
        return metrics_constants.lad_telegraf_service_name
    else:
        return metrics_constants.telegraf_service_name
        

def handle_config(config_data, me_url, mdsd_url, is_lad):
    """
    The main method to perfom the task of parsing the config , writing them to disk, setting up, stopping, removing and starting telegraf
    :param config_data: Parsed Metrics Configuration from which telegraf config is created
    :param me_url: The url to which telegraf will send metrics to for MetricsExtension
    :param mdsd_url: The url to which telegraf will send metrics to for MDSD
    :param is_lad: Boolean value for whether the extension is Lad or not (AMA)
    """

    # Making the imds call to get resource id, sub id, resource group and region for the dimensions for telegraf metrics
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

        req = urllib.Request(imdsurl, headers={'Metadata':'true'})
        res = urllib.urlopen(req)
        data = json.loads(res.read().decode('utf-8', 'ignore'))

        if "compute" not in data:
            retries += 1
        else:
            break

        time.sleep(sleep_time)

    if retries > max_retries:
        raise Exception("Unable to find 'compute' key in imds query response. Reached max retry limit of - {0} times. Failed to setup Telegraf.".format(max_retries))

    if "resourceId" not in data["compute"]:
        raise Exception("Unable to find 'resourceId' key in imds query response. Failed to setup Telegraf.")

    # resource id is needed for ME to show metrics on the metrics blade of the VM/VMSS
    # ME expected ID- /subscriptions/<sub-id>/resourceGroups/<rg_name>/providers/Microsoft.Compute/virtualMachineScaleSets/<VMSSName>
    # or /subscriptions/20ff167c-9f4b-4a73-9fd6-0dbe93fa778a/resourceGroups/sidama/providers/Microsoft.Compute/virtualMachines/syslogReliability_1ec84a39
    az_resource_id = data["compute"]["resourceId"]

    # If the instance is VMSS instance resource id of a uniform VMSS then trim the last two values from the resource id ie - "/virtualMachines/0"
    # Since ME expects the resource id in a particular format. For egs -
    # IMDS returned ID - /subscriptions/<sub-id>/resourceGroups/<rg_name>/providers/Microsoft.Compute/virtualMachineScaleSets/<VMSSName>/virtualMachines/0
    # ME expected ID- /subscriptions/<sub-id>/resourceGroups/<rg_name>/providers/Microsoft.Compute/virtualMachineScaleSets/<VMSSName>
    if "virtualMachineScaleSets" in az_resource_id: 
        az_resource_id = "/".join(az_resource_id.split("/")[:-2])

    virtual_machine_name = ""
    if "vmScaleSetName" in data["compute"] and data["compute"]["vmScaleSetName"] != "":
        virtual_machine_name = data["compute"]["name"]
        # for flexible VMSS above resource id is instance specific and won't have virtualMachineScaleSets
        # for e.g., /subscriptions/20ff167c-9f4b-4a73-9fd6-0dbe93fa778a/resourceGroups/sidama/providers/Microsoft.Compute/virtualMachines/syslogReliability_1ec84a39
        # ME expected ID- /subscriptions/<sub-id>/resourceGroups/<rg_name>/providers/Microsoft.Compute/virtualMachineScaleSets/<VMSSName>
        if "virtualMachineScaleSets" not in az_resource_id: 
            az_resource_id = "/".join(az_resource_id.split("/")[:-2]) + "/virtualMachineScaleSets/" + data["compute"]["vmScaleSetName"]

    if "subscriptionId" not in data["compute"]:
        raise Exception("Unable to find 'subscriptionId' key in imds query response. Failed to setup Telegraf.")

    subscription_id = data["compute"]["subscriptionId"]

    if "resourceGroupName" not in data["compute"]:
        raise Exception("Unable to find 'resourceGroupName' key in imds query response. Failed to setup Telegraf.")

    resource_group = data["compute"]["resourceGroupName"]

    if "location" not in data["compute"]:
        raise Exception("Unable to find 'location' key in imds query response. Failed to setup Telegraf.")

    region = data["compute"]["location"]

    #call the method to first parse the configs
    output, namespaces = parse_config(config_data, me_url, mdsd_url, is_lad, az_resource_id, subscription_id, resource_group, region, virtual_machine_name)

    _, configFolder = get_handler_vars()
    if is_lad:
        telegraf_bin = metrics_constants.lad_telegraf_bin
    else:
        telegraf_bin = metrics_constants.ama_telegraf_bin

    telegraf_conf_dir = configFolder + "/telegraf_configs/"
    telegraf_agent_conf = telegraf_conf_dir + "telegraf.conf"
    telegraf_d_conf_dir = telegraf_conf_dir + "telegraf.d/"


    #call the method to write the configs
    write_configs(output, telegraf_conf_dir, telegraf_d_conf_dir)

    # Setup Telegraf service.
    # If the VM has systemd, then we will copy over the systemd unit file and use that to start/stop
    if metrics_utils.is_systemd():
        telegraf_service_setup = setup_telegraf_service(is_lad, telegraf_bin, telegraf_d_conf_dir, telegraf_agent_conf)
        if not telegraf_service_setup:
            return False, []

    return True, namespaces
