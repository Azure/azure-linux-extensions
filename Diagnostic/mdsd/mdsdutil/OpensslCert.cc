// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include <openssl/x509.h>
#include <cstring>
#include <stdexcept>
#include "OpensslCert.hh"

bool OpensslCert::IsValid() const
{
    if (m_invalid)
    {
        return false;
    }
    if (!m_cert)
    {
        m_invalid = true;
        return false;
    }

    ASN1_TIME* notBefore = X509_get_notBefore(m_cert.get());

    int nDiffDays = 0;
    int nDiffSeconds = 0;
    if (!ASN1_TIME_diff(&nDiffDays, &nDiffSeconds, notBefore, NULL)) {
        throw std::runtime_error("ASN1_TIME_diff() failed for checking notBefore time.");
    }

    if (nDiffSeconds < 0 || nDiffDays < 0) {
        return false;
    }

    ASN1_TIME* notAfter = X509_get_notAfter(m_cert.get());
    if (!ASN1_TIME_diff(&nDiffDays, &nDiffSeconds, notAfter, NULL)) {
        throw std::runtime_error("ASN1_TIME_diff() failed for checking notAfter time.");
    }

    if (nDiffSeconds > 0 || nDiffDays > 0) {
        return false;
    }
    return true;
}
