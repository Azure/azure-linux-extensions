from glob import glob
import sys
from os.path import basename, dirname
import subprocess

#['sdd', 'sdb', 'sde', 'sdc', 'sda']
def physical_drives():
    drive_glob = '/sys/block/sd*/device'
    return [basename(dirname(d)) for d in glob(drive_glob)]

#[('sdd', '4dc5a85f-3da7-4f2c-81a5-22e62142100b', 'crypt', '/datadrive'), ('sdb', 'sdb1', 'part', '/mnt'), ('sdc', 'sdc1', 'part', '/mnt/azure_bek_disk'), ('sda', 'sda2', 'part', '/boot'), ('sda', 'osencrypt', 'crypt', '/')]
def GetMountedDevices():
    finalMountList = []
    for drive in physical_drives():
        lsblk = subprocess.Popen(["lsblk", "-o", "name,type,mountpoint", "-nl", "/dev/" + drive], stdout=subprocess.PIPE)
        out = lsblk.stdout.read()
        if sys.version_info > (3,):
            out = str(out, encoding='utf-8', errors="backslashreplace")
        else:
            out = str(out)
        list = out.strip().split("\n")
        for item in list:
            subList = item.split()
            if len(subList) == 3:    #mountpoint is available
                finalMountList.append((drive, subList[0], subList[1], subList[2]))
    return finalMountList

def GetUsedSize():
    sizeList = []
    sizeList.append(("lun", "device", "fileSystem", "type", "mountPoint", "size", "used", "percent"))
    deviceLunDict = GetDeviceLun()
    mountDetailsList = GetMountedDevices()
    #df command
    df = subprocess.Popen(["df", "-k"], stdout=subprocess.PIPE)
    out = df.stdout.read()
    if sys.version_info > (3,):
        out = str(out, encoding='utf-8', errors="backslashreplace")
    else:
        out = str(out)
    dfList = out.strip().split("\n")
    index=1
    dfListLen = len(dfList)
    while index < dfListLen:
        dfItem = dfList[index]
        fs, size, used, available, percent, mountpoint = dfItem.split()
        for mountDetails in mountDetailsList:
            if mountDetails[3] == mountpoint:
                lun = -1
                if mountDetails[0] in deviceLunDict:
                    lun = deviceLunDict[mountDetails[0]]
                else:
                    print("error. LUN not found")
                sizeList.append((lun, mountDetails[0], fs, mountDetails[2], mountpoint, size, used, percent))
        index = index + 1
    #print(*sizeList, sep="\n")
    return sizeList
    
def GetDeviceLun():
    deviceLunDict = {}
    for drive in physical_drives():
        devicePath = "/sys/block/" + drive + "/device"
        #lrwxrwxrwx 1 root root 0 Oct 28 20:45 /sys/block/sdd/device -> ../../../4:0:0:0
        ls = subprocess.Popen(["ls", "-ld", devicePath], stdout=subprocess.PIPE)
        out = ls.stdout.read()
        if sys.version_info > (3,):
            out = str(out, encoding='utf-8', errors="backslashreplace")
        else:
            out = str(out)
        list = out.strip().split("\n")
        if len(list) != 1:
            print("Error, not expected")
        tempSplit = list[0].split('/')
        deviceDetails = tempSplit[len(tempSplit) - 1].split(':')
        #print(deviceDetails)
        deviceLunDict[drive] = deviceDetails[3]
    return deviceLunDict

if __name__ == '__main__':
    list = GetUsedSize()
    for item in list:
        print(item)





