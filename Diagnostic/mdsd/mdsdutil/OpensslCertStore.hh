// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once

#ifndef _OPENSSLCERTSTORE_HH__
#define _OPENSSLCERTSTORE_HH__

#include <memory>

class OpensslCert;

/// <summary>
/// Represents a OpenSSL certificate store.
/// </summary>
class OpensslCertStore
{
public:
    /// <summary>
    /// Initializes a CertificateStore object.
    /// Throw exception if any of the input strings is empty.
    /// </summary>
    OpensslCertStore(
        const std::string& certFile,
        const std::string& privateKeyFile,
        const std::string& sslDigest);

    /// <summary>
    /// Destroys the object and releases all associated resources.
    /// </summary>
    ~OpensslCertStore() { }

    /// <summary>
    /// Loads certificate from the store by certificate's thumb print.
    /// Throw exception if any error.
    /// </summary>
    std::shared_ptr<OpensslCert> LoadCertificate(const std::string& thumbprint);

private:
    /// Read a public certificate object from the file. The file
    /// must be a plain text file in PEM format.
    /// Caller function needs to call X509_free(X509*) to free the object.
    /// Return X509* object or NULL if any error.
    std::shared_ptr<X509> ReadCertFromFile();

    /// Read a private key object from the file. The file
    /// must be in a plain text file in PEM format.
    /// Caller function needs to call EVP_PKEY_free(EVP_PKEY*) to free the object.
    /// Return EVP_PKEY* object or NULL if any error.
    std::shared_ptr<EVP_PKEY> ReadPrivateKeyFromFile();

    /// Get the certificate digest object.
    /// If m_SslDigest is empty, or if any error occurs when using the given
    /// non-empty SslDigest, return SHA1 digest object.        
    const EVP_MD* GetCertDigest();

    /// Return the thumbprint in upper case for the given cert object.
    /// If any error, return "".
    std::string GetCertThumbprint(X509* cert);


    std::string m_CertFile;
    std::string m_PrivateKeyFile;
    std::string m_SslDigest;
};


#endif

