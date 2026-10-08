"""
Fallback crypt implementation using ctypes for Python 3.13+.

This module provides crypt.crypt() functionality without requiring pip install
by directly calling the system's libxcrypt/libcrypt library via ctypes.

Usage:
    # In your code, use this import pattern:
    try:
        import crypt
    except ImportError:
        try:
            import crypt_r as crypt
        except ImportError:
            from Common import crypt_fallback as crypt
"""

import ctypes
import ctypes.util
import string
import random

__all__ = ['crypt', 'mksalt', 'METHOD_SHA512', 'METHOD_SHA256', 'methods']


# Try to load libcrypt
_libcrypt = None
_libcrypt_path = ctypes.util.find_library("crypt")

if _libcrypt_path:
    try:
        _libcrypt = ctypes.CDLL(_libcrypt_path)
        _libcrypt.crypt.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        _libcrypt.crypt.restype = ctypes.c_char_p
    except (OSError, AttributeError):
        _libcrypt = None


class _Method:
    """Class representing a crypt method."""
    def __init__(self, name, ident, salt_chars, total_size):
        self.name = name
        self.ident = ident
        self.salt_chars = salt_chars
        self.total_size = total_size
    
    def __repr__(self):
        return '<crypt.METHOD_{0}>'.format(self.name)


# Define standard methods
METHOD_SHA512 = _Method('SHA512', '6', 16, 106)
METHOD_SHA256 = _Method('SHA256', '5', 16, 63)
METHOD_MD5 = _Method('MD5', '1', 8, 34)
METHOD_CRYPT = _Method('CRYPT', None, 2, 13)

methods = [METHOD_SHA512, METHOD_SHA256, METHOD_MD5, METHOD_CRYPT]


def mksalt(method=None, rounds=None):
    """Generate a salt for the specified method.
    
    If not specified, the strongest available method (SHA512) will be used.
    """
    if method is None:
        method = METHOD_SHA512
    
    saltchars = string.ascii_letters + string.digits + './'
    
    if method.ident:
        salt = '${0}$'.format(method.ident)
        if method.ident in ('5', '6') and rounds is not None:
            if not 1000 <= rounds <= 999999999:
                raise ValueError('rounds out of the range 1000 to 999_999_999')
            salt += 'rounds={0}$'.format(rounds)
    else:
        salt = ''
    
    salt += ''.join(random.choice(saltchars) for _ in range(method.salt_chars))
    return salt


def crypt(word, salt=None):
    """Return a string representing the one-way hash of a password.
    
    If salt is not specified, the strongest available method will be used.
    
    Args:
        word: The password to hash
        salt: The salt string (e.g., '$6$rounds=5000$saltsalt$') or a METHOD_* constant
        
    Returns:
        The hashed password string
        
    Raises:
        ImportError: If libcrypt is not available on the system
    """
    if _libcrypt is None:
        raise ImportError(
            "crypt_fallback requires libcrypt/libxcrypt. "
            "Install with: sudo tdnf install libxcrypt (Azure Linux) or "
            "sudo apt install libcrypt1 (Debian/Ubuntu)"
        )
    
    # Handle METHOD_* constants passed as salt
    if salt is None or isinstance(salt, _Method):
        salt = mksalt(salt)
    
    # Encode strings to bytes for ctypes
    if isinstance(word, str):
        word = word.encode('utf-8')
    if isinstance(salt, str):
        salt = salt.encode('utf-8')
    
    result = _libcrypt.crypt(word, salt)
    
    if result is None:
        raise ValueError("crypt() failed - invalid salt or system error")
    
    return result.decode('utf-8')
