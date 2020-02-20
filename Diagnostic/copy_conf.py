import json

name_map = { 
"percentiowaittime" : {"plugin":"cpu", "field":"usage_iowait"},
"percentusertime" : {"plugin":"cpu", "field":"usage_user"},
"percentnicetime" : {"plugin":"cpu", "field":"usage_nice"},
"percentprocessortime" : {"plugin":"cpu", "field":"usage_active"},
"percentinterrupttime" : {"plugin":"cpu", "field":"usage_irq"},
"percentidletime" : {"plugin":"cpu", "field":"usage_idle"},
"percentprivilegedtime" : {"plugin":"cpu", "field":"usage_system"},

"bytesreceived" : {"plugin":"net", "field":"bytes_recv"},
# "bytestotal" : {"plugin":"net", "field":""},
"bytestransmitted" : {"plugin":"net", "field":"bytes_sent"},
# "totalcollisions" : {"plugin":"net", "field":""},
"totalrxerrors" : {"plugin":"net", "field":"err_in"},
"packetstransmitted" : {"plugin":"net", "field":"packets_sent"},
"packetsreceived" : {"plugin":"net", "field":"packets_recv"},
"totaltxerrors" : {"plugin":"net", "field":"err_out"},

"availablememory" : {"plugin":"mem", "field":"available"},
"percentavailablememory" : {"plugin":"mem", "field":"available_percent"},
"usedmemory" : {"plugin":"mem", "field":"used"},
"percentusedmemory" : {"plugin":"mem", "field":"used_percent"}, 

"availableswap" : {"plugin":"swap", "field":"free"},
# "percentavailableswap" : {"plugin":"swap", "field":"available"}, 
"usedswap" : {"plugin":"swap", "field":"used"}, 
"percentusedswap" : {"plugin":"swap", "field":"used_percent"},

# "pagesreadpersec": {"plugin":"kernel", "field":"disk_pages_in"},
# "pageswrittenpersec" : {"plugin":"kernel", "field":"disk_pages_out"},
# "pagespersec" : {"plugin":"kernel", "field":""},

# "transferspersecond" :
# "usedspace" :
# "percentfreespace" :
# "percentusedspace" :

}

"""
Sample OMI metric json config taken from .settings file
{
    u'counterSpecifier': u'/builtin/network/packetstransmitted', 
    u'counter': u'packetstransmitted', 
    u'class': u'network', 
    u'sampleRate': u'PT15S', 
    u'type': u'builtin', 
    u'annotation': [{
            u'locale': u'en-us', 
            u'displayName': u'Packets sent'
        }],
    u'unit': u'Count'
}
"""
# settings = "/var/lib/waagent/Microsoft.Azure.Diagnostics.LinuxDiagnostic-3.0.125/config/0.settings"
settings = "./test.settings"
data = ""
telegraf_conf = {}
with open(settings, 'r') as f:
    data = json.load(f)
    perfconf = data["runtimeSettings"][0]["handlerSettings"]["publicSettings"]["ladCfg"]["diagnosticMonitorConfiguration"]["performanceCounters"]["performanceCounterConfiguration"]
    for item in perfconf:
        counter = item["counter"]
        if counter in name_map:
            plugin = name_map[counter]["plugin"]
            if plugin not in telegraf_conf:
                telegraf_conf[plugin] = {"fields" : {}, "displayName": item["class"]}
            else:
                telegraf_conf[plugin]["fields"][name_map[counter]["field"]] = {}
                telegraf_conf[plugin]["fields"][name_map[counter]["field"]]["displayName"] = item["annotation"][0]["displayName"]
                telegraf_conf[plugin]["fields"][name_map[counter]["field"]]["interval"] = item["sampleRate"][2:].lower() #Example, converting PT15S tp 15s

print telegraf_conf

"""
Sample converted telegraf conf dict -

{
    'net': {
        'fields': {
            'err_out': {'interval': u'15s', 'displayName': u'Packets sent errors'},
            'packets_sent': {'interval': u'15s', 'displayName': u'Packets sent'}, 
            'err_in': {'interval': u'15s', 'displayName': u'Packets received errors'}, 
            'bytes_sent': {'interval': u'15s', 'displayName': u'Network out guest OS'}, 
            'packets_recv': {'interval': u'5s', 'displayName': u'Packets received'}
        }, 
        'displayName': u'network'
    }, 
    'cpu': {
        'fields': {
            'usage_nice': {'interval': u'15s', 'displayName': u'CPU nice time'}, 
            'usage_user': {'interval': u'15s', 'displayName': u'CPU user time'}, 
            'usage_idle': {'interval': u'15s', 'displayName': u'CPU idle time'}, 
            'usage_active': {'interval': u'15s', 'displayName': u'CPU percentage guest OS'}, 
            'usage_irq': {'interval': u'15s', 'displayName': u'CPU interrupt time'}, 
            'usage_system': {'interval': u'15s', 'displayName': u'CPU privileged time'}
        }, 
        'displayName': u'processor'
    }
}
"""
input_str = ""
rename_str= ""
for plugin in telegraf_conf:
    min_interval = "60s"
    input_str += "[[inputs." + plugin + "]]\n"
    rename_str += "[[processors.rename]]\n"
    rename_str += "\n" + " "*2 + "[[processors.rename.replace]]\n"
    rename_str += " "*4 + "measurement = \"" + str(plugin) +"\"\n" 
    rename_str += " "*4 + "dest = \"" + telegraf_conf[plugin]["displayName"] +"\"\n"
    fields = ""
    for field in telegraf_conf[plugin]["fields"]:
        fields += "\"" + field + "\", "
        
        #Use the shortest interval time for the whole plugin
        new_interval = telegraf_conf[plugin]["fields"][field]["interval"]
        if int(new_interval[:-1]) < int(min_interval[:-1]): 
            min_interval = new_interval
        
        #Add respective rename processor plugin based on the displayname
        rename_str += "\n" + " "*2 + "[[processors.rename.replace]]\n" 
        rename_str += " "*4 + "field = \"" + field + "\"\n"
        rename_str += " "*4 + "dest = \"" + telegraf_conf[plugin]["fields"][field]["displayName"] + "\"\n"


    rename_str += "\n"
    input_str += "\n  fieldpass = ["+fields[:-2]+"]\n"  #Using fields[: -2] here to get rid of the last ", " at the end of the string
    input_str += "  interval = " + "\"" + min_interval + "\"\n"



with open("./telegraf.conf", "w") as f:
    f.write(input_str)
    f.write("\n")
    f.write(rename_str)
    f.write("\n")
"""
Sample telegraf TOML file output

[[inputs.net]]

  fieldpass = ["err_out", "packets_sent", "err_in", "bytes_sent", "packets_recv"]
  interval = "5s"

[[inputs.cpu]]

  fieldpass = ["usage_nice", "usage_user", "usage_idle", "usage_active", "usage_irq", "usage_system"]
  interval = "15s"

"""


 