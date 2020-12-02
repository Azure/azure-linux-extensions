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


# Output of running the script on Windows:
# The scheduled events endpoint IP address will be available as part of the system environment variable.
#
# Output of running the script on Linux:
# The scheduled events endpoint IP address will be available as part of the environment variable for all users.

import os
import socket
import struct
import array
import time
from Utils import dhcpUtils
import sys
if sys.platform == 'win32':
    import _winreg as wreg
from uuid import getnode as get_mac

"""
Defines dhcp exception
"""

class BaseError(Exception):
    """
    Base error class.
    """
    def __init__(self, errno, msg, inner=None):
        msg = u"({0}){1}".format(errno, msg)
        if inner is not None:
            msg = u"{0} \n  inner error: {1}".format(msg, inner)
        super(BaseError, self).__init__(msg)

class DhcpError(BaseError):
    """
    Failed to handle dhcp response
    """
    def __init__(self, msg=None, inner=None):
        super(DhcpError, self).__init__('000006', msg, inner)

class DhcpHandler(object):

    def __init__(self, logger):
        self.osutil = dhcpUtils.DefaultOSUtil(logger)
        self.endpoint = None
        self.gateway = None
        self.routes = None
        self._request_broadcast = False
        self.skip_cache = False
        self.logger = logger

    def getHostEndoint(self):
        self.run()
        return self.endpoint

    def run(self):
        """
        Send dhcp request
        """

        self.send_dhcp_req()

    def _send_dhcp_req(self, request):
        __waiting_duration__ = [0, 10, 30, 60, 60]
        for duration in __waiting_duration__:
            try:
                self.osutil.allow_dhcp_broadcast()
                response = self.socket_send(request)
                self.validate_dhcp_resp(request, response)
                return response
            except DhcpError as e:
                self.logger.log("Failed to send DHCP request: " + str(e))
            time.sleep(duration)
        return None

    def send_dhcp_req(self):
        """
        Build dhcp request with mac addr
        Configure route to allow dhcp traffic
        Stop dhcp service if necessary
        """
        self.logger.log("Sending dhcp request")
        mac_addr = self.osutil.get_mac_in_bytes()


        req = self.build_dhcp_request(mac_addr, self._request_broadcast)

        resp = self._send_dhcp_req(req)

        if resp is None:
            raise DhcpError("Failed to receive dhcp response.")
        self.endpoint, self.gateway, self.routes = self.parse_dhcp_resp(resp)
        self.logger.log('Scheduled Events endpoint IP address:' + self.endpoint)

    def validate_dhcp_resp(self, request, response):
        bytes_recv = len(response)
        if bytes_recv < 0xF6:
            self.logger.log("HandleDhcpResponse: Too few bytes received: " + str(bytes_recv))
            return False

        self.logger.log("BytesReceived:{0}" + str(hex(bytes_recv)))
        #self.logger.log("DHCP response:{0}" + dhcpUtils.hex_dump(response, bytes_recv))

        # check transactionId, cookie, MAC address cookie should never mismatch
        # transactionId and MAC address may mismatch if we see a response
        # meant from another machine
        if not dhcpUtils.compare_bytes(request, response, 0xEC, 4):
            self.logger.log("Cookie not match:\nsend={0},\nreceive={1}".format(dhcpUtils.hex_dump3(request, 0xEC, 4), dhcpUtils.hex_dump3(response, 0xEC, 4)))
            raise DhcpError("Cookie in dhcp respones doesn't match the request")

        if not dhcpUtils.compare_bytes(request, response, 4, 4):
            self.logger.log("TransactionID not match:\nsend={0},\nreceive={1}".format(dhcpUtils.hex_dump3(request, 4, 4), dhcpUtils.hex_dump3(response, 4, 4)))
            raise DhcpError("TransactionID in dhcp respones "
                            "doesn't match the request")

        if not dhcpUtils.compare_bytes(request, response, 0x1C, 6):
            self.logger.log("Mac Address not match:\nsend={0},\nreceive={1}".format(dhcpUtils.hex_dump3(request, 0x1C, 6), dhcpUtils.hex_dump3(response, 0x1C, 6)))
            raise DhcpError("Mac Addr in dhcp respones "
                            "doesn't match the request")


    def parse_route(self, response, option, i, length, bytes_recv):
        # http://msdn.microsoft.com/en-us/library/cc227282%28PROT.10%29.aspx
        self.logger.log("Routes at offset: {0} with length:{1}".format(hex(i), hex(length)))
        routes = []
        if length < 5:
            self.logger.log("Data too small for option:{0}" + str(option))
        j = i + 2
        while j < (i + length + 2):
            mask_len_bits = dhcpUtils.str_to_ord(response[j])
            mask_len_bytes = (((mask_len_bits + 7) & ~7) >> 3)
            mask = 0xFFFFFFFF & (0xFFFFFFFF << (32 - mask_len_bits))
            j += 1
            net = dhcpUtils.unpack_big_endian(response, j, mask_len_bytes)
            net <<= (32 - mask_len_bytes * 8)
            net &= mask
            j += mask_len_bytes
            gateway = dhcpUtils.unpack_big_endian(response, j, 4)
            j += 4
            routes.append((net, mask, gateway))
        if j != (i + length + 2):
            self.logger.log("Unable to parse routes")
        return routes


    def parse_ip_addr(self, response, option, i, length, bytes_recv):
        if i + 5 < bytes_recv:
            if length != 4:
                self.logger.log("Endpoint or Default Gateway not 4 bytes")
                return None
            addr = dhcpUtils.unpack_big_endian(response, i + 2, 4)
            ip_addr = dhcpUtils.int_to_ip4_addr(addr)
            return ip_addr
        else:
            self.logger.log("Data too small for option: " + str(option))
        return None


    def parse_dhcp_resp(self, response):
        """
        Parse DHCP response:
        Returns endpoint server or None on error.
        """
        self.logger.log('Parsing Dhcp response')
        bytes_recv = len(response)
        endpoint = None
        gateway = None
        routes = None

        # Walk all the returned options, parsing out what we need, ignoring the
        # others. We need the custom option 245 to find the the endpoint we talk to
        # options 3 for default gateway and 249 for routes; 255 is end.

        i = 0xF0  # offset to first option
        while i < bytes_recv:
            option = dhcpUtils.str_to_ord(response[i])
            length = 0
            if (i + 1) < bytes_recv:
                length = dhcpUtils.str_to_ord(response[i + 1])
                self.logger.log("DHCP option {0} at offset:{1} with length:{2}".format(hex(option), hex(i), hex(length)))
            if option == 255:
                self.logger.log("DHCP packet ended at offset:{0}".format(hex(i)))
                break
            elif option == 249:
                routes = self.parse_route(response, option, i, length, bytes_recv)
            elif option == 3:
                gateway = self.parse_ip_addr(response, option, i, length, bytes_recv)
                self.logger.log("Default gateway:{0}, at {1}".format(gateway, hex(i)))
            elif option == 245:
                endpoint = self.parse_ip_addr(response, option, i, length, bytes_recv)
                self.logger.log("Azure scheduled events endpoint IP:{0}, at {1}".format(endpoint, hex(i)))
            else:
                self.logger.log("Skipping DHCP option:{0} at {1} with length {2}".format(hex(option), hex(i), hex(length)))
            i += length + 2
        return endpoint, gateway, routes


    def socket_send(self, request):
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM,
                                 socket.IPPROTO_UDP)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("0.0.0.0", 68))
            sock.sendto(request, ("<broadcast>", 67))
            sock.settimeout(10)
            self.logger.log("Send DHCP request: Setting socket.timeout=10, entering recv")
            response = sock.recv(1024)
            return response
        except IOError as e:
            raise DhcpError("{0}".format(e))
        finally:
            if sock is not None:
                sock.close()


    def build_dhcp_request(self, mac_addr, request_broadcast):
        """
        Build DHCP request string.
        """
        #
        # typedef struct _DHCP {
        #  UINT8   Opcode;                    /* op:    BOOTREQUEST or BOOTREPLY */
        #  UINT8   HardwareAddressType;       /* htype: ethernet */
        #  UINT8   HardwareAddressLength;     /* hlen:  6 (48 bit mac address) */
        #  UINT8   Hops;                      /* hops:  0 */
        #  UINT8   TransactionID[4];          /* xid:   random */
        #  UINT8   Seconds[2];                /* secs:  0 */
        #  UINT8   Flags[2];                  /* flags: 0 or 0x8000 for broadcast*/
        #  UINT8   ClientIpAddress[4];        /* ciaddr: 0 */
        #  UINT8   YourIpAddress[4];          /* yiaddr: 0 */
        #  UINT8   ServerIpAddress[4];        /* siaddr: 0 */
        #  UINT8   RelayAgentIpAddress[4];    /* giaddr: 0 */
        #  UINT8   ClientHardwareAddress[16]; /* chaddr: 6 byte eth MAC address */
        #  UINT8   ServerName[64];            /* sname:  0 */
        #  UINT8   BootFileName[128];         /* file:   0  */
        #  UINT8   MagicCookie[4];            /*   99  130   83   99 */
        #                                        /* 0x63 0x82 0x53 0x63 */
        #     /* options -- hard code ours */
        #
        #     UINT8 MessageTypeCode;              /* 53 */
        #     UINT8 MessageTypeLength;            /* 1 */
        #     UINT8 MessageType;                  /* 1 for DISCOVER */
        #     UINT8 End;                          /* 255 */
        # } DHCP;
        #

        # tuple of 244 zeros
        # (struct.pack_into would be good here, but requires Python 2.5)
        request = [0] * 244

        trans_id = self.gen_trans_id()

        # Opcode = 1
        # HardwareAddressType = 1 (ethernet/MAC)
        # HardwareAddressLength = 6 (ethernet/MAC/48 bits)
        for a in range(0, 3):
            request[a] = [1, 1, 6][a]

        # fill in transaction id (random number to ensure response matches request)
        for a in range(0, 4):
            request[4 + a] = dhcpUtils.str_to_ord(trans_id[a])

        self.logger.log("BuildDhcpRequest: transactionId:{0},{1:04x}".format(dhcpUtils.hex_dump2(trans_id), dhcpUtils.unpack_big_endian(request, 4, 4)))

        if request_broadcast:
            # set broadcast flag to true to request the dhcp sever
            # to respond to a boradcast address,
            # this is useful when user dhclient fails.
            request[0x0A] = 0x80;

        # fill in ClientHardwareAddress
        for a in range(0, 6):
            request[0x1C + a] = dhcpUtils.str_to_ord(mac_addr[a])

        # DHCP Magic Cookie: 99, 130, 83, 99
        # MessageTypeCode = 53 DHCP Message Type
        # MessageTypeLength = 1
        # MessageType = DHCPDISCOVER
        # End = 255 DHCP_END
        for a in range(0, 8):
            request[0xEC + a] = [99, 130, 83, 99, 53, 1, 1, 255][a]
        return array.array("B", request)

    def gen_trans_id(self):
        return os.urandom(4)

