// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include <fstream>
#include <openssl/pem.h>
#include <algorithm>

#include "OpensslCert.hh"
#include "OpensslCertStore.hh"
#include "Utility.hh"

static std::string
StringToUpper(
    std::string strToConvert
    )
{
    std::transform(strToConvert.begin(), strToConvert.end(), strToConvert.begin(), ::toupper);
    return strToConvert;
}

static void
CertDeleter(X509* cert)
{
    if (cert) {
        X509_free(cert);
    }
}

static void
KeyDeleter(EVP_PKEY* pkey)
{
    if (pkey) {
        EVP_PKEY_free(pkey);
    }
}

OpensslCertStore::OpensslCertStore(
    const std::string& certFile,
    const std::string& privateKeyFile,
    const std::string& sslDigest) :
    m_CertFile(certFile),
    m_PrivateKeyFile(privateKeyFile),
    m_SslDigest(sslDigest)
{
    if (certFile.empty()) {
        throw std::invalid_argument("OpensslCertStore: unexpected empty string for certFile");
    }
    if (privateKeyFile.empty()) {
        throw std::invalid_argument("OpensslCertStore: unexpected empty string for privateKeyFile");
    }
    if (sslDigest.empty()) {
        throw std::invalid_argument("OpensslCertStore: unexpected empty string for sslDigest");
    }
}

std::shared_ptr<X509>
OpensslCertStore::ReadCertFromFile()
{
    if (!MdsdUtil::IsRegFileExists(m_CertFile))
    {
        throw std::runtime_error("ReadCertFromFile(): failed to find certificate file: '" + m_CertFile + "'");
    }

    FILE *fp = fopen(m_CertFile.c_str(), "r");
    if (!fp) {
        throw std::runtime_error("ReadCertFromFile(): failed to open certificate file: '" + m_CertFile + "'");
    }
    MdsdUtil::FileCloser fcloser(fp);

    X509 *cert = PEM_read_X509(fp, NULL, NULL, NULL);
    if (!cert) {
        throw std::runtime_error("ReadCertFromFile(): failed to read certificate file: '" + m_CertFile + "'");
    }

    return std::shared_ptr<X509>(cert, CertDeleter);
}

std::shared_ptr<EVP_PKEY>
OpensslCertStore::ReadPrivateKeyFromFile()
{
    if (!MdsdUtil::IsRegFileExists(m_PrivateKeyFile))
    {
        throw std::runtime_error("ReadPrivateKeyFromFile(): failed to find privatekey file: '" + m_PrivateKeyFile + "'");
    }
    FILE* fp = fopen(m_PrivateKeyFile.c_str(), "r");
    if (!fp) {
        throw std::runtime_error("ReadPrivateKeyFromFile(): failed to open privatekey file: '" + m_PrivateKeyFile + "'");
    }
    MdsdUtil::FileCloser fcloser(fp);

    EVP_PKEY* keyobj = PEM_read_PrivateKey(fp, NULL, NULL, NULL);
    if (!keyobj)
    {
        throw std::runtime_error("ReadPrivateKeyFromFile(): failed to read privatekey file: '" + m_PrivateKeyFile + "'");
    }

    return std::shared_ptr<EVP_PKEY>(keyobj, KeyDeleter);
}


const EVP_MD*
OpensslCertStore::GetCertDigest()
{
    OpenSSL_add_all_digests();
    auto pdigest = EVP_get_digestbyname(m_SslDigest.c_str());
    if (!pdigest) {
        throw std::runtime_error("GetCertDigest: failed to get digest by name: " +  m_SslDigest);
    }
    return pdigest;
}

std::string
OpensslCertStore::GetCertThumbprint(
    X509* cert
    )
{
    if (!cert) {
        throw std::invalid_argument("GetCertThumbprint(): unexpected nullptr for cert");
    }

    std::string thumbprint;
    unsigned char mdarray[EVP_MAX_MD_SIZE];
    const EVP_MD* pdigest = GetCertDigest();
    unsigned int len = 0;
    if (!X509_digest(cert, pdigest, mdarray, &len))
    {
        throw std::runtime_error("GetCertThumbprint(): failed at calling X509_digest(): out of memory");
    }   
    else {
        unsigned int w = 2;
        size_t buflen = len*w+1;
        char buf[buflen];
        char* pbuf = (char*)buf;

        for (unsigned int i = 0; i < len; i++)
        {           
            BIO_snprintf(pbuf, w+1, "%02X", mdarray[i]);
            pbuf += w;
        }
        buf[buflen-1] = '\0';
        thumbprint = buf;

        thumbprint = StringToUpper(thumbprint);
    }

    return thumbprint;
}


std::shared_ptr<OpensslCert>
OpensslCertStore::LoadCertificate(
    const std::string& thumbprint
    )
{
    if (thumbprint.empty())
    {
        throw std::invalid_argument("LoadCertificate(): unexpected empty string for thumbprint");
    }

    std::shared_ptr<X509> certObj = ReadCertFromFile();
    if (!certObj) {
        throw std::runtime_error("LoadCertificate(): failed to get certificate");
    }

    auto thumbprintFromFile = GetCertThumbprint(certObj.get());

    auto thumbprintUpper = StringToUpper(thumbprint);
    if (thumbprintFromFile != thumbprintUpper)
    {
        throw std::runtime_error("LoadCertificate(): given thumbprint " + thumbprint +
                                 " doesn't match cert " + m_CertFile + " thumbprint " + thumbprintFromFile);
    }

    std::shared_ptr<EVP_PKEY> pkey = ReadPrivateKeyFromFile();
    if (!pkey)
    {
        throw std::runtime_error("LoadCertificate(): failed to get private key");
    }
    return std::make_shared<OpensslCert>(certObj, pkey, thumbprintUpper);
}
