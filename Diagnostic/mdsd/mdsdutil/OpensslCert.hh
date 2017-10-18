// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _OPENSSLCERT_H_
#define _OPENSSLCERT_H_

#include <memory>
#include <ctime>
#include <string>
#include <openssl/x509.h>

/// <summary>
/// Represents a certificate used for HTTPS connection to the service.
/// </summary>
class OpensslCert
{
public:
    /// <summary>
    /// Initializes a Certificate object.
    /// </summary>
    /// <param name="cert">public certificate object</param>
    /// <param name="privateKey"> private key object. Can be NULL.</param>
    /// <param name="thumbprint">Certificate's thumbprint.</param>
    OpensslCert(
        const std::shared_ptr<X509> & cert,
        const std::shared_ptr<EVP_PKEY> & privateKey,
        const std::string& thumbprint) :
        m_cert(cert),
        m_privatekey(privateKey),
        m_thumbprint(thumbprint),
        m_invalid(false) 
    {
    }

    /// <summary>
    /// Destroys Certificate object and releases all associated resources.
    /// The certificate object and private key object in the contructor will be
    /// freed here.
    /// </summary>
    ~OpensslCert()
    {

    }

    /// <summary>
    /// Gets a value indicating whether certificate is still valid.
    /// </summary>
    bool IsValid() const;

    /// <summary>
    /// Explicitly marks certificate as invalid..
    /// </summary>
    void Invalidate()
    {
        m_invalid = true;
    }

    void SetAsValid()
    {
        m_invalid = false;
    }

    /// <summary>
    /// Gets the certificate's thumbprint.
    /// </summary>
    const std::string& GetThumbprint() const
    {
        return m_thumbprint;
    }

    /// <summary>
    /// Gets the certificate object.
    /// </summary>
    X509* GetCert() const
    {
        return m_cert.get();
    }

    EVP_PKEY* GetPrivateKey() const
    {
        return m_privatekey.get();
    }

private:
    std::shared_ptr<X509> m_cert;
    std::shared_ptr<EVP_PKEY> m_privatekey;
    std::string m_thumbprint;
    mutable bool m_invalid;
};


#endif
