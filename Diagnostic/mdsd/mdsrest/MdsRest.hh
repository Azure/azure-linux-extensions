// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once

#ifndef __MDSREST_HH__
#define __MDSREST_HH__

#include <string>
#include <memory>
#include <cpprest/http_client.h>
#include <pplx/pplxtasks.h>

class OpensslCert;

namespace mdsd {

struct GcsAccount;

/// This class defines APIs to call Geneva Configuration Service (GCS) REST APIs.
/// NOTE:
/// - This class is not thread-safe.
class MdsRestInterface : public std::enable_shared_from_this<MdsRestInterface>
{
public:
    /// Construct a new MdsRestInterface.
    /// <param name="endPoint">GCS endpoint. If empty, search its value
    /// using gcsEnvironment from pre-defined table. e.g. "ppe.warmpath.msftcloudes.com"</param>
    /// <param name="gcsEnvironment">Environment. e.g. "Test"</param>
    /// <param name="thumbPrint">Certificate thumb print</param>
    /// <param name="certFile">full path to public certificate file.</param>
    /// <param name="keyFile">full path to private key file.</param>
    /// <param name="sslDigest">certificate digest. e.g. "sha1"</param>
    static std::shared_ptr<MdsRestInterface> Create(
        const std::string & endPoint,
        const std::string & gcsEnvironment,
        const std::string & thumbPrint,
        const std::string & certFile,
        const std::string & keyFile,
        const std::string & sslDigest
        )
    {
        // Because the MdsRestInterface constructor is private, std::make_shared cannot be used.
        // std::make_shared requires public constructor.
        return std::shared_ptr<MdsRestInterface>(
            new MdsRestInterface(endPoint, gcsEnvironment, thumbPrint, certFile, keyFile, sslDigest));
    }

    ~MdsRestInterface() = default;

    /// Initialize MdsRestInterface.
    /// Return true if success, false if any error.
    bool Initialize();

    /// Query GCS account information. If successful, the result will be stored to
    /// json object m_responseJsonVal.
    ///
    /// <param name="mdsAccount">MDS Account name</param>
    /// <param name="mdsNamespace">MDS namespace</param>
    /// <param name="configVersion">configuration version. e.g. "Ver5v0"</param>
    /// <param name="region">Region to get storage account credentials. e.g. "westus"</param>
    /// <param name="agentIdentity">An identification string, which is used for
    /// http query hashing. It can be built from mdsd IdentityColumns.</param>
    /// <param name="tagid">GCS configuration tag id. GCS internally has a tag id, which
    /// is a combination of service configuration file md5 hash + account moniker versions.
    /// If the input tagId is equal to GCS's internal tag id, GCS will return null JSON objects.
    /// If the input tagId is not equal to GCS's internal tag id, GCS will return full
    /// account information. GCS account query will return its internal tagId in the returned JSON.
    ///
    /// Return true if success; return false if any error.
    pplx::task<bool> QueryGcsAccountInfo(
        const std::string & mdsAccount,
        const std::string & mdsNamespace,
        const std::string & configVersion,
        const std::string & region,
        const std::string & agentIdentity,
        const std::string & tagId);

    /// Get the account JSON object, which stores results from GCS account query.
    web::json::value GetGcsAccountJson() const { return m_responseJsonVal; }

    /// Parse GCS account JSON object and return the results in 'gcsAccount'.
    /// Return true if JSON object is successfully parsed.
    /// Return false if JSON object is null, or there is parsing error.
    bool GetGcsAccountData(GcsAccount & gcsAccount) const;

private:
    /// Constructor.
    MdsRestInterface(
        const std::string & endPoint,
        const std::string & gcsEnvironment,
        const std::string & thumbPrint,
        const std::string & certFile,
        const std::string & keyFile,
        const std::string & sslDigest);

    /// Load certificates from files.
    /// Return true if success, false if any error.
    bool InitCert();

    /// Reset http client if any. Then recreate it.
    void ResetClient();

    /// Build the api string to call GCS service.
    std::string BuildGcsApiCall(const std::string & mdsAccount);

    /// Build the args to call GCS account service.
    std::string BuildGcsAcountArgs(
        const std::string & mdsNamespace,
        const std::string & configVersion,
        const std::string & region,
        const std::string & agentIdentity,
        const std::string & tagId);

    /// Execute GCS REST API call.
    /// Return true if success, false if any error.
    pplx::task<bool> ExecuteGcsGetCall(const std::string & contractApi, const std::string & arguments);

    /// Set certificates on native openssl handle
    void SetNativeHandleOptions(web::http::client::native_handle handle);

    /// Get http request id from http response. This is for logging purpose.
    std::string GetRequestIdFromResponse(const std::string & responseString);

    /// Handle GCS http response. Extract desired data from the response.
    /// Return true if success, false if any error.
    bool HandleServerResponse(pplx::task<web::http::http_response> responseTask);

private:
    bool m_initialized = false;
    std::string m_endPoint;
    std::string m_gcsEnv;
    std::string m_thumbPrint;
    std::string m_certFile;
    std::string m_keyFile;
    std::string m_sslDigest;
    std::shared_ptr<OpensslCert> m_cert;

    std::unique_ptr<web::http::client::http_client> m_client;
    bool m_resetHttpClient = false;
    web::json::value m_responseJsonVal;
};

} // namespace mdsd

#endif // __MDSREST_HH__
