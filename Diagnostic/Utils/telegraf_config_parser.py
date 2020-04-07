import json
import os
from Utils.telegraf_name_map import name_map


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


def parse_config(data):

    if len(data) == 0:
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
        aggregator_str = ""
        for plugin in telegraf_json[omiclass]:
            config_file = {"filename" : omiclass+".conf"}
            min_interval = "60s"
            input_str += "[[inputs." + plugin + "]]\n"
            # input_str += " "*2 + "name_override = \"" + omiclass + "\"\n"
            rename_str += "\n[[processors.rename]]\n"
            rename_str += " "*2 + "namepass = [\"" + plugin + "\"]\n"

            fields = ""
            ops_fields = ""
            ops = ""
            twiceminperiod = ""
            aggregate = False
            for field in telegraf_json[omiclass][plugin]:
                fields += "\"" + field + "\", "
                
                #Use the shortest interval time for the whole plugin
                new_interval = telegraf_json[omiclass][plugin][field]["interval"]
                if int(new_interval[:-1]) < int(min_interval[:-1]): 
                    min_interval = new_interval
                
                #compute values for aggregator options
                if "op" in telegraf_json[omiclass][plugin][field]:
                    aggregate = True
                    if telegraf_json[omiclass][plugin][field]["op"] not in ops:
                        ops += "\"" +  telegraf_json[omiclass][plugin][field]["op"] + "\", "
                    ops_fields += "\"" +  field + "\", "
                    twiceminperiod = str(int(min_interval[:-1])*2)

                #Add respective rename processor plugin based on the displayname
                rename_str += "\n" + " "*2 + "[[processors.rename.replace]]\n" 
                if "op" in telegraf_json[omiclass][plugin][field]:
                    rename_str += " "*4 + "field = \"" + field + "_rate\"\n"
                    rename_str += " "*4 + "dest = \"" + telegraf_json[omiclass][plugin][field]["displayName"] + "\"\n"
                else:
                    rename_str += " "*4 + "field = \"" + field + "\"\n"
                    rename_str += " "*4 + "dest = \"" + telegraf_json[omiclass][plugin][field]["displayName"] + "\"\n"

            #Add respective operations for aggregators
            if aggregate:
                aggregator_str += "[[aggregators.basicstats]]\n"
                aggregator_str += " "*2 + "period = \"" + twiceminperiod + "s\"\n"
                aggregator_str += " "*2 + "drop_original = false\n"
                aggregator_str += " "*2 + "fieldpass = [" + ops_fields[:-2] + "]\n" #-2 to strip the last comma and space
                aggregator_str += " "*2 + "stats = [" + ops[:-2] + "]\n"  #-2 to strip the last comma and space
                aggregator_str += " "*2 + "rate_period = \"" + twiceminperiod + "s\"\n\n"



            rename_str += "\n"
            input_str += " "*2 + "fieldpass = ["+fields[:-2]+"]\n"  #Using fields[: -2] here to get rid of the last ", " at the end of the string
            input_str += " "*2 + "interval = " + "\"" + min_interval + "\"\n\n"
        
            config_file["data"] = input_str + "\n" + rename_str + "\n" +aggregator_str

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
    logdir = "./LADtelegraf.log"
    handler_env_path = os.path.abspath(os.path.join(os.path.dirname( __file__ ), '..', 'HandlerEnvironment.json'))
    print handler_env_path
    if os.path.exists(handler_env_path):
        with open(handler_env_path, 'r') as handler_env_file:
            handler_env_txt = handler_env_file.read()
        handler_env = json.loads(handler_env_txt)
        if type(handler_env) == list:
            handler_env = handler_env[0]
        print handler_env
        if "handlerEnvironment" in handler_env and "logFolder" in handler_env["handlerEnvironment"]:
                logdir = handler_env["handlerEnvironment"]["logFolder"]
    
    # Telegraf basic agent and output config 
    agentconf = "[agent]\n"
    agentconf += "  interval = \"10s\"\n"
    agentconf += "  round_interval = true"
    agentconf += "  metric_batch_size = 1000\n"
    agentconf += "  metric_buffer_limit = 10000\n"
    agentconf += "  collection_jitter = \"0s\"\n"
    agentconf += "  flush_interval = \"10s\"\n"
    agentconf += "  flush_jitter = \"0s\"\n"
    agentconf += "  logtarget = \"file\"\n"
    agentconf += "  logfile = \"" + logdir + "/telegraf.log\"\n"
    agentconf += "  logfile_rotation_max_size = \"100MB\"\n"
    agentconf += "  logfile_rotation_max_archives = 5\n"                
    agentconf += "\n# Configuration for sending metrics to InfluxD\n"
    agentconf += "[[outputs.influxdb]]\n"

    agent_file = {"filename":"telegraf.conf", "data": agentconf}
    output.append(agent_file)


    return output


