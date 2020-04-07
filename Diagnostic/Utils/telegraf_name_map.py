name_map = { 

######These are the counter keys and telegraf plugins for LAD

"processor->CPU IO wait time" : {"plugin":"cpu", "field":"usage_iowait"},
"processor->CPU user time" : {"plugin":"cpu", "field":"usage_user"},
"processor->CPU nice time" : {"plugin":"cpu", "field":"usage_nice"},
"processor->CPU percentage guest OS" : {"plugin":"cpu", "field":"usage_active"},
"processor->CPU interrupt time" : {"plugin":"cpu", "field":"usage_irq"},
"processor->CPU idle time" : {"plugin":"cpu", "field":"usage_idle"},
"processor->CPU privileged time" : {"plugin":"cpu", "field":"usage_system"},

"network->Network in guest OS" : {"plugin":"net", "field":"bytes_recv"},
"network->Network total bytes" : {"plugin":"net", "field":"bytes_total"}, #Need to calculate sum
"network->Network out guest OS" : {"plugin":"net", "field":"bytes_sent"},
"network->Network collisions" : {"plugin":"net", "field":"drop_total"}, #Need to calculate sum
"network->Packets received errors" : {"plugin":"net", "field":"err_in"},
"network->Packets sent" : {"plugin":"net", "field":"packets_sent"},
"network->Packets received" : {"plugin":"net", "field":"packets_recv"},
"network->Packets sent errors" : {"plugin":"net", "field":"err_out"},

"memory->Memory available" : {"plugin":"mem", "field":"available"},
"memory->Mem. percent available" : {"plugin":"mem", "field":"available_percent"},
"memory->Memory used" : {"plugin":"mem", "field":"used"},
"memory->Memory percentage" : {"plugin":"mem", "field":"used_percent"}, 

"memory->Swap available" : {"plugin":"swap", "field":"free"},
"memory->Swap percent available" : {"plugin":"swap", "field":"free_percent"}, #Need to calculate percentage
"memory->Swap used" : {"plugin":"swap", "field":"used"}, 
"memory->Swap percent used" : {"plugin":"swap", "field":"used_percent"},

"memory->Page reads": {"plugin":"kernel_vmstat", "field":"pgpgin", "op":"rate"},
"memory->Page writes" : {"plugin":"kernel_vmstat", "field":"pgpgout", "op":"rate"},
# "memory->Pages" : {"plugin":"kernel", "field":""},

#OMI Filesystem plugin
"filesystem->Filesystem used space" : {"plugin":"disk", "field":"used"},
"filesystem->Filesystem % used space" : {"plugin":"disk", "field":"used_percent"},
"filesystem->Filesystem free space" : {"plugin":"disk", "field":"free"},
"filesystem->Filesystem % free space" : {"plugin":"disk", "field":"free_percent"}, #Need to calculate percentage
"filesystem->Filesystem % free inodes" : {"plugin":"disk", "field":"inodes_free_percent"}, #Need to calculate percentage
"filesystem->Filesystem % used inodes" : {"plugin":"disk", "field":"inodes_used_percent"}, #Need to calculate percentage

# # "filesystem->Filesystem transfers/sec" : {"plugin":"diskio", "field":"reads + writes"}, #Need to calculate sum
"filesystem->Filesystem read bytes/sec" : {"plugin":"diskio", "field":"read_bytes", "op":"rate"}, #Need to calculate rate (but each second not each interval)
# # "filesystem->Filesystem bytes/sec" : {"plugin":"diskio", "field":"read_bytes + write_bytes"}, #Need to calculate rate and then sum
"filesystem->Filesystem write bytes/sec" : {"plugin":"diskio", "field":"write_bytes", "op":"rate"}, #Need to calculate rate (but each second not each interval)
"filesystem->Filesystem reads/sec" : {"plugin":"diskio", "field":"reads", "op":"rate"}, #Need to calculate rate (but each second not each interval)
"filesystem->Filesystem writes/sec" : {"plugin":"diskio", "field":"writes", "op":"rate"}, #Need to calculate rate (but each second not each interval)

# #OMI Disk plugin 
"disk->Disk read guest OS" : {"plugin":"diskio", "field":"read_bytes", "op":"rate"},
"disk->Disk write guest OS" : {"plugin":"diskio", "field":"write_bytes", "op":"rate"},
# # "disk->Disk total bytes" : {"plugin":"diskio", "field":"read_bytes + write_bytes"},
"disk->Disk reads" : {"plugin":"diskio", "field":"reads", "op":"rate"}, #Need to calculate rate (but each second not each interval)
"disk->Disk writes" : {"plugin":"diskio", "field":"writes", "op":"rate"},
# # "disk->Disk transfers" :
"disk->Disk read time" : {"plugin":"diskio", "field":"read_time"},
"disk->Disk write time" : {"plugin":"diskio", "field":"write_time"},
"disk->Disk transfer time" : {"plugin":"diskio", "field":"io_time"},
"disk->Disk queue length" : {"plugin":"diskio", "field":"iops_in_progress", "op":"mean"}


##### These are the counter keys and telegraf plugins for Azure Monitor Agent

}
