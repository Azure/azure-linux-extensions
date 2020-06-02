import json
import os
from telegraf_utils.telegraf_name_map import name_map
import subprocess
import signal
import urllib2
from shutil import copyfile



"""
Sample input data received by this script
[
    {
        "displayName" : "Network->Packets sent",
        "interval" : "15s"
    },
    {
        "displayName" : "Network->Packets recieved",
        "interval" : "15s"
    }
]
"""


def parse_config(data, me_url, mdsd_url, is_lad, az_resource_id, subscription_id, resource_group, region):

    lad_storage_namepass_list = []
    lad_storage_namepass_str = ""

    ama_storage_namepass_list = []
    ama_storage_namepass_str = ""

    if len(data) == 0:
        raise Exception("Empty config data received.")
        return []

    if me_url is None or mdsd_url is None:
        raise Exception("No url provided for Influxdb output plugin to ME, AMA.")
        return []

    telegraf_json = {}

    for item in data:
        counter = item["displayName"]
        if counter in name_map:
            plugin = name_map[counter]["plugin"]
            omiclass = counter.split("->")[0]
            if omiclass not in telegraf_json:
                telegraf_json[omiclass] = {}
            if plugin not in telegraf_json[omiclass]:
                telegraf_json[omiclass][plugin] = {}
            telegraf_json[omiclass][plugin][name_map[counter]["field"]] = {}
            telegraf_json[omiclass][plugin][name_map[counter]["field"]]["displayName"] = counter.split("->")[1]
            telegraf_json[omiclass][plugin][name_map[counter]["field"]]["interval"] = item["interval"]
            if is_lad:
                telegraf_json[omiclass][plugin][name_map[counter]["field"]]["ladtablekey"] = name_map[counter]["ladtablekey"]
            if "op" in name_map[counter]:
                telegraf_json[omiclass][plugin][name_map[counter]["field"]]["op"] = name_map[counter]["op"]

    """
    Sample converted telegraf conf dict -

    u'network': {
        'net': {
            'err_in': {  'interval': u'15s',  'displayName': u'Packets received errors'},
            'packets_sent': {  'interval': u'15s',  'displayName': u'Packets sent'},
            'bytes_recv': {  'interval': u'5s',  'displayName': u'Network in guest OS'},
            'packets_recv': {  'interval': u'5s',  'displayName': u'Packets received'},
            'err_out': {  'interval': u'15s',  'displayName': u'Packets sent errors'},
            'bytes_sent': {  'interval': u'15s',  'displayName': u'Network out guest OS'}
        }
    },
    u'filesystem': {
        'disk': {
            'used_percent': {  'interval': u'15s',  'displayName': u'Filesystem % used space'},
            'used': {  'interval': u'15s',
                'displayName': u'Filesystem used space'},
            'free': {  'interval': u'15s',  'displayName': u'Filesystem free space'}
        },
        'diskio': {
            'write_bytes': {  'interval': u'15s',  'displayName': u'Filesystem write bytes/sec',  'op': 'rate'},
            'read_bytes': {  'interval': u'15s',  'displayName': u'Filesystem read bytes/sec',  'op': 'rate'},
            'writes': {  'interval': u'15s',  'displayName': u'Filesystem writes/sec',  'op': 'rate'},
            'reads': {  'interval': u'15s',  'displayName': u'Filesystem reads/sec',  'op': 'rate'}
        }
    },
    """

    if len(telegraf_json) == 0:
        raise Exception("Unable to parse telegraf config into intermediate dictionary.")
        return []



    int_file = {"filename":"intermediate.json", "data": json.dumps(telegraf_json)}
    output = []
    output.append(int_file)

    for omiclass in telegraf_json:
        input_str = ""
        ama_rename_str = ""
        lad_specific_rename_str = ""
        rate_specific_aggregator_str = ""
        aggregator_str = ""
        for plugin in telegraf_json[omiclass]:
            config_file = {"filename" : omiclass+".conf"}
            min_interval = "999999999s" #arbitrary max value for finding min
            input_str += "[[inputs." + plugin + "]]\n"
            # input_str += " "*2 + "name_override = \"" + omiclass + "\"\n"
            
            # If it's a lad config then add the namepass fields for sending totals to storage
            if is_lad:
                lad_plugin_name = plugin + "_total"
                lad_specific_rename_str += "\n[[processors.rename]]\n"
                lad_specific_rename_str += " "*2 + "namepass = [\"" + lad_plugin_name + "\"]\n"
                if lad_plugin_name not in lad_storage_namepass_list:
                    lad_storage_namepass_list.append(lad_plugin_name)
            else:
                ama_rename_str += "\n[[processors.rename]]\n"
                ama_rename_str += " "*2 + "namepass = [\"" + plugin + "\"]\n"

           
            fields = ""
            ops_fields = ""
            non_ops_fields = ""
            non_rate_aggregate = False
            ops = ""
            min_agg_period = ""
            rate_aggregate = False
            for field in telegraf_json[omiclass][plugin]:
                fields += "\"" + field + "\", "
                
                #Use the shortest interval time for the whole plugin
                new_interval = telegraf_json[omiclass][plugin][field]["interval"]
                if int(new_interval[:-1]) < int(min_interval[:-1]): 
                    min_interval = new_interval
                
                #compute values for aggregator options
                if "op" in telegraf_json[omiclass][plugin][field]:
                    if telegraf_json[omiclass][plugin][field]["op"] == "rate":
                        rate_aggregate = True
                        ops = "\"rate\", \"rate_min\", \"rate_max\", \"rate_count\", \"rate_sum\", \"rate_mean\""
                    ops_fields += "\"" +  telegraf_json[omiclass][plugin][field]["ladtablekey"] + "\", "
                else:
                    non_rate_aggregate = True 
                    non_ops_fields += "\"" +  telegraf_json[omiclass][plugin][field]["ladtablekey"] + "\", "
                
                #Aggregation perdiod needs to be double of interval/polling period for metrics for rate aggegation to work properly
                if int(min_interval[:-1]) > 30:
                    min_agg_period = str(int(min_interval[:-1])*2)  #if the min interval is greater than 30, use the double value
                else:
                    min_agg_period = "60"   #else use 60 as mininum so that we can maintain 1 event per minute

                #Add respective rename processor plugin based on the displayname
                if is_lad:
                    lad_specific_rename_str += "\n" + " "*2 + "[[processors.rename.replace]]\n" 
                else:
                    ama_rename_str += "\n" + " "*2 + "[[processors.rename.replace]]\n" 

                if "op" in telegraf_json[omiclass][plugin][field]:
                    if is_lad:
                        lad_specific_rename_str += " "*4 + "field = \"" + field + "\"\n"
                        lad_specific_rename_str += " "*4 + "dest = \"" + telegraf_json[omiclass][plugin][field]["ladtablekey"] + "\"\n"
                    else:
                        ama_rename_str += " "*4 + "field = \"" + field + "\"\n"
                        ama_rename_str += " "*4 + "dest = \"" + telegraf_json[omiclass][plugin][field]["displayName"] + "\"\n"
                else:
                    if is_lad:
                        lad_specific_rename_str += " "*4 + "field = \"" + field + "\"\n"
                        lad_specific_rename_str += " "*4 + "dest = \"" + telegraf_json[omiclass][plugin][field]["ladtablekey"] + "\"\n"
                    else:
                        ama_rename_str += " "*4 + "field = \"" + field + "\"\n"
                        ama_rename_str += " "*4 + "dest = \"" + telegraf_json[omiclass][plugin][field]["displayName"] + "\"\n"
                        

            #Add respective operations for aggregators
            if is_lad:
                if rate_aggregate:
                    aggregator_str += "[[aggregators.basicstats]]\n"
                    aggregator_str += " "*2 + "namepass = [\"" + plugin + "_total\"]\n"
                    aggregator_str += " "*2 + "period = \"" + min_agg_period + "s\"\n"
                    aggregator_str += " "*2 + "drop_original = true\n"
                    aggregator_str += " "*2 + "fieldpass = [" + ops_fields[:-2] + "]\n" #-2 to strip the last comma and space
                    aggregator_str += " "*2 + "stats = [" + ops + "]\n"
                    aggregator_str += " "*2 + "rate_period = \"" + min_agg_period + "s\"\n\n"
                
                if non_rate_aggregate:
                    aggregator_str += "[[aggregators.basicstats]]\n"
                    aggregator_str += " "*2 + "namepass = [\"" + plugin + "_total\"]\n"
                    aggregator_str += " "*2 + "period = \"" + min_agg_period + "s\"\n"
                    aggregator_str += " "*2 + "drop_original = true\n"
                    aggregator_str += " "*2 + "fieldpass = [" + non_ops_fields[:-2] + "]\n" #-2 to strip the last comma and space
                    aggregator_str += " "*2 + "stats = [\"mean\", \"max\", \"min\", \"sum\", \"count\"]\n\n"
            



            if is_lad:
                lad_specific_rename_str += "\n"
            else:
                ama_rename_str += "\n"

            input_str += " "*2 + "fieldpass = ["+fields[:-2]+"]\n"  #Using fields[: -2] here to get rid of the last ", " at the end of the string
            if plugin == "cpu":
                input_str += " "*2 + "report_active = true\n"
            input_str += " "*2 + "interval = " + "\"" + min_interval + "\"\n\n"
        
            config_file["data"] = input_str + "\n" + ama_rename_str + "\n" + lad_specific_rename_str + "\n"  +aggregator_str

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

    for measurement in lad_storage_namepass_list:
        lad_storage_namepass_str += "\"" + measurement + "\", "
    
    # Telegraf basic agent and output config 
    agentconf = "[agent]\n"
    agentconf += "  interval = \"10s\"\n"
    agentconf += "  round_interval = true\n"
    agentconf += "  metric_batch_size = 1000\n"
    agentconf += "  metric_buffer_limit = 10000\n"
    agentconf += "  collection_jitter = \"0s\"\n"
    agentconf += "  flush_interval = \"10s\"\n"
    agentconf += "  flush_jitter = \"0s\"\n"
    agentconf += "  logtarget = \"file\"\n"
    agentconf += "  logfile = \"" + logFolder + "/telegraf.log\"\n"
    agentconf += "  logfile_rotation_max_size = \"100MB\"\n"
    agentconf += "  logfile_rotation_max_archives = 5\n" 
    agentconf += "\n# Configuration for adding gloabl tags\n"
    agentconf += "[global_tags]\n"
    agentconf += "  DeploymentId= \"${DeploymentId}\"\n"          
    agentconf += "  \"microsoft.subscriptionId\"= \"" + subscription_id + "\"\n"
    agentconf += "  \"microsoft.resourceGroupName\"= \"" + resource_group + "\"\n"
    agentconf += "  \"microsoft.regionName\"= \"" + region + "\"\n"          
    agentconf += "  \"microsoft.resourceId\"= \"" + az_resource_id + "\"\n"          
    agentconf += "\n# Configuration for sending metrics to ME\n"
    agentconf += "[[outputs.influxdb]]\n"
    if is_lad:
        agentconf += "  namedrop = [" + lad_storage_namepass_str[:-2] + "]\n"
    agentconf += "  urls = [\"" + str(me_url) + "\"]\n\n"
    agentconf += "\n# Configuration for sending metrics to AMA\n"
    agentconf += "[[outputs.influxdb]]\n"
    if is_lad:
        agentconf += "  namepass = [" + lad_storage_namepass_str[:-2] + "]\n"
    agentconf += "  urls = [\"" + str(mdsd_url) + "\"]\n\n"
    agentconf += "\n# Configuration for outputing metrics to file. Uncomment to enable.\n"
    agentconf += "#[[outputs.file]]\n"
    agentconf += "#  files = [\"./metrics_to_file.out\"]\n\n"

    agent_file = {"filename":"telegraf.conf", "data": agentconf}
    output.append(agent_file)

    return output, lad_storage_namepass_list


def write_configs(configs, telegraf_conf_dir, telegraf_d_conf_dir):

    if not os.path.exists(telegraf_conf_dir):
        os.mkdir(telegraf_conf_dir)

    if not os.path.exists(telegraf_d_conf_dir):
        os.mkdir(telegraf_d_conf_dir)

    for configfile in configs:
        if configfile["filename"] == "telegraf.conf" or configfile["filename"] == "intermediate.json":
            path = telegraf_conf_dir + configfile["filename"]
        else:
            path = telegraf_d_conf_dir + configfile["filename"]
        with open(path, "w") as f:
            f.write(configfile["data"])



def get_handler_vars():
    logFolder = "./LADtelegraf/"
    configFolder = "./telegraf_configs/"
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


def stop_telegraf_service():
    
    # If the VM has systemd, then we will use that to stop
    check_systemd = os.system("pidof systemd 1>/dev/null 2>&1")
    if check_systemd == 0:
        code = 1
        telegraf_service_path = "/lib/systemd/system/metrics-sourcer.service"
        
        if os.path.isfile(telegraf_service_path):
            code = os.system("sudo systemctl stop metrics-sourcer")
        else:
            # raise Exception("Telegraf service file does not exist. Failed to stop telegraf service: metrics-sourcer.service .")
            return False, "Telegraf service file does not exist. Failed to stop telegraf service: metrics-sourcer.service ."
        
        if code != 0:
            # raise Exception("Unable to stop telegraf service: metrics-sourcer.service .")
            return False, "Unable to stop telegraf service: metrics-sourcer.service. Run systemctl status metrics-sourcer.service for more info."
    else:
        #This VM does not have systemd, So we will use the pid from the last ran telegraf process and terminate it
        _, configFolder = get_handler_vars()
        telegraf_conf_dir = configFolder + "/telegraf_configs/"
        telegraf_pid_path = telegraf_conf_dir + "telegraf_pid.txt"
        if os.path.isfile(telegraf_pid_path):
            pid = ""
            with open(telegraf_pid_path, "r") as f:
                pid = f.read()
            if pid != "":
                os.kill(pid, signal.SIGKILL)
            else:
                return False, "No pid found for an currently running telegraf process in {0}. Failed to stop telegraf.".format(telegraf_pid_path)
        else:
            return False, "File containing the pid for the running telegraf process at {0} does not exit. Failed to stop telegraf".format(telegraf_pid_path)

    return True, "Successfully stopped metrics-sourcer service"


def remove_telegraf_service():

    _, configFolder = get_handler_vars()
    telegraf_service_path = "/lib/systemd/system/metrics-sourcer.service"
    code = 1
    
    if os.path.isfile(telegraf_service_path):
        code = os.remove(telegraf_service_path)
    else:
        #Service file doesnt exist or is already removed, exit the method with exit code 0
        return True, "Metrics sourcer service file doesnt exist or is already removed"
    
    if code != 0:
        # raise Exception("Unable to remove telegraf service: metrics-sourcer.service .")
        return False, "Unable to remove telegraf service: metrics-sourcer.service."

    return True, "Successfully removed metrics-sourcer service"


def setup_telegraf_service(telegraf_bin, telegraf_d_conf_dir, telegraf_agent_conf):

    telegraf_service_path = "/lib/systemd/system/metrics-sourcer.service"
    telegraf_service_template_path = os.getcwd() + "/services/metrics-sourcer.service"
    

    if not os.path.exists(telegraf_d_conf_dir):
        raise Exception("Telegraf config directory does not exist. Failed to setup telegraf service.")
        return False

    if not os.path.isfile(telegraf_agent_conf):
        raise Exception("Telegraf agent config does not exist. Failed to setup telegraf service.")
        return False
    
    if not os.path.isfile(telegraf_bin):
        raise Exception("Telegraf binary does not exist. Failed to setup telegraf service.")
        return False       

    if os.path.isfile(telegraf_service_template_path):

        copyfile(telegraf_service_template_path, telegraf_service_path)

        if os.path.isfile(telegraf_service_path):
            os.system(r"sed -i 's+%TELEGRAF_BIN%+{1}+' {0}".format(telegraf_service_path, telegraf_bin)) 
            os.system(r"sed -i 's+%TELEGRAF_AGENT_CONFIG%+{1}+' {0}".format(telegraf_service_path, telegraf_agent_conf))
            os.system(r"sed -i 's+%TELEGRAF_CONFIG_DIR%+{1}+' {0}".format(telegraf_service_path, telegraf_d_conf_dir))

            daemon_reload_status = os.system("sudo systemctl daemon-reload")
            if daemon_reload_status != 0:
                raise Exception("Unable to reload systemd after Telegraf service file change. Failed to setup telegraf service.")
                return False
        else:
            raise Exception("Unable to copy Telegraf service template file to {0}. Failed to setup telegraf service.".format(telegraf_service_path))
            return False
    else:
        raise Exception("Telegraf service template file does not exist at {0}. Failed to setup telegraf service.".format(telegraf_service_template_path))
        return False

    return True


def start_telegraf():

    # If the VM has systemd, then we will copy over the systemd unit file and use that to start/stop
    check_systemd = os.system("pidof systemd 1>/dev/null 2>&1")
    if check_systemd == 0:
        service_restart_status = os.system("sudo systemctl restart metrics-sourcer")
        if service_restart_status != 0:
            raise Exception("Unable to start Telegraf service. Failed to setup telegraf service.")
            return False        

    #Else start telegraf as a process and save the pid to a file so that we can terminate it while disabling/uninstalling
    else:
        #Reusing the code to create these variables inside this function because start_telegraf can also be called durint Enable process outisde this script
        _, configFolder = get_handler_vars()
        telegraf_bin = "/usr/local/lad/bin/telegraf"
        telegraf_conf_dir = configFolder + "/telegraf_configs/"
        telegraf_agent_conf = telegraf_conf_dir + "telegraf.conf"
        telegraf_d_conf_dir = telegraf_conf_dir + "telegraf.d/"
        telegraf_pid_path = telegraf_conf_dir + "telegraf_pid.txt"

        binary_exec_command = "{0} --config {1} --config-directory {2}".format(telegraf_bin, telegraf_agent_conf, telegraf_d_conf_dir)
        proc = subprocess.Popen(binary_exec_command.split(" "), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(3) #sleeping for 3 seconds before checking if the process is still running, to give it ample time to relay crash info
        p = proc.poll()

        if p is None: #Process is running successfully
            telegraf_pid = proc.pid
            
            #write this pid to a file for future use
            with open(telegraf_pid_path, "w+") as f:
                f.write(telegraf_pid)
        else:
            out, err = proc.communicate()
            raise Exception("Unable to run telegraf binary as a process due to error - {0}. Failed to start telegraf.".format(err))
            return False
    return True
    

def handle_config(config_data, me_url, mdsd_url, is_lad=False):
    #main method to perfom the task of parsing the config , writing them to disk, setting up and starting telegraf service

    #Making the imds call to get resource id, sub id, resource group and region for the dimensions for telegraf metrics

    # imdsurl = "http://169.254.169.254/metadata/instance?api-version=2019-03-11"
    # #query imds to get the required information 
    # req = urllib2.Request(imdsurl, headers={'Metadata':'true'})
    # res = urllib2.urlopen(req)
    # data = json.loads(res.read())

    data = {"compute":{"azEnvironment":"AzurePublicCloud","customData":"","location":"eastus","name":"ubtest-16","offer":"UbuntuServer","osType":"Linux","placementGroupId":"","plan":{"name":"","product":"","publisher":""},"platformFaultDomain":"0","platformUpdateDomain":"0","provider":"Microsoft.Compute","publicKeys":[{"keyData":"ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQDJmcpHCPcSg+J0S7pbqj5X08iaIMulAc7qq1iLPrcSu04alVWQTFE58f3LbabDwDBhiXIgWO4W4/26l0+arTLOj6TJe9EiaabAYniUglC0ChbgMTjAvXQCbtwLc2yo30Uh4DbdFhEo9UXG/AeYdwvt7TCVYFrd/seGQ+7dENcFdyd4rRs1hZdMxKil+Tx0dBoFE+IEydY6PSm48qgq7XlteLAT6q/Gqpo4wVqboyTcal+QIZftDfSlJ2G+Asem/mjWj9U1nhJeBcRy2JWOSJeKgojCI3WZUMVly6lkxbX6c1UYHkT53w/tFxMehm9TUUiviOTZOAXIE6Yj/7KWlGmosJPTCA6VSRr3b5RS3lgRerOIwwb/FDAlaM7mQs/Qssm51+yHw4WSdDeYQ94n5wH5mUKoX8SqzLl3gAy6wHj9bi3jD1Txoscks0HSpHR9Lrxoy06TMLs8h3CygSdZr7kTkf5PXtKE3Gqbg54cyp+Wa2FGO0ijQ0paLEI2rPWRwxVUOkrs4r7i9YH0sJcEOUaoEiWMiNdeV5Zo9ciGddgCDz1EXdWoO6JPleD5r6W1dFfcsPnsaLl56fU/J/FDvwSj7et7AyKPwQvNQFQwtP6/tHoMksDUmBSadUWM0wA+Dbn0Ve7V6xdCXbqUn+Cs22EFPxqpnX7kl5xeq7XVWW+Mbw== nidhanda@microsoft.com","path":"/home/nidhanda/.ssh/authorized_keys"}],"publisher":"Canonical","resourceGroupName":"nidhanda_test","resourceId":"/subscriptions/13723929-6644-4060-a50a-cc38ebc5e8b1/resourceGroups/nidhanda_test/providers/Microsoft.Compute/virtualMachines/ubtest-16","sku":"16.04-LTS","subscriptionId":"13723929-6644-4060-a50a-cc38ebc5e8b1","tags":"","version":"16.04.202004290","vmId":"4bb331fc-2320-49d5-bb5e-bcdff8ab9e74","vmScaleSetName":"","vmSize":"Basic_A1","zone":""},"network":{"interface":[{"ipv4":{"ipAddress":[{"privateIpAddress":"172.16.16.6","publicIpAddress":"13.68.157.2"}],"subnet":[{"address":"172.16.16.0","prefix":"24"}]},"ipv6":{"ipAddress":[]},"macAddress":"000D3A4DDE5F"}]}}
    if "compute" not in data:
        raise Exception("Unable to find 'compute' key in imds query response. Failed to setup Telegraf.")
        return False

    if "resourceId" not in data["compute"]:
        raise Exception("Unable to find 'resourceId' key in imds query response. Failed to setup Telegraf.")
        return False   

    az_resource_id = data["compute"]["resourceId"]
    
    if "subscriptionId" not in data["compute"]:
        raise Exception("Unable to find 'subscriptionId' key in imds query response. Failed to setup Telegraf.")
        return False

    subscription_id = data["compute"]["subscriptionId"]

    if "resourceGroupName" not in data["compute"]:
        raise Exception("Unable to find 'resourceGroupName' key in imds query response. Failed to setup Telegraf.")
        return False

    resource_group = data["compute"]["resourceGroupName"]
    
    if "location" not in data["compute"]:
        raise Exception("Unable to find 'location' key in imds query response. Failed to setup Telegraf.")
        return False

    region = data["compute"]["location"]

    #call the method to first parse the configs
    output, namespaces = parse_config(config_data, me_url, mdsd_url, is_lad, az_resource_id, subscription_id, resource_group, region)

    _, configFolder = get_handler_vars()
    telegraf_bin = "/usr/local/lad/bin/telegraf"
    telegraf_conf_dir = configFolder + "/telegraf_configs/"
    telegraf_agent_conf = telegraf_conf_dir + "telegraf.conf"
    telegraf_d_conf_dir = telegraf_conf_dir + "telegraf.d/"


    #call the method to write the configs
    write_configs(output, telegraf_conf_dir, telegraf_d_conf_dir)

    # If the VM has systemd, then we will copy over the systemd unit file and use that to start/stop
    check_systemd = os.system("pidof systemd 1>/dev/null 2>&1")
    if check_systemd == 0:
        telegraf_service_setup = setup_telegraf_service(telegraf_bin, telegraf_d_conf_dir, telegraf_agent_conf)
        if not telegraf_service_setup:
            return False, []

    #Setup and start telegraf 
    result = start_telegraf()
    if not result:
        return False, []

    
    return True, namespaces