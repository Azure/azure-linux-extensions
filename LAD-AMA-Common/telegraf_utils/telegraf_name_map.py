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

name_map = {

######These are the counter keys and telegraf plugins for LAD/AMA

"processor->cpu io wait time" : {"plugin":"cpu", "field":"usage_iowait", "ladtablekey":"/builtin/processor/percentiowaittime"},
"processor->cpu user time" : {"plugin":"cpu", "field":"usage_user", "ladtablekey":"/builtin/processor/percentusertime"},
"processor->cpu nice time" : {"plugin":"cpu", "field":"usage_nice", "ladtablekey":"/builtin/processor/percentnicetime"},
"processor->cpu percentage guest os" : {"plugin":"cpu", "field":"usage_active", "ladtablekey":"/builtin/processor/percentprocessortime"},
"processor->cpu interrupt time" : {"plugin":"cpu", "field":"usage_irq", "ladtablekey":"/builtin/processor/percentinterrupttime"},
"processor->cpu idle time" : {"plugin":"cpu", "field":"usage_idle", "ladtablekey":"/builtin/processor/percentidletime"},
"processor->cpu privileged time" : {"plugin":"cpu", "field":"usage_system", "ladtablekey":"/builtin/processor/percentprivilegedtime"},

"% IO Wait Time" : {"plugin":"cpu", "field":"usage_iowait", "module":"processor"},
"% User Time" : {"plugin":"cpu", "field":"usage_user", "module":"processor"},
"% Nice Time" : {"plugin":"cpu", "field":"usage_nice", "module":"processor"},
"% Processor Time" : {"plugin":"cpu", "field":"usage_active", "module":"processor"},
"% Interrupt Time" : {"plugin":"cpu", "field":"usage_irq", "module":"processor"},
"% Idle Time" : {"plugin":"cpu", "field":"usage_idle", "module":"processor"},
"% Privileged Time" : {"plugin":"cpu", "field":"usage_system", "module":"processor"},

# VM Insights
# 8 slashes because this goes from JSON -> Python -> Telegraf config -> Go -> C++ and each level does an escape
"Processor\\UtilizationPercentage" : {"plugin":"cpu_vmi", "field":"Processor\\\\\\\\UtilizationPercentage", "module":"processor"},
"Computer\\Heartbeat" : {"plugin":"cpu_heartbeat_vmi", "field":"Computer\\\\\\\\Heartbeat", "module":"processor"},

"network->network in guest os" : {"plugin":"net", "field":"bytes_recv", "ladtablekey":"/builtin/network/bytesreceived"},
"network->network total bytes" : {"plugin":"net", "field":"bytes_total", "ladtablekey":"/builtin/network/bytestotal"}, #Need to calculate sum
"network->network out guest os" : {"plugin":"net", "field":"bytes_sent", "ladtablekey":"/builtin/network/bytestransmitted"},
"network->network collisions" : {"plugin":"net", "field":"drop_total", "ladtablekey":"/builtin/network/totalcollisions"}, #Need to calculate sum
"network->packets received errors" : {"plugin":"net", "field":"err_in", "ladtablekey":"/builtin/network/totalrxerrors"},
"network->packets sent" : {"plugin":"net", "field":"packets_sent", "ladtablekey":"/builtin/network/packetstransmitted"},
"network->packets received" : {"plugin":"net", "field":"packets_recv", "ladtablekey":"/builtin/network/packetsreceived"},
"network->packets sent errors" : {"plugin":"net", "field":"err_out", "ladtablekey":"/builtin/network/totaltxerrors"},

"Total Bytes Received" : {"plugin":"net", "field":"bytes_recv", "module":"network"},
"Total Bytes" : {"plugin":"net", "field":"bytes_total", "module":"network"}, #Need to calculate sum
"Total Bytes Transmitted" : {"plugin":"net", "field":"bytes_sent", "module":"network"},
"Total Collisions" : {"plugin":"net", "field":"drop_total", "module":"network"}, #Need to calculate sum
"Total Rx Errors" : {"plugin":"net", "field":"err_in", "module":"network"},
"Total Packets Transmitted" : {"plugin":"net", "field":"packets_sent", "module":"network"},
"Total Packets Received" : {"plugin":"net", "field":"packets_recv", "module":"network"},
"Total Tx Errors" : {"plugin":"net", "field":"err_out", "module":"network"},

# VM Insights
# "Network\ReadBytesPerSecond", "Network\WriteBytesPerSecond"
# 8 slashes because this goes from JSON -> Python -> Telegraf config -> Go -> C++ and each level does an escape
"Network\\ReadBytesPerSecond" : {"plugin":"net_recv_vmi", "field":"Network\\\\\\\\ReadBytesPerSecond", "op":"rate", "module":"network"},
"Network\\WriteBytesPerSecond" : {"plugin":"net_sent_vmi", "field":"Network\\\\\\\\WriteBytesPerSecond", "op":"rate", "module":"network"},

"memory->memory available" : {"plugin":"mem", "field":"available", "ladtablekey":"/builtin/memory/availablememory"},
"memory->mem. percent available" : {"plugin":"mem", "field":"available_percent", "ladtablekey":"/builtin/memory/percentavailablememory"},
"memory->memory used" : {"plugin":"mem", "field":"used", "ladtablekey":"/builtin/memory/usedmemory"},
"memory->memory percentage" : {"plugin":"mem", "field":"used_percent", "ladtablekey":"/builtin/memory/percentusedmemory"},

"memory->swap available" : {"plugin":"swap", "field":"free", "ladtablekey":"/builtin/memory/availableswap"},
"memory->swap percent available" : {"plugin":"swap", "field":"free_percent", "ladtablekey":"/builtin/memory/percentavailableswap"}, #Need to calculate percentage
"memory->swap used" : {"plugin":"swap", "field":"used", "ladtablekey":"/builtin/memory/usedswap"},
"memory->swap percent used" : {"plugin":"swap", "field":"used_percent", "ladtablekey":"/builtin/memory/percentusedswap"},

"memory->page reads": {"plugin":"kernel_vmstat", "field":"pgpgin", "op":"rate", "ladtablekey":"/builtin/memory/pagesreadpersec"},
"memory->page writes" : {"plugin":"kernel_vmstat", "field":"pgpgout", "op":"rate", "ladtablekey":"/builtin/memory/pageswrittenpersec"},
"memory->pages" : {"plugin":"kernel_vmstat", "field":"total_pages", "op":"rate", "ladtablekey":"/builtin/memory/pagespersec"},

"Available MBytes Memory" : {"plugin":"mem", "field":"available", "module":"memory"},
"% Available Memory" : {"plugin":"mem", "field":"available_percent", "module":"memory"},
"Used Memory MBytes" : {"plugin":"mem", "field":"used", "module":"memory"},
"% Used Memory" : {"plugin":"mem", "field":"used_percent", "module":"memory"},

"Available MBytes Swap" : {"plugin":"swap", "field":"free", "module":"memory"},
"% Available Swap Space" : {"plugin":"swap", "field":"free_percent", "module":"memory"}, #Need to calculate percentage
"Used MBytes Swap Space" : {"plugin":"swap", "field":"used", "module":"memory"},
"% Used Swap Space" : {"plugin":"swap", "field":"used_percent", "module":"memory"},

"Page Reads/sec": {"plugin":"kernel_vmstat", "field":"pgpgin", "op":"rate", "module":"memory"},
"Page Writes/sec" : {"plugin":"kernel_vmstat", "field":"pgpgout", "op":"rate", "module":"memory"},
"Pages/sec" : {"plugin":"kernel_vmstat", "field":"total_pages", "op":"rate", "module":"memory"},

# VM Insights
# 8 slashes because this goes from JSON -> Python -> Telegraf config -> Go -> C++ and each level does an escape
"Memory\\AvailableMB" : {"plugin":"mem_vmi", "field":"Memory\\\\\\\\AvailableMB", "module":"memory"},
"Memory\\AvailablePercentage" : {"plugin":"mem_vmi", "field":"Memory\\\\\\\\AvailablePercentage", "module":"memory"},

#OMI Filesystem plugin
"filesystem->filesystem used space" : {"plugin":"disk", "field":"used", "ladtablekey":"/builtin/filesystem/usedspace"},
"filesystem->filesystem % used space" : {"plugin":"disk", "field":"used_percent", "ladtablekey":"/builtin/filesystem/percentusedspace"},
"filesystem->filesystem free space" : {"plugin":"disk", "field":"free", "ladtablekey":"/builtin/filesystem/freespace"},
"filesystem->filesystem % free space" : {"plugin":"disk", "field":"free_percent", "ladtablekey":"/builtin/filesystem/percentfreespace"}, #Need to calculate percentage
"filesystem->filesystem % free inodes" : {"plugin":"disk", "field":"inodes_free_percent", "ladtablekey":"/builtin/filesystem/percentfreeinodes"}, #Need to calculate percentage
"filesystem->filesystem % used inodes" : {"plugin":"disk", "field":"inodes_used_percent", "ladtablekey":"/builtin/filesystem/percentusedinodes"}, #Need to calculate percentage

"filesystem->filesystem transfers/sec" : {"plugin":"diskio", "field":"total_transfers_filesystem", "op":"rate", "ladtablekey":"/builtin/filesystem/transferspersecond"}, #Need to calculate sum
"filesystem->filesystem read bytes/sec" : {"plugin":"diskio", "field":"read_bytes_filesystem", "op":"rate", "ladtablekey":"/builtin/filesystem/bytesreadpersecond"}, #Need to calculate rate (but each second not each interval)
"filesystem->filesystem bytes/sec" : {"plugin":"diskio", "field":"total_bytes_filesystem", "op":"rate", "ladtablekey":"/builtin/filesystem/bytespersecond"}, #Need to calculate rate and then sum
"filesystem->filesystem write bytes/sec" : {"plugin":"diskio", "field":"write_bytes_filesystem", "op":"rate", "ladtablekey":"/builtin/filesystem/byteswrittenpersecond"}, #Need to calculate rate (but each second not each interval)
"filesystem->filesystem reads/sec" : {"plugin":"diskio", "field":"reads_filesystem", "op":"rate", "ladtablekey":"/builtin/filesystem/readspersecond"}, #Need to calculate rate (but each second not each interval)
"filesystem->filesystem writes/sec" : {"plugin":"diskio", "field":"writes_filesystem", "op":"rate", "ladtablekey":"/builtin/filesystem/writespersecond"}, #Need to calculate rate (but each second not each interval)

"% Used Space" : {"plugin":"disk", "field":"used_percent", "module":"filesystem"},
"Free Megabytes" : {"plugin":"disk", "field":"free", "module":"filesystem"},
"% Free Space" : {"plugin":"disk", "field":"free_percent", "module":"filesystem"}, #Need to calculate percentage
"% Free Inodes" : {"plugin":"disk", "field":"inodes_free_percent", "module":"filesystem"}, #Need to calculate percentage
"% Used Inodes" : {"plugin":"disk", "field":"inodes_used_percent", "module":"filesystem"}, #Need to calculate percentage

"Disk Transfers/sec" : {"plugin":"diskio", "field":"total_transfers", "op":"rate", "module":"filesystem"}, #Need to calculate sum
"Disk Read Bytes/sec" : {"plugin":"diskio", "field":"read_bytes", "op":"rate", "module":"filesystem"}, #Need to calculate rate (but each second not each interval)
"Logical Disk Bytes/sec" : {"plugin":"diskio", "field":"total_bytes", "op":"rate", "module":"filesystem"}, #Need to calculate rate and then sum
"Disk Write Bytes/sec" : {"plugin":"diskio", "field":"write_bytes", "op":"rate", "module":"filesystem"}, #Need to calculate rate (but each second not each interval)
"Disk Reads/sec" : {"plugin":"diskio", "field":"reads", "op":"rate", "module":"filesystem"}, #Need to calculate rate (but each second not each interval)
"Disk Writes/sec" : {"plugin":"diskio", "field":"writes", "op":"rate", "module":"filesystem"}, #Need to calculate rate (but each second not each interval)

# VM Insights
# 8 slashes because this goes from JSON -> Python -> Telegraf config -> Go -> C++ and each level does an escape
"LogicalDisk\\FreeSpaceMB" : {"plugin":"disk_vmi", "field":"LogicalDisk\\\\\\\\FreeSpaceMB", "module":"filesystem"},
"LogicalDisk\\FreeSpacePercentage" : {"plugin":"disk_vmi", "field":"LogicalDisk\\\\\\\\FreeSpacePercentage", "module":"filesystem"}, #Need to calculate percentage
"LogicalDisk\\Status" : {"plugin":"disk_vmi", "field":"LogicalDisk\\\\\\\\Status", "module":"filesystem"}, #Need to calculate percentage

#"LogicalDisk\BytesPerSecond", "LogicalDisk\ReadBytesPerSecond", "LogicalDisk\ReadsPerSecond",  "LogicalDisk\WriteBytesPerSecond", "LogicalDisk\WritesPerSecond", "LogicalDisk\TransfersPerSecond", 

"LogicalDisk\\TransfersPerSecond" : {"plugin":"diskio_vmi", "field":"LogicalDisk\\\\\\\\TransfersPerSecond", "op":"rate", "module":"filesystem"}, #Need to calculate sum
"LogicalDisk\\ReadBytesPerSecond" : {"plugin":"diskio_vmi", "field":"LogicalDisk\\\\\\\\ReadBytesPerSecond", "op":"rate", "module":"filesystem"}, #Need to calculate rate (but each second not each interval)
"LogicalDisk\\BytesPerSecond" : {"plugin":"diskio_vmi", "field":"LogicalDisk\\\\\\\\BytesPerSecond", "op":"rate", "module":"filesystem"}, #Need to calculate rate and then sum
"LogicalDisk\\WriteBytesPerSecond" : {"plugin":"diskio_vmi", "field":"LogicalDisk\\\\\\\\WriteBytesPerSecond", "op":"rate", "module":"filesystem"}, #Need to calculate rate (but each second not each interval)
"LogicalDisk\\ReadsPerSecond" : {"plugin":"diskio_vmi", "field":"LogicalDisk\\\\\\\\ReadsPerSecond", "op":"rate", "module":"filesystem"}, #Need to calculate rate (but each second not each interval)
"LogicalDisk\\WritesPerSecond" : {"plugin":"diskio_vmi", "field":"LogicalDisk\\\\\\\\WritesPerSecond", "op":"rate", "module":"filesystem"}, #Need to calculate rate (but each second not each interval)

# #OMI Disk plugin
"disk->disk read guest os" : {"plugin":"diskio", "field":"read_bytes", "op":"rate", "ladtablekey":"/builtin/disk/readbytespersecond"},
"disk->disk write guest os" : {"plugin":"diskio", "field":"write_bytes", "op":"rate", "ladtablekey":"/builtin/disk/writebytespersecond"},
"disk->disk total bytes" : {"plugin":"diskio", "field":"total_bytes", "op":"rate", "ladtablekey":"/builtin/disk/bytespersecond"},
"disk->disk reads" : {"plugin":"diskio", "field":"reads", "op":"rate", "ladtablekey":"/builtin/disk/readspersecond"}, #Need to calculate rate (but each second not each interval)
"disk->disk writes" : {"plugin":"diskio", "field":"writes", "op":"rate", "ladtablekey":"/builtin/disk/writespersecond"},
"disk->disk transfers" : {"plugin":"diskio", "field":"total_transfers", "op":"rate", "ladtablekey":"/builtin/disk/transferspersecond"},
"disk->disk read time" : {"plugin":"diskio", "field":"read_time", "op":"rate", "ladtablekey":"/builtin/disk/averagereadtime"},
"disk->disk write time" : {"plugin":"diskio", "field":"write_time", "op":"rate", "ladtablekey":"/builtin/disk/averagewritetime"},
"disk->disk transfer time" : {"plugin":"diskio", "field":"io_time", "op":"rate", "ladtablekey":"/builtin/disk/averagetransfertime"},
"disk->disk queue length" : {"plugin":"diskio", "field":"iops_in_progress", "ladtablekey":"/builtin/disk/averagediskqueuelength"}

##### These are the counter keys and telegraf plugins for Azure Monitor Agent

}
