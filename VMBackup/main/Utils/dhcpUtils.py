# Copyright 2014 Microsoft Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Requires Python 2.4+ and Openssl 1.0+

import sys
import platform 
import os 
import subprocess 
import socket
import array
import struct
from uuid import getnode as get_mac
import json

# Utils for sample.py

def make_address(ip_address):
    '''
    Returns the address for scheduled event endpoint from the IP address provided.
    '''
    return 'http://' + ip_address + '/metadata/scheduledevents?api-version=2017-03-01'

def check_ip_address(address, headers):
    '''
    Checks whether the address of the scheduled event endpoint is valid.
    '''
    try:
        response = get_scheduled_events(address, headers)
        return 'Events' in json.loads(response.read().decode('utf-8'))
    except (urllib.error.URLError, UnicodeDecodeError, json.decoder.JSONDecodeError) as _:
        return False

def get_ip_address_reg_env(use_registry):
    '''
    Get the IP address of scheduled event from registry or environment.
    Returns None if IP address is not provided or stored.
    '''
    ip_address = None
    if use_registry and sys.platform == 'win32':
        import winreg as wreg
        # use ScheduledEventsIp in registry if available.
        try:
            key = wreg.OpenKey(wreg.HKEY_LOCAL_MACHINE, "Software\\ScheduledEvents")
            ip_address = wreg.QueryValueEx(key, 'ScheduledEventsIp')[0]
            key.Close()
        except FileNotFoundError:
            pass
    elif sys.platform == 'win32' or "linux" in sys.platform:
        # use SCHEDULEDEVENTSIP in system variables if available.
        ip_address = os.getenv('SCHEDULEDEVENTSIP')

    return ip_address


# Utils for discovery.py

def unpack(buf, offset, range):
    """
    Unpack bytes into python values.
    """
    result = 0
    for i in range:
        result = (result << 8) | str_to_ord(buf[offset + i])
    return result
        
def unpack_big_endian(buf, offset, length):
    """
    Unpack big endian bytes into python values.
    """
    return unpack(buf, offset, list(range(0, length)))

def hex_dump3(buf, offset, length):
    """
    Dump range of buf in formatted hex.
    """
    return ''.join(['%02X' % str_to_ord(char) for char in buf[offset:offset + length]])

def hex_dump2(buf):
    """
    Dump buf in formatted hex.
    """
    return hex_dump3(buf, 0, len(buf))

def hex_dump(buffer, size):
    """
    Return Hex formated dump of a 'buffer' of 'size'.
    """
    if size < 0:
        size = len(buffer)
    result = ""
    for i in range(0, size):
        if (i % 16) == 0:
            result += "%06X: " % i
        byte = buffer[i]
        if type(byte) == str:
            byte = ord(byte.decode('latin1'))
        result += "%02X " % byte
        if (i & 15) == 7:
            result += " "
        if ((i + 1) % 16) == 0 or (i + 1) == size:
            j = i
            while ((j + 1) % 16) != 0:
                result += "   "
                if (j & 7) == 7:
                    result += " "
                j += 1
            result += " "
            for j in range(i - (i % 16), i + 1):
                byte = buffer[j]
                if type(byte) == str:
                    byte = str_to_ord(byte.decode('latin1'))
                k = '.'
                if is_printable(byte):
                    k = chr(byte)
                result += k
            if (i + 1) != size:
                result += "\n"
    return result

def str_to_ord(a):
    """
    Allows indexing into a string or an array of integers transparently.
    Generic utility function.
    """
    if type(a) == type(b'') or type(a) == type(u''):
        a = ord(a)
    return a

def compare_bytes(a, b, start, length):
    for offset in range(start, start + length):
        if str_to_ord(a[offset]) != str_to_ord(b[offset]):
            return False
    return True

def int_to_ip4_addr(a):
    """
    Build DHCP request string.
    """
    return "%u.%u.%u.%u" % ((a >> 24) & 0xFF,
                            (a >> 16) & 0xFF,
                            (a >> 8) & 0xFF,
                            (a) & 0xFF)


def hexstr_to_bytearray(a):
    """
    Return hex string packed into a binary struct.
    """
    b = b""
    for c in range(0, len(a) // 2):
        b += struct.pack("B", int(a[c * 2:c * 2 + 2], 16))
    return b

def is_printable(ch):
    """
    Return True if character is displayable.
    """
    return (is_in_range(ch, str_to_ord('A'), str_to_ord('Z'))
            or is_in_range(ch, str_to_ord('a'), str_to_ord('z'))
            or is_in_range(ch, str_to_ord('0'), str_to_ord('9')))
			
def is_in_range(a, low, high):
    """
    Return True if 'a' in 'low' <= a >= 'high'
    """
    return (a >= low and a <= high)
                                                        
if not hasattr(subprocess,'check_output'): 
    def check_output(*popenargs, **kwargs): 
        r"""Backport from subprocess module from python 2.7""" 
        if 'stdout' in kwargs: 
            raise ValueError('stdout argument not allowed, ' 
                             'it will be overridden.') 
        process = subprocess.Popen(stdout=subprocess.PIPE, *popenargs, **kwargs) 
        output, unused_err = process.communicate() 
        retcode = process.poll() 
        if retcode: 
            cmd = kwargs.get("args") 
            if cmd is None: 
                cmd = popenargs[0] 
            raise subprocess.CalledProcessError(retcode, cmd, output=output) 
        return output 

    # Exception classes used by this module. 
    class CalledProcessError(Exception): 
        def __init__(self, returncode, cmd, output=None): 
            self.returncode = returncode 
            self.cmd = cmd 
            self.output = output 
        def __str__(self): 
            return ("Command '{0}' returned non-zero exit status {1}" "").format(self.cmd, self.returncode) 
    subprocess.check_output=check_output 
    subprocess.CalledProcessError=CalledProcessError 

""" 
Shell command util functions 
""" 
def run(cmd, chk_err=True): 
    """ 
    Calls run_get_output on 'cmd', returning only the return code. 
    If chk_err=True then errors will be reported in the log. 
    If chk_err=False then errors will be suppressed from the log. 
    """ 
    retcode,out=run_get_output(cmd,chk_err) 
    return retcode 
 
def run_get_output(cmd, chk_err=True, log_cmd=False): 
    """ 
    Wrapper for subprocess.check_output. 
    Execute 'cmd'.  Returns return code and STDOUT, trapping expected exceptions. 
    Reports exceptions to Error if chk_err parameter is True 
    """ 
    try: 
        output=subprocess.check_output(cmd,stderr=subprocess.STDOUT,shell=True) 
        output = ustr(output, encoding='utf-8', errors="backslashreplace") 
    except subprocess.CalledProcessError as e : 
        output = ustr(e.output, encoding='utf-8', errors="backslashreplace") 
        return e.returncode, output  
    return 0, output 

# End shell command util functions 

class DefaultOSUtil(object):

    def __init__(self, logger):
        self.logger = logger

    def get_mac_in_bytes(self):
        mac = get_mac()
        machex = '%012x' % mac
        try:
            macb = bytearray.fromhex(machex)
        except TypeError:
            # Work-around for Python 2.6 bug 
            macb = bytearray.fromhex(unicode(machex))
        return macb
        
    def allow_dhcp_broadcast(self):
        #Open DHCP port if iptables is enabled.
        # We supress error logging on error.
        run("iptables -D INPUT -p udp --dport 68 -j ACCEPT",
            chk_err=False)
        run("iptables -I INPUT -p udp --dport 68 -j ACCEPT",
            chk_err=False)

    def get_first_if(self):
        """
        Return the interface name, and ip addr of the
        first active non-loopback interface.
        """
        iface=''
        expected=16 # how many devices should I expect...
        struct_size=40 # for 64bit the size is 40 bytes
        sock = socket.socket(socket.AF_INET,
                             socket.SOCK_DGRAM,
                             socket.IPPROTO_UDP)
        buff=array.array('B', b'\0' * (expected * struct_size))
        param = struct.pack('iL',
                            expected*struct_size,
                            buff.buffer_info()[0])
        ret = fcntl.ioctl(sock.fileno(), 0x8912, param)
        retsize=(struct.unpack('iL', ret)[0])
        if retsize == (expected * struct_size):
            self.logger.log(('SIOCGIFCONF returned more than {0} up network interfaces.').format(expected))
        sock = buff.tostring()
        primary = bytearray(self.get_primary_interface(), encoding='utf-8')
        for i in range(0, struct_size * expected, struct_size):
            iface=sock[i:i+16].split(b'\0', 1)[0]
            if len(iface) == 0 or self.is_loopback(iface) or iface != primary:
                # test the next one
                self.logger.log('interface [{0}] skipped'.format(iface))
                continue
            else:
                # use this one
                self.logger.log('interface [{0}] selected'.format(iface))
                break

        return iface.decode('latin-1'), socket.inet_ntoa(sock[i+20:i+24])

    def get_primary_interface(self):
        """
        Get the name of the primary interface, which is the one with the
        default route attached to it; if there are multiple default routes,
        the primary has the lowest Metric.
        :return: the interface which has the default route
        """
        # from linux/route.h
        RTF_GATEWAY = 0x02
        DEFAULT_DEST = "00000000"

        hdr_iface = "Iface"
        hdr_dest = "Destination"
        hdr_flags = "Flags"
        hdr_metric = "Metric"

        idx_iface = -1
        idx_dest = -1
        idx_flags = -1
        idx_metric = -1
        primary = None
        primary_metric = None

        self.logger.log("examine /proc/net/route for primary interface")
        with open('/proc/net/route') as routing_table:
            idx = 0
            for header in list(filter(lambda h: len(h) > 0, routing_table.readline().strip(" \n").split("\t"))):
                if header == hdr_iface:
                    idx_iface = idx
                elif header == hdr_dest:
                    idx_dest = idx
                elif header == hdr_flags:
                    idx_flags = idx
                elif header == hdr_metric:
                    idx_metric = idx
                idx = idx + 1
            for entry in routing_table.readlines():
                route = entry.strip(" \n").split("\t")
                if route[idx_dest] == DEFAULT_DEST and int(route[idx_flags]) & RTF_GATEWAY == RTF_GATEWAY:
                    metric = int(route[idx_metric])
                    iface = route[idx_iface]
                    if primary is None or metric < primary_metric:
                        primary = iface
                        primary_metric = metric

        if primary is None:
            primary = ''

        self.logger.log('primary interface is [{0}]'.format(primary))
        return primary

    def is_loopback(self, ifname):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        result = fcntl.ioctl(s.fileno(), 0x8913, struct.pack('256s', ifname[:15]))
        flags, = struct.unpack('H', result[16:18])
        isloopback = flags & 8 == 8
        self.logger.log('interface [{0}] has flags [{1}], is loopback [{2}]'.format(ifname, flags, isloopback))
        return isloopback

    def get_ip4_addr(self):
        return self.get_first_if()[1]

    def start_network(self):
        pass

    def route_add(self, net, mask, gateway):
        """
        Add specified route using /sbin/route add -net.
        """
        cmd = ("/sbin/route add -net "
               "{0} netmask {1} gw {2}").format(net, mask, gateway)
        return run(cmd, chk_err=False)
                
"""
Add alies for python2 and python3 libs and fucntions.
"""

if sys.version_info[0]== 3:
    import http.client as httpclient
    from urllib.parse import urlparse

    """Rename Python3 str to ustr"""
    ustr = str

    bytebuffer = memoryview

    read_input = input

elif sys.version_info[0] == 2:
    import httplib as httpclient
    from urlparse import urlparse

    """Rename Python2 unicode to ustr"""
    ustr = unicode

    bytebuffer = buffer

    read_input = raw_input

else:
    raise ImportError("Unknown python version:{0}".format(sys.version_info))
