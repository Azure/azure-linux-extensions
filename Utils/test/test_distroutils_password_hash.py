#!/usr/bin/env python
#
# Copyright 2026 Microsoft Corporation
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
# Tests for gen_password_hash in GenericDistro (distroutils.py).
#
# Strategy:
#   - We cannot compare hashes across libraries because each generates a fresh
#     random salt, so hashes will always differ.
#   - Instead, we verify each library's hash *verifies* against the original
#     password using that same library.
#   - We also test that gen_password_hash raises ImportError when nothing is available.

import unittest
import unittest.mock as mock

# ---------------------------------------------------------------------------
# Minimal stub config so GenericDistro can be instantiated without the full
# extension environment.
# ---------------------------------------------------------------------------
class _StubConfig:
    def get(self, key):
        return None


def _make_distro():
    # Import after path manipulation if needed; distroutils expects Utils.*
    # to be importable, so run tests from the repo root:
    #   python -m pytest Utils/test/test_distroutils_password_hash.py
    import Utils.distroutils as du
    return du.GenericDistro(_StubConfig())


class TestGenPasswordHashWithCrypt(unittest.TestCase):
    """Hash produced by the built-in 'crypt' (or 'legacycrypt') module."""

    def setUp(self):
        # Skip if crypt / legacycrypt is not available in this environment.
        try:
            import crypt as _crypt
            self._crypt = _crypt.crypt
        except ImportError:
            try:
                from legacycrypt import crypt as _crypt
                self._crypt = _crypt
            except ImportError:
                self.skipTest("Neither 'crypt' nor 'legacycrypt' is available")

    def test_hash_verifies_with_crypt(self):
        distro = _make_distro()
        password = "TestP@ssw0rd!"
        hash_val = distro.gen_password_hash(password, crypt_id=6, salt_len=10)

        # A valid crypt hash starts with the salt prefix
        self.assertTrue(hash_val.startswith("$6$"), "Expected SHA-512 hash prefix '$6$'")
        # Verify: re-hashing with the produced hash as the salt must equal the hash
        self.assertEqual(self._crypt(password, hash_val), hash_val,
                         "Hash does not verify against the original password")

    def test_different_passwords_produce_different_hashes(self):
        distro = _make_distro()
        hash1 = distro.gen_password_hash("PasswordOne1!", crypt_id=6, salt_len=10)
        hash2 = distro.gen_password_hash("PasswordTwo2!", crypt_id=6, salt_len=10)
        self.assertNotEqual(hash1, hash2)

    def test_same_password_produces_different_hashes_due_to_salting(self):
        # Each call generates a fresh random salt, so the same password must
        # produce a different hash every time — proving salting is in effect.
        distro = _make_distro()
        password = "TestP@ssw0rd!"
        hash1 = distro.gen_password_hash(password, crypt_id=6, salt_len=10)
        hash2 = distro.gen_password_hash(password, crypt_id=6, salt_len=10)
        self.assertNotEqual(hash1, hash2, "Same password produced identical hashes — salt may not be random")

    def test_crypt_id_5_produces_sha256_hash(self):
        distro = _make_distro()
        hash_val = distro.gen_password_hash("TestP@ssw0rd!", crypt_id=5, salt_len=10)
        self.assertTrue(hash_val.startswith("$5$"), "Expected SHA-256 hash prefix '$5$'")


class TestGenPasswordHashWithPasslib(unittest.TestCase):
    """Hash produced by passlib (fallback when crypt/legacycrypt unavailable)."""

    def setUp(self):
        try:
            from passlib.hash import sha512_crypt as _sha512
            self._sha512 = _sha512
        except ImportError:
            self.skipTest("'passlib' is not available")

    def test_hash_verifies_with_passlib(self):
        import Utils.distroutils as du

        # Force the passlib path by temporarily patching the module-level flags.
        with mock.patch.object(du, 'cryptImported', False), \
             mock.patch.object(du, 'passLibImported', True):
            distro = du.GenericDistro(_StubConfig())
            password = "TestP@ssw0rd!"
            hash_val = distro.gen_password_hash(password, crypt_id=6, salt_len=10)

        self.assertTrue(hash_val.startswith("$6$"),
                        "Expected passlib SHA-512 hash prefix '$6$'")
        self.assertTrue(self._sha512.verify(password, hash_val),
                        "Hash does not verify against the original password")

    def test_passlib_different_passwords_produce_different_hashes(self):
        import Utils.distroutils as du

        with mock.patch.object(du, 'cryptImported', False), \
             mock.patch.object(du, 'passLibImported', True):
            distro = du.GenericDistro(_StubConfig())
            hash1 = distro.gen_password_hash("PasswordOne1!", crypt_id=6, salt_len=10)
            hash2 = distro.gen_password_hash("PasswordTwo2!", crypt_id=6, salt_len=10)

        self.assertNotEqual(hash1, hash2)

    def test_passlib_same_password_produces_different_hashes_due_to_salting(self):
        import Utils.distroutils as du

        with mock.patch.object(du, 'cryptImported', False), \
             mock.patch.object(du, 'passLibImported', True):
            distro = du.GenericDistro(_StubConfig())
            password = "TestP@ssw0rd!"
            hash1 = distro.gen_password_hash(password, crypt_id=6, salt_len=10)
            hash2 = distro.gen_password_hash(password, crypt_id=6, salt_len=10)

        self.assertNotEqual(hash1, hash2, "Same password produced identical hashes — passlib salt may not be random")

class TestCreateAccountPasswordHashFailure(unittest.TestCase):
    """
    Verify behavior of create_account and change_password when no hashing
    library is available.

    gen_password_hash raises ImportError, which propagates through
    chpasswd -> change_password -> create_account, causing vmaccess.py to
    fail the extension operation via its general except block.
    """

    def test_create_account_raises_when_password_hash_unavailable(self):
        import Utils.distroutils as du

        with mock.patch.object(du, 'cryptImported', False), \
             mock.patch.object(du, 'passLibImported', False), \
             mock.patch('pwd.getpwnam', side_effect=KeyError), \
             mock.patch('Utils.extensionutils.run', return_value=0), \
             mock.patch('os.path.isdir', return_value=True), \
             mock.patch('Utils.extensionutils.set_file_contents'), \
             mock.patch('os.chmod'):
            distro = du.GenericDistro(_StubConfig())
            with self.assertRaises(ImportError):
                distro.create_account(
                    user="testuser",
                    password="SomePassword1!",
                    expiration=None,
                    thumbprint=None,
                    enable_nopasswd=False
                )

class TestGenPasswordHashNoLibraryAvailable(unittest.TestCase):
    """When no hashing library is importable, gen_password_hash raises ImportError."""

    def test_gen_password_hash_raises_when_nothing_importable(self):
        import Utils.distroutils as du

        with mock.patch.object(du, 'cryptImported', False), \
             mock.patch.object(du, 'passLibImported', False):
            distro = du.GenericDistro(_StubConfig())
            with self.assertRaises(ImportError):
                distro.gen_password_hash("SomePassword1!", crypt_id=6, salt_len=10)

    def test_chpasswd_raises_when_nothing_importable(self):
        import Utils.distroutils as du

        with mock.patch.object(du, 'cryptImported', False), \
             mock.patch.object(du, 'passLibImported', False):
            distro = du.GenericDistro(_StubConfig())
            with self.assertRaises(ImportError):
                distro.chpasswd("someuser", "SomePassword1!")


if __name__ == '__main__':
    unittest.main()
