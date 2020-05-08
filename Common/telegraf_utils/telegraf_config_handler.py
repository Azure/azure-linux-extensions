import json
import os
from telegraf_utils.telegraf_name_map import name_map


"""
Sample input data received by this script
[
    {
        "displayName" : "Network/Packets sent",
        "interval" : "15s"
    },
    {
        "displayName" : "Network/Packets recieved",
        "interval" : "15s"
    }
]
"""


def parse_config(data, me_url, mdsd_url, is_lad):

    lad_storage_namepass_list = []
    lad_storage_namepass_str = ""

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
        rename_str = ""
        lad_specific_rename_str = ""
        rate_specific_aggregator_str = ""
        aggregator_str = ""
        for plugin in telegraf_json[omiclass]:
            config_file = {"filename" : omiclass+".conf"}
            min_interval = "60s"
            input_str += "[[inputs." + plugin + "]]\n"
            # input_str += " "*2 + "name_override = \"" + omiclass + "\"\n"
            rename_str += "\n[[processors.rename]]\n"
            rename_str += " "*2 + "namepass = [\"" + plugin + "\"]\n"
            
            # If it's a lad config then add the namepass fields for sending totals to storage
            if is_lad:
                lad_plugin_name = plugin + "_total"
                lad_specific_rename_str += "\n[[processors.rename]]\n"
                lad_specific_rename_str += " "*2 + "namepass = [\"" + lad_plugin_name + "\"]\n"
                if lad_plugin_name not in lad_storage_namepass_list:
                    lad_storage_namepass_list.append(lad_plugin_name)
           
            fields = ""
            ops_fields = ""
            non_ops_fields = ""
            non_rate_aggregate = False
            ops = ""
            twiceminperiod = ""
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
                
                twiceminperiod = str(int(min_interval[:-1])*2)
                #Add respective rename processor plugin based on the displayname
                rename_str += "\n" + " "*2 + "[[processors.rename.replace]]\n" 
                if is_lad:
                    lad_specific_rename_str += "\n" + " "*2 + "[[processors.rename.replace]]\n" 
                if "op" in telegraf_json[omiclass][plugin][field]:
                    rename_str += " "*4 + "field = \"" + field + "\"\n"
                    rename_str += " "*4 + "dest = \"" + telegraf_json[omiclass][plugin][field]["displayName"] + "\"\n"
                    if is_lad:
                        lad_specific_rename_str += " "*4 + "field = \"" + field + "\"\n"
                        lad_specific_rename_str += " "*4 + "dest = \"" + telegraf_json[omiclass][plugin][field]["ladtablekey"] + "\"\n"
                else:
                    rename_str += " "*4 + "field = \"" + field + "\"\n"
                    rename_str += " "*4 + "dest = \"" + telegraf_json[omiclass][plugin][field]["displayName"] + "\"\n"
                    if is_lad:
                        lad_specific_rename_str += " "*4 + "field = \"" + field + "\"\n"
                        lad_specific_rename_str += " "*4 + "dest = \"" + telegraf_json[omiclass][plugin][field]["ladtablekey"] + "\"\n"
                        

            #Add respective operations for aggregators
            if is_lad:
                if rate_aggregate:
                    aggregator_str += "[[aggregators.basicstats]]\n"
                    aggregator_str += " "*2 + "namepass = [\"" + plugin + "_total\"]\n"
                    aggregator_str += " "*2 + "period = \"" + twiceminperiod + "s\"\n"
                    aggregator_str += " "*2 + "drop_original = true\n"
                    aggregator_str += " "*2 + "fieldpass = [" + ops_fields[:-2] + "]\n" #-2 to strip the last comma and space
                    aggregator_str += " "*2 + "stats = [" + ops + "]\n"
                    aggregator_str += " "*2 + "rate_period = \"" + twiceminperiod + "s\"\n\n"
                
                if non_rate_aggregate:
                    aggregator_str += "[[aggregators.basicstats]]\n"
                    aggregator_str += " "*2 + "namepass = [\"" + plugin + "_total\"]\n"
                    aggregator_str += " "*2 + "period = \"" + twiceminperiod + "s\"\n"
                    aggregator_str += " "*2 + "drop_original = true\n"
                    aggregator_str += " "*2 + "fieldpass = [" + non_ops_fields[:-2] + "]\n" #-2 to strip the last comma and space
                    aggregator_str += " "*2 + "stats = [\"mean\", \"max\", \"min\", \"sum\", \"count\"]\n\n"
            



            rename_str += "\n"
            if is_lad:
                lad_specific_rename_str += "\n"
            input_str += " "*2 + "fieldpass = ["+fields[:-2]+"]\n"  #Using fields[: -2] here to get rid of the last ", " at the end of the string
            if plugin == "cpu":
                input_str += " "*2 + "report_active = true\n"
            input_str += " "*2 + "interval = " + "\"" + min_interval + "\"\n\n"
        
            config_file["data"] = input_str + "\n" + rename_str + "\n" + lad_specific_rename_str + "\n"  +aggregator_str

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
    agentconf += "\n# Configuration for sending metrics to ME\n"
    agentconf += "[[outputs.influxdb]]\n"
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


def write_configs(configs):

    _, configFolder = get_handler_vars()
    telegraf_conf_dir = configFolder + "/telegraf_configs/"
    if not os.path.exists(telegraf_conf_dir):
        os.mkdir(telegraf_conf_dir)

    for configfile in configs:
        path = telegraf_conf_dir + configfile["filename"]
        with open(path, "w") as f:
            f.write(configfile["data"])



def get_handler_vars():
    logFolder = "./LADtelegraf.log"
    configFolder = "./telegraf_configs"
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

    _, configFolder = get_handler_vars()
    telegraf_service_path = "/lib/systemd/system/metrics-sourcer.service"
     
    code = 1
    if os.path.isfile(telegraf_service_path):
        code = os.system("sudo systemctl stop metrics-sourcer")
    else:
        raise Exception("Telegraf service file does not exist. Failed to stop telegraf service: metrics-sourcer.service .")
        return code
    
    if code != 0:
        raise Exception("Unable to stop telegraf service: metrics-sourcer.service .")

    return code

def setup_telegraf_service():

    _, configFolder = get_handler_vars()
    telegraf_service_path = "/lib/systemd/system/metrics-sourcer.service"
    telegraf_bin = "/usr/sbin/telegraf"
    telegraf_conf_dir = configFolder + "/telegraf_configs/"
    telegraf_agent_conf = telegraf_conf_dir + "telegraf.conf"

    if not os.path.exists(telegraf_conf_dir):
        raise Exception("Telegraf config directory does not exist. Failed to setup telegraf service.")
        return False

    if not os.path.isfile(telegraf_agent_conf):
        raise Exception("Telegraf agent config does not exist. Failed to setup telegraf service.")
        return False
    
    if not os.path.isfile(telegraf_bin):
        raise Exception("Telegraf binary does not exist. Failed to setup telegraf service.")
        return False       

    if os.path.isfile(telegraf_service_path):
        os.system(r"sed -i 's+%TELEGRAF_BIN%+{1}+' {0}".format(telegraf_service_path, telegraf_bin)) 
        os.system(r"sed -i 's+%TELEGRAF_AGENT_CONFIG%+{1}+' {0}".format(telegraf_service_path, telegraf_agent_conf))
        os.system(r"sed -i 's+%TELEGRAF_CONFIG_DIR%+{1}+' {0}".format(telegraf_service_path, telegraf_conf_dir))
    else:
        raise Exception("Telegraf service file does not exist. Failed to setup telegraf service.")
        return False

    return True


def handle_config(data, me_url, mdsd_url, is_lad=False):
    #main method to perfom the task of parsing the config , writing them to disk, setting up and starting telegraf service

    #call the method to first parse the configs
    output, namespaces = parse_config(data, me_url, mdsd_url, is_lad)

    #call the method to write the configs
    write_configs(output)

    # call the method to setup the telegraf service file
    telegraf_setup = setup_telegraf_service()

    # print telegraf_setup
    #start telegraf service if it was set up correctly
    daemon_start = 1
    daemon_reload_status = 1
    if telegraf_setup:
        daemon_reload_status = os.system("sudo systemctl daemon-reload")
        daemon_start = os.system("sudo systemctl start metrics-sourcer")
    
    if daemon_start != 0 or daemon_reload_status != 0:
        return False , []
    
    return True, namespaces