name_map = {

######These are the counter keys and telegraf plugins for LAD/AMA

"processor->CPU IO wait time" : {"plugin":"cpu", "field":"usage_iowait", "ladtablekey":"/builtin/processor/percentiowaittime"},
"processor->CPU user time" : {"plugin":"cpu", "field":"usage_user", "ladtablekey":"/builtin/processor/percentusertime"},
"processor->CPU nice time" : {"plugin":"cpu", "field":"usage_nice", "ladtablekey":"/builtin/processor/percentnicetime"},
"processor->CPU percentage guest OS" : {"plugin":"cpu", "field":"usage_active", "ladtablekey":"/builtin/processor/percentprocessortime"},
"processor->CPU interrupt time" : {"plugin":"cpu", "field":"usage_irq", "ladtablekey":"/builtin/processor/percentinterrupttime"},
"processor->CPU idle time" : {"plugin":"cpu", "field":"usage_idle", "ladtablekey":"/builtin/processor/percentidletime"},
"processor->CPU privileged time" : {"plugin":"cpu", "field":"usage_system", "ladtablekey":"/builtin/processor/percentprivilegedtime"},

"% IO Wait Time" : {"plugin":"cpu", "field":"usage_iowait", "ladtablekey":"% IO Wait Time", "module":"processor"},
"% User Time" : {"plugin":"cpu", "field":"usage_user", "ladtablekey":"% User Time", "module":"processor"},
"% Nice Time" : {"plugin":"cpu", "field":"usage_nice", "ladtablekey":"% Nice Time", "module":"processor"},
"% Processor Time" : {"plugin":"cpu", "field":"usage_active", "ladtablekey":"% Processor Time", "module":"processor"},
"% Interrupt Time" : {"plugin":"cpu", "field":"usage_irq", "ladtablekey":"% Interrupt Time", "module":"processor"},
"% Idle Time" : {"plugin":"cpu", "field":"usage_idle", "ladtablekey":"% Idle Time", "module":"processor"},
"% Privileged Time" : {"plugin":"cpu", "field":"usage_system", "ladtablekey":"% Privileged Time", "module":"processor"},

  
"network->Network in guest OS" : {"plugin":"net", "field":"bytes_recv", "ladtablekey":"/builtin/network/bytesreceived"},
"network->Network total bytes" : {"plugin":"net", "field":"bytes_total", "ladtablekey":"/builtin/network/bytestotal"}, #Need to calculate sum
"network->Network out guest OS" : {"plugin":"net", "field":"bytes_sent", "ladtablekey":"/builtin/network/bytestransmitted"},
"network->Network collisions" : {"plugin":"net", "field":"drop_total", "ladtablekey":"/builtin/network/totalcollisions"}, #Need to calculate sum
"network->Packets received errors" : {"plugin":"net", "field":"err_in", "ladtablekey":"/builtin/network/totalrxerrors"},
"network->Packets sent" : {"plugin":"net", "field":"packets_sent", "ladtablekey":"/builtin/network/packetstransmitted"},
"network->Packets received" : {"plugin":"net", "field":"packets_recv", "ladtablekey":"/builtin/network/packetsreceived"},
"network->Packets sent errors" : {"plugin":"net", "field":"err_out", "ladtablekey":"/builtin/network/totaltxerrors"},

"memory->Memory available" : {"plugin":"mem", "field":"available", "ladtablekey":"/builtin/memory/availablememory"},
"memory->Mem. percent available" : {"plugin":"mem", "field":"available_percent", "ladtablekey":"/builtin/memory/percentavailablememory"},
"memory->Memory used" : {"plugin":"mem", "field":"used", "ladtablekey":"/builtin/memory/usedmemory"},
"memory->Memory percentage" : {"plugin":"mem", "field":"used_percent", "ladtablekey":"/builtin/memory/percentusedmemory"},

"memory->Swap available" : {"plugin":"swap", "field":"free", "ladtablekey":"/builtin/memory/availableswap"},
"memory->Swap percent available" : {"plugin":"swap", "field":"free_percent", "ladtablekey":"/builtin/memory/percentavailableswap"}, #Need to calculate percentage
"memory->Swap used" : {"plugin":"swap", "field":"used", "ladtablekey":"/builtin/memory/usedswap"},
"memory->Swap percent used" : {"plugin":"swap", "field":"used_percent", "ladtablekey":"/builtin/memory/percentusedswap"},

"memory->Page reads": {"plugin":"kernel_vmstat", "field":"pgpgin", "op":"rate", "ladtablekey":"/builtin/memory/pagesreadpersec"},
"memory->Page writes" : {"plugin":"kernel_vmstat", "field":"pgpgout", "op":"rate", "ladtablekey":"/builtin/memory/pageswrittenpersec"},
"memory->Pages" : {"plugin":"kernel_vmstat", "field":"total_pages", "op":"rate", "ladtablekey":"/builtin/memory/pagespersec"},

#OMI Filesystem plugin
"filesystem->Filesystem used space" : {"plugin":"disk", "field":"used", "ladtablekey":"/builtin/filesystem/usedspace"},
"filesystem->Filesystem % used space" : {"plugin":"disk", "field":"used_percent", "ladtablekey":"/builtin/filesystem/percentusedspace"},
"filesystem->Filesystem free space" : {"plugin":"disk", "field":"free", "ladtablekey":"/builtin/filesystem/freespace"},
"filesystem->Filesystem % free space" : {"plugin":"disk", "field":"free_percent", "ladtablekey":"/builtin/filesystem/percentfreespace"}, #Need to calculate percentage
"filesystem->Filesystem % free inodes" : {"plugin":"disk", "field":"inodes_free_percent", "ladtablekey":"/builtin/filesystem/percentfreeinodes"}, #Need to calculate percentage
"filesystem->Filesystem % used inodes" : {"plugin":"disk", "field":"inodes_used_percent", "ladtablekey":"/builtin/filesystem/percentusedinodes"}, #Need to calculate percentage

"filesystem->Filesystem transfers/sec" : {"plugin":"diskio", "field":"total_transfers_filesystem", "op":"rate", "ladtablekey":"/builtin/filesystem/transferspersecond"}, #Need to calculate sum
"filesystem->Filesystem read bytes/sec" : {"plugin":"diskio", "field":"read_bytes_filesystem", "op":"rate", "ladtablekey":"/builtin/filesystem/bytesreadpersecond"}, #Need to calculate rate (but each second not each interval)
"filesystem->Filesystem bytes/sec" : {"plugin":"diskio", "field":"total_bytes_filesystem", "op":"rate", "ladtablekey":"/builtin/filesystem/bytespersecond"}, #Need to calculate rate and then sum
"filesystem->Filesystem write bytes/sec" : {"plugin":"diskio", "field":"write_bytes_filesystem", "op":"rate", "ladtablekey":"/builtin/filesystem/byteswrittenpersecond"}, #Need to calculate rate (but each second not each interval)
"filesystem->Filesystem reads/sec" : {"plugin":"diskio", "field":"reads_filesystem", "op":"rate", "ladtablekey":"/builtin/filesystem/readspersecond"}, #Need to calculate rate (but each second not each interval)
"filesystem->Filesystem writes/sec" : {"plugin":"diskio", "field":"writes_filesystem", "op":"rate", "ladtablekey":"/builtin/filesystem/writespersecond"}, #Need to calculate rate (but each second not each interval)

# #OMI Disk plugin
"disk->Disk read guest OS" : {"plugin":"diskio", "field":"read_bytes", "op":"rate", "ladtablekey":"/builtin/disk/readbytespersecond"},
"disk->Disk write guest OS" : {"plugin":"diskio", "field":"write_bytes", "op":"rate", "ladtablekey":"/builtin/disk/writebytespersecond"},
"disk->Disk total bytes" : {"plugin":"diskio", "field":"total_bytes", "op":"rate", "ladtablekey":"/builtin/disk/bytespersecond"},
"disk->Disk reads" : {"plugin":"diskio", "field":"reads", "op":"rate", "ladtablekey":"/builtin/disk/readspersecond"}, #Need to calculate rate (but each second not each interval)
"disk->Disk writes" : {"plugin":"diskio", "field":"writes", "op":"rate", "ladtablekey":"/builtin/disk/writespersecond"},
"disk->Disk transfers" : {"plugin":"diskio", "field":"total_transfers", "op":"rate", "ladtablekey":"/builtin/disk/transferspersecond"},
"disk->Disk read time" : {"plugin":"diskio", "field":"read_time", "ladtablekey":"/builtin/disk/averagereadtime"},
"disk->Disk write time" : {"plugin":"diskio", "field":"write_time", "ladtablekey":"/builtin/disk/averagewritetime"},
"disk->Disk transfer time" : {"plugin":"diskio", "field":"io_time", "ladtablekey":"/builtin/disk/averagetransfertime"},
"disk->Disk queue length" : {"plugin":"diskio", "field":"iops_in_progress", "ladtablekey":"/builtin/disk/averagediskqueuelength"}


##### These are the counter keys and telegraf plugins for Azure Monitor Agent

}
