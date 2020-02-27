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
# "bytestotal" : {"plugin":"net", "field":"butes_recv + bytes_sent"}, #Need to calculate sum
"bytestransmitted" : {"plugin":"net", "field":"bytes_sent"},
# "totalcollisions" : {"plugin":"net", "field":"drop_in + drop_out"}, #Need to calculate sum
"totalrxerrors" : {"plugin":"net", "field":"err_in"},
"packetstransmitted" : {"plugin":"net", "field":"packets_sent"},
"packetsreceived" : {"plugin":"net", "field":"packets_recv"},
"totaltxerrors" : {"plugin":"net", "field":"err_out"},

"availablememory" : {"plugin":"mem", "field":"available"},
"percentavailablememory" : {"plugin":"mem", "field":"available_percent"},
"usedmemory" : {"plugin":"mem", "field":"used"},
"percentusedmemory" : {"plugin":"mem", "field":"used_percent"}, 

"availableswap" : {"plugin":"swap", "field":"free"},
# "percentavailableswap" : {"plugin":"swap", "field":"available"}, #Need to calculate percentage
"usedswap" : {"plugin":"swap", "field":"used"}, 
"percentusedswap" : {"plugin":"swap", "field":"used_percent"},

# "pagesreadpersec": {"plugin":"kernel", "field":"disk_pages_in"},
# "pageswrittenpersec" : {"plugin":"kernel", "field":"disk_pages_out"},
# "pagespersec" : {"plugin":"kernel", "field":""},

#OMI Filesystem plugin
"usedspace" : {"plugin":"disk", "field":"used"},
"percentusedspace" : {"plugin":"disk", "field":"used_percent"},
"freespace" : {"plugin":"disk", "field":"free"},
# "percentfreespace" : {"plugin":"disk", "field":"disk_pages_in"}, #Need to calculate percentage
# "percentfreeinodes" : {"plugin":"disk", "field":"inodes_free"}, #Need to calculate percentage
# "percentusedinodes" : {"plugin":"disk", "field":"inodes_used"}, #Need to calculate percentage

# "transferspersecond" : {"plugin":"diskio", "field":"reads + writes"}, #Need to calculate sum
"bytesreadpersecond" : {"plugin":"diskio", "field":"read_bytes", "op":"diff"}, #Need to calculate diff (but each second not each interval)
# "bytespersecond" : {"plugin":"diskio", "field":"read_bytes + write_bytes"}, #Need to calculate diff and then sum
"byteswrittenpersecond" : {"plugin":"diskio", "field":"write_bytes", "op":"diff"}, #Need to calculate diff (but each second not each interval)
"readspersecond" : {"plugin":"diskio", "field":"reads", "op":"diff"}, #Need to calculate diff (but each second not each interval)
"writespersecond" : {"plugin":"diskio", "field":"writes", "op":"diff"}, #Need to calculate diff (but each second not each interval)

#OMI Disk plugin 
# "readbytespersecond" :
# "writebytespersecond" :
# "bytespersecond" :
# "readspersecond" : 
# "writespersecond" :
# "transferspersecond" :
# "averagereadtime" :
# "averagewritetime" : 
# "averagetransfertime" :
# "averagediskqueuelength" : 

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
                if "op" in name_map[counter]:
                    telegraf_conf[plugin]["fields"][name_map[counter]["field"]]["op"] = name_map[counter]["op"]
                # else:
                #     telegraf_conf[plugin]["fields"][name_map[counter]["field"]]["op"] = ""

print telegraf_conf

"""
Sample converted telegraf conf dict -

{
  'mem': {
    'fields': {
      'used_percent': {  'interval': u'15s',  'displayName': u'Memory percentage'},
      'used': {  'interval': u'15s',  'displayName': u'Memory used'},
      'available_percent': {  'interval': u'15s',  'displayName': u'Mem. percent available'}
    },
    'displayName': u'memory'
  },
  'diskio': {
    'fields': {
      'reads': {  'interval': u'15s',  'displayName': u'Disk reads',  'op': 'diff'},
      'writes': {  'interval': u'15s',  'displayName': u'Disk writes',  'op': 'diff'},
      'write_bytes': {  'interval': u'15s',  'displayName': u'Filesystem write bytes/sec',  'op': 'diff'}
    },
    'displayName': u'filesystem'
  },
  'net': {
    'fields': {
      'err_out': {  'interval': u'15s',  'displayName': u'Packets sent errors'},
      'packets_sent': {  'interval': u'15s',  'displayName': u'Packets sent'},
      'err_in': {  'interval': u'15s',  'displayName': u'Packets received errors'},
      'bytes_sent': {  'interval': u'15s',  'displayName': u'Network out guest OS'},
      'packets_recv': {  'interval': u'5s',  'displayName': u'Packets received'}
    },
    'displayName': u'network'
  },
"""

input_str = ""
rename_str = "[[processors.rename]]\n"
aggregator_str = ""
for plugin in telegraf_conf:
    min_interval = "60s"
    input_str += "[[inputs." + plugin + "]]\n"
    rename_str += "\n" + " "*2 + "[[processors.rename.replace]]\n"
    rename_str += " "*4 + "measurement = \"" + str(plugin) +"\"\n" 
    rename_str += " "*4 + "dest = \"" + telegraf_conf[plugin]["displayName"] +"\"\n"
    fields = ""
    ops_fields = ""
    ops = ""
    twiceminperiod = ""
    aggregate = False
    for field in telegraf_conf[plugin]["fields"]:
        fields += "\"" + field + "\", "
        
        #Use the shortest interval time for the whole plugin
        new_interval = telegraf_conf[plugin]["fields"][field]["interval"]
        if int(new_interval[:-1]) < int(min_interval[:-1]): 
            min_interval = new_interval
        
        #compute values for aggregator options
        if "op" in telegraf_conf[plugin]["fields"][field]:
            aggregate = True
            if telegraf_conf[plugin]["fields"][field]["op"] not in ops:
                ops += "\"" +  telegraf_conf[plugin]["fields"][field]["op"] + "\", "
            ops_fields += "\"" +  field + "\", "
            twiceminperiod = str(int(min_interval[:-1])*2)

        #Add respective rename processor plugin based on the displayname
        rename_str += "\n" + " "*2 + "[[processors.rename.replace]]\n" 
        if "op" in telegraf_conf[plugin]["fields"][field]:
            rename_str += " "*4 + "field = \"" + field + "_diff\"\n"
            rename_str += " "*4 + "dest = \"" + telegraf_conf[plugin]["fields"][field]["displayName"] + "\"\n"
        else:
            rename_str += " "*4 + "field = \"" + field + "\"\n"
            rename_str += " "*4 + "dest = \"" + telegraf_conf[plugin]["fields"][field]["displayName"] + "\"\n"

    #Add respective operations for aggregators
    if aggregate:
        aggregator_str += "[[aggregators.basicstats]]\n"
        aggregator_str += " "*2 + "period = \"" + twiceminperiod + "s\"\n"
        aggregator_str += " "*2 + "drop_original = false\n"
        aggregator_str += " "*2 + "fieldpass = [" + ops_fields[:-2] + "]\n" #-2 to strip the last comma and space
        aggregator_str += " "*2 + "stats = [" + ops[:-2] + "]\n\n"  #-2 to strip the last comma and space


    rename_str += "\n"
    input_str += " "*2 + "fieldpass = ["+fields[:-2]+"]\n"  #Using fields[: -2] here to get rid of the last ", " at the end of the string
    input_str += " "*2 + "interval = " + "\"" + min_interval + "\"\n\n"



with open("./telegraf.conf", "w") as f:
    f.write(input_str)
    f.write("\n")
    f.write(rename_str)
    f.write("\n")
    if len(aggregator_str) > 0:
        f.write(aggregator_str)
        f.write("\n")
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
  stats = ["diff"]

"""