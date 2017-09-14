// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "cryptutil.hh"

#include <exception>
#include <fstream>
#include <iostream>
#include <memory>
#include <sstream>
#include <system_error>

extern "C" {
#include <openssl/cms.h>
#include <openssl/err.h>
#include <openssl/pkcs7.h>
#include <openssl/pkcs12.h>
#include <openssl/ssl.h>
#include <openssl/x509.h>
#include <sys/stat.h>
}

using namespace std;

namespace cryptutil
{
    using uniqueEvpKey = std::unique_ptr<EVP_PKEY, void(*)(EVP_PKEY*)>;
    using uniqueCms = std::unique_ptr<CMS_ContentInfo, void (*)(CMS_ContentInfo*)>;
    using uniqueP12 = std::unique_ptr<PKCS12, void (*)(PKCS12*)>;
    
    // True if file exists, false if not
    bool FileExists(const string& filename)
    {
        struct stat buffer;   
        return ((stat(filename.c_str(), &buffer)==0) && S_ISREG(buffer.st_mode));
    }
    
    // Convert a hex string into a vector of bytes
    bool DecodeString(const string& encoded, vector<BYTE>& byteBuf)
    {
        if (encoded.length() < 2)
        {
            return false;
        }
        auto bufLen = encoded.length() / 2;
        byteBuf = vector<BYTE>(bufLen);
        size_t idx = 0;
        for (size_t i = 0; i < bufLen; i++)
        {
            BYTE data1 = (BYTE)(encoded[idx] - '0');
            if (data1 > 9)
            {
                data1 = (BYTE)((encoded[idx] - 'A') + 10);
            }
            BYTE data2 = (BYTE)(encoded[idx+1] - '0');
            if (data2 > 9)
            {
                data2 = (BYTE)((encoded[idx+1] - 'A') + 10);
            }
            byteBuf[i] = (data1 << 4) | data2;
            idx += 2;
        }
        return true;
    }

    // Read a string from the data in a BIO object
    string GetStringFromBio(BIO *mem)
    {
        if (mem == nullptr)
        {
            throw invalid_argument("A nullptr was passed in place of a BIO argument");
        }
        const int bufSize = 10;
        char buf[bufSize] = "";
        stringstream ss;
        while (BIO_gets(mem, buf, bufSize) > 0)
        {
            ss << buf;
        }
        return ss.str();
    }
    
    // Open a PKCS12 (.pfx) file, and return a suitable object or throw an exception
    uniqueP12 GetPkcs12FromFile(const string& privKeyPath)
    {
        FILE *p12_file = fopen(privKeyPath.c_str(), "rb");
        if (p12_file == nullptr)
        {
            throw system_error(errno, system_category(), string("Unable to read PKCS12 file " + privKeyPath));
        }
        PKCS12 *p12 = nullptr;
        d2i_PKCS12_fp(p12_file, &p12);
        fclose(p12_file);
        if (p12 == nullptr)
        {
            throw cryptutilException("PKCS12 structure could not be parsed from " + privKeyPath);
        }
        uniqueP12 retP12(p12, PKCS12_free);
        return retP12;
    }
    
    // Return the EVP_PKEY contained in the specified pkcs12 file, or throw an exception
    uniqueEvpKey GetPrivateKeyFromPkcs12(const string& privKeyPath, const string& keyPass)
    {
        EVP_PKEY *pkey = nullptr;
        X509 *cert = nullptr;
        
        uniqueP12 p12 = GetPkcs12FromFile(privKeyPath);
        
        if (!PKCS12_parse(p12.get(), keyPass.c_str(), &pkey, &cert, (STACK_OF(X509)**)nullptr))
        {
            throw cryptutilException("Could not parse private key from PKCS12 file " + privKeyPath);
        }
        uniqueEvpKey retKey(pkey, EVP_PKEY_free);
        // clear certs
        X509_free(cert);
        return retKey;
    }
    
    // Return the EVP_PKEY contained in the specified PEM file, or NULL if a failure occurs.
    uniqueEvpKey GetPrivateKeyFromPem(const string& privKeyPath)
    {
        BIO *keyBio = BIO_new_file(privKeyPath.c_str(), "r");
        if (keyBio == nullptr)
        {
            throw cryptutilException("Unable to read PEM file " + privKeyPath);
        }
        EVP_PKEY *pkey = PEM_read_bio_PrivateKey(keyBio, NULL, 0, NULL);
        BIO_free(keyBio);
        if (pkey == nullptr)
        {
            throw cryptutilException("Unable to parse private key from PEM file " + privKeyPath);
        }
        uniqueEvpKey retKey(pkey, EVP_PKEY_free);
        return retKey;
    }
    
    // Try to parse the specified file as PKCS12 (PFX) or PEM, return the private key or NULL
    uniqueEvpKey GetPrivateKeyFromUnknownFileType(const string& privKeyPath, const string& keyPass)
    {
        try
        {
            return GetPrivateKeyFromPem(privKeyPath);
        }
        catch (exception& ex)
        {
            // File isn't a PEM, but it might be a PFX. We don't care unless BOTH fail.
        }
        // This function can throw cryptutilException and system_error.
        // No need to catch/rethrow the exception - just let it go unhindered
        // The last call in this function should always allow any exceptions
        // to pass through to the caller.
        return GetPrivateKeyFromPkcs12(privKeyPath, keyPass);
    }
    
    // Parse the specified file as Cryptographic Message Syntax (CMS) or return NULL
    uniqueCms GetCMSFromEncodedString(const string& encoded)
    {
        // Decode text from hex chars to binary
        vector<BYTE> byteBuf;
        if(!DecodeString(encoded, byteBuf))
        {
            throw cryptutilException("Unable to decode provided string to CMS");
        }
        BIO *mem = BIO_new_mem_buf(byteBuf.data(), byteBuf.size());
        
        // Read encrypted text
        CMS_ContentInfo *cms = d2i_CMS_bio(mem, NULL);
        BIO_free(mem);
        if (cms == nullptr)
        {
            throw cryptutilException("Unable to parse CMS from decoded string");
        }
        uniqueCms retCms(cms, CMS_ContentInfo_free);
        return retCms;
    }

    // Given a private key and CMS object,return decrypted string
    // or throw an exception
    string DecryptCMSWithPrivateKey(uniqueEvpKey& pkey, uniqueCms& cms)
    {
        if (pkey.get() == nullptr)
        {
            throw invalid_argument("The provided private key must not be a nullptr");
        }
        if (cms.get() == nullptr)
        {
            throw invalid_argument("The provided CMS must not be a nullptr");
        }
        // Decrypt file contents
        BIO *out = BIO_new(BIO_s_mem());
        int res = CMS_decrypt(cms.get(), pkey.get(), NULL, NULL, out, 0);
        if (!res)
        {
            BIO_free(out);
            int error = ERR_get_error();
            const char* errstr = ERR_reason_error_string(error);
            if (errstr) {
                throw cryptutilException("Error decrypting cipher text [" + string(errstr) + "]");
            }
            else {
                throw cryptutilException("Error decrypting cipher text");
            }
        }
        string plaintext = GetStringFromBio(out);
        BIO_free(out);
        return plaintext;
    }

    // Given an encrypted STRING (CMS encoded as hex chars), a private key file, and an optional password,
    // decode and decrypt the CMS and return the decrypted string, or throw a cryptutilException if it fails
    string DecodeAndDecryptString(const string& privKeyPath, const string& encoded, const string& keyPass)
    {
        if (privKeyPath.empty())
        {
            throw invalid_argument("The private key path must not be an empty string");
        }
        if (encoded.empty())
        {
            throw invalid_argument("The encoded ciphertext must not be an empty string");
        }
        if (!FileExists(privKeyPath))
        {
            throw runtime_error("Private key file was not found at path: " + privKeyPath);
        }
        OpenSSL_add_all_algorithms();
        ERR_load_crypto_strings();

        // Read Private Key
        uniqueEvpKey pkey = GetPrivateKeyFromUnknownFileType(privKeyPath, keyPass);
        uniqueCms cms = GetCMSFromEncodedString(encoded);
        return DecryptCMSWithPrivateKey(pkey, cms);
    }
}
