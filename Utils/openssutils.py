import struct
import base64


def number_to_bytes(i):
    """
    Pack number into bytes.  Retun as string.
    """
    result = []
    while i:
        result.append(chr(i & 0xFF))
        i >>= 8
    result.reverse()
    return ''.join(result)


def bits_to_string(self, a):
    """
    Return string representation of bits in a.
    """
    index = 7
    s = ""
    c = 0
    for bit in a:
        c = c | (bit << index)
        index = index - 1
        if index == -1:
            s = s + struct.pack('>B', c)
            c = 0
            index = 7
    return s


def openssl_publickey_to_ssh(file):
    """
    Return base-64 encoded key appropriate for ssh.
    """
    from pyasn1.codec.der import decoder as der_decoder
    try:
        f = open(file).read().replace('\n', '').split("KEY-----")[1].split('-')[0]
        k = der_decoder.decode(bits_to_string(der_decoder.decode(base64.b64decode(f))[0][1]))[0]
        n = k[0]
        e = k[1]
        keydata = ""
        keydata += struct.pack('>I', len("ssh-rsa"))
        keydata += "ssh-rsa"
        keydata += struct.pack('>I', len(number_to_bytes(e)))
        keydata += number_to_bytes(e)
        keydata += struct.pack('>I', len(number_to_bytes(n)) + 1)
        keydata += "\0"
        keydata += number_to_bytes(n)
    except Exception as e:
        print("OpensslToSsh: Exception " + str(e))
        return None
    return "ssh-rsa " + base64.b64encode(keydata) + "\n"

