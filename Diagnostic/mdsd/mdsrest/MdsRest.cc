// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include <vector>
#include <sstream>
#include <cpprest/json.h>
#include <wascore/basic_types.h>
#include <boost/asio.hpp>
#include <boost/asio/ssl.hpp>
#include <cctype>

#include "GcsJsonData.hh"
#include "GcsJsonParser.hh"
#include "GcsUtil.hh"
#include "Logger.hh"
#include "MdsRest.hh"
#include "MdsConst.hh"
#include "OpensslCert.hh"
#include "OpensslCertStore.hh"
#include "Trace.hh"


using namespace mdsd;
using namespace web::http;
using namespace web::http::client;

static inline void
ThrowIfEmpty(
    const std::string & apiName,
    const std::string & argName,
    const std::string & argVal
    )
{
    if (argVal.empty()) {
        throw std::invalid_argument(apiName + ": unexpected empty string for " + argName);
    }
}

MdsRestInterface::MdsRestInterface(
    const std::string & endPoint,
    const std::string & gcsEnvironment,
    const std::string & thumbPrint,
    const std::string & certFile,
    const std::string & keyFile,
    const std::string & sslDigest
    ) :
    m_endPoint(endPoint),
    m_gcsEnv(gcsEnvironment),
    m_thumbPrint(thumbPrint),
    m_certFile(certFile),
    m_keyFile(keyFile),
    m_sslDigest(sslDigest)
{
    ThrowIfEmpty("MdsRestInterface", "gcsEnvironment", gcsEnvironment);
    ThrowIfEmpty("MdsRestInterface", "thumbPrint", thumbPrint);
    ThrowIfEmpty("MdsRestInterface", "certFile", certFile);
    ThrowIfEmpty("MdsRestInterface", "keyFile", keyFile);
    ThrowIfEmpty("MdsRestInterface", "sslDigest", sslDigest);
}

bool
MdsRestInterface::Initialize()
{
    Trace trace(Trace::MdsCmd, "MdsRestInterface::Initialize");

    try {
        if (m_endPoint.empty()) {
            m_endPoint = GcsUtil::GetGcsEndpointFromEnvironment(m_gcsEnv);
            if (m_endPoint.empty()) {
                Logger::LogError("Error: unexpected empty value for GCS endpoint.");
                return false;
            }
        }

        m_initialized = InitCert();
    }
    catch(const std::exception & ex) {
        Logger::LogError(std::string("Error: MdsRestInterface::Initialize() exception: ") + ex.what());
        m_initialized = false;
    }

    return m_initialized;
}

bool
MdsRestInterface::InitCert()
{
    Trace trace(Trace::MdsCmd, "MdsRestInterface::InitCert");
    bool retVal = true;
    try {
        OpensslCertStore certStore(m_certFile, m_keyFile, m_sslDigest);
        m_cert = certStore.LoadCertificate(m_thumbPrint);
        if (!m_cert->IsValid()) {
            Logger::LogError("Error: initializing certificate failed: certificate is invalid");
            retVal = false;
            m_cert = nullptr;
        }
    }
    catch(const std::exception& ex) {
        Logger::LogError(std::string("Error: initializing certificate failed: ") + ex.what());
        retVal = false;
    }

    return retVal;
}

void
MdsRestInterface::ResetClient()
{
    Trace trace(Trace::MdsCmd, "MdsRestInterface::ResetClient");

    if (m_client) {
        TRACEINFO(trace, "Http client will be reset due to previous failure.");
        m_client.reset();
        m_resetHttpClient = false;
    }

    http_client_config httpClientConfig;
    httpClientConfig.set_validate_certificates(true);
    httpClientConfig.set_timeout(utility::seconds(gcs::c_HttpTimeInSeconds));

    httpClientConfig.set_nativehandle_options([this](web::http::client::native_handle handle)->void
    {
        SetNativeHandleOptions(handle);
    });

    auto fullEndpoint = "https://" + m_endPoint;
    m_client = std::move(std::unique_ptr<http_client>(new http_client(fullEndpoint.c_str(), httpClientConfig)));
}

pplx::task<bool>
MdsRestInterface::QueryGcsAccountInfo(
    const std::string & mdsAccount,
    const std::string & mdsNamespace,
    const std::string & configVersion,
    const std::string & region,
    const std::string & agentIdentity,
    const std::string & tagId
    )
{
    Trace trace(Trace::MdsCmd, "MdsRestInterface::QueryGcsAccountInfo");

    ThrowIfEmpty("GcsAccountInfo", "mdsAccount", mdsAccount);
    ThrowIfEmpty("GcsAccountInfo", "mdsNamespace", mdsNamespace);
    ThrowIfEmpty("GcsAccountInfo", "configVersion", configVersion);
    ThrowIfEmpty("GcsAccountInfo", "region", region);
    ThrowIfEmpty("GcsAccountInfo", "agentIdentity", agentIdentity);

    if (!m_initialized) {
        if (!Initialize()) {
            return pplx::task_from_result(false);
        }
    }

    try {
        auto apicall = BuildGcsApiCall(mdsAccount);
        auto args = BuildGcsAcountArgs(mdsNamespace, configVersion, region, agentIdentity, tagId);
        return ExecuteGcsGetCall(apicall, args);
    }
    catch(const std::exception & ex) {
        Logger::LogError(std::string("Error: QueryGcsAccountInfo() exception: ") + ex.what());
    }
    return pplx::task_from_result(false);
}

std::string
MdsRestInterface::BuildGcsApiCall(
    const std::string & mdsAccount
    )
{
    std::ostringstream apicall;
    apicall << gcs::c_GcsServiceName
            << m_gcsEnv << "/"
            << mdsAccount << "/"
            << gcs::c_GcsMonitoringStorageKeysApiName << "/";
    return apicall.str();
}

std::string
MdsRestInterface::BuildGcsAcountArgs(
    const std::string & mdsNamespace,
    const std::string & configVersion,
    const std::string & region,
    const std::string & agentIdentity,
    const std::string & tagId
    )
{
    // Encode agentIdentity so that no special character like '/' is used in URI.
    std::vector<unsigned char> vec(agentIdentity.begin(), agentIdentity.end());
    auto encodedAgentId = utility::conversions::to_base64(vec);

    std::ostringstream args;
    args << "Namespace=" << mdsNamespace
         << "&ConfigMajorVersion=" << configVersion
         << "&Region=" << region
         << "&Identity=" << encodedAgentId;

    if (!tagId.empty()) {
        args << "&TagId=" + tagId;
    }
    return args.str();
}


pplx::task<bool>
MdsRestInterface::ExecuteGcsGetCall(
    const std::string & contractApi,
    const std::string & arguments
    )
{
    Trace trace(Trace::MdsCmd, "MdsRestInterface::ExecuteGcsGetCall");
    TRACEINFO(trace, "contractApi='" << contractApi << "'; arguments='" << arguments << "'");

    ThrowIfEmpty("ExecuteGcsGetCall", "contractApi", contractApi);
    ThrowIfEmpty("ExecuteGcsGetCall", "arguments", arguments);

    if (!m_client || m_resetHttpClient) {
        ResetClient();
    }

    web::http::uri_builder request_uri;
    request_uri.append_path(contractApi, false);
    request_uri.append_query(arguments, true);

    http_request request;
    auto requestId = utility::uuid_to_string(utility::new_uuid());
    request.headers().add(_XPLATSTR("x-ms-client-request-id"), requestId.c_str());
    request.set_request_uri(request_uri.to_uri());
    request.set_method(methods::GET);

    auto shThis = shared_from_this();
    TRACEINFO(trace, "Start to send request {" << requestId << "} to GCS: " << request.absolute_uri().to_string());

    return m_client->request(request)
    .then([shThis](pplx::task<web::http::http_response> task)
    {
        return shThis->HandleServerResponse(task);
    });

    TRACEINFO(trace, "ExecuteGcsGetCall returns false");
    return pplx::task_from_result(false);
}

void
MdsRestInterface::SetNativeHandleOptions(
    web::http::client::native_handle handle
    )
{
    Trace trace(Trace::MdsCmd, "MdsRestInterface::SetNativeHandleOptions");

    auto streamobj = static_cast<boost::asio::ssl::stream<boost::asio::ip::tcp::socket &>* >(handle);
    if (!streamobj) {
        throw std::runtime_error("SetNativeHandleOptions() failed: unexpected NULL tcp::socket handle");
    }
    auto ssl = streamobj->native_handle();
    if (!ssl) {
        throw std::runtime_error("SetNativeHandleOptions() failed: unexpected NULL ssl handle");
    }

    const int isOK = 1;
    auto errorcode = ::SSL_use_certificate(ssl, m_cert->GetCert());
    if (isOK != errorcode) {
        throw std::runtime_error("SSL_use_certificate() failed with error " + std::to_string(errorcode));
    }
    errorcode = ::SSL_use_PrivateKey(ssl, m_cert->GetPrivateKey());
    if (isOK != errorcode) {
        throw std::runtime_error("SSL_use_PrivateKey() failed with error " + std::to_string(errorcode));
    }

    // Disable weak ssl ciphers
    const std::string cipherList = "HIGH:!DSS:!RC4:!aNULL@STRENGTH";
    errorcode = ::SSL_set_cipher_list(ssl, cipherList.c_str());
    if (isOK != errorcode) {
        throw std::runtime_error("SSL_set_cipher_list() failed with error " + std::to_string(errorcode));
    }
}

std::string
MdsRestInterface::GetRequestIdFromResponse(
    const std::string & responseString
    )
{
    Trace trace(Trace::MdsCmd, "MdsRestInterface::GetRequestIdFromResponse");
    if (responseString.empty()) {
        TRACEINFO(trace, "ResponseString is empty. No request id is found.");
        return std::string();
    }

    auto ptr = responseString.find(mdsd::gcs::c_RequestIdHeader);
    if (ptr == std::string::npos) {
        TRACEINFO(trace, "No request id is found from response string.");
        return std::string();
    }

    ptr += mdsd::gcs::c_RequestIdHeader.size();

    auto index = responseString.find_first_not_of(' ', ptr);
    std::string requestId;
    while(isalnum(responseString[index]) || responseString[index] == '-') {
        requestId.append(1, responseString[index]);
        index++;
    }

    TRACEINFO(trace, "RequestId from response: '" << requestId << "'");
    return requestId;
}

static inline bool
IsHttpStatusOK(web::http::status_code statusCode)
{
    return (status_codes::OK == statusCode ||
        status_codes::Created == statusCode);  // 201. According to MSDN, 201 means success.
}


bool
MdsRestInterface::HandleServerResponse(
    pplx::task<web::http::http_response> responseTask
    )
{
    Trace trace(Trace::MdsCmd, "MdsRestInterface::HandleServerResponse");

    bool retVal = false;

    try {
        auto response = responseTask.get();
        auto statusCode = response.status_code();
        auto responseString = response.to_string();

        if (trace.IsActive()) {
            TRACEINFO(trace, "Response Code: " << statusCode << "; Response: " << responseString);
        }

        if (!IsHttpStatusOK(statusCode)) {
            auto requestId = GetRequestIdFromResponse(responseString);
            std::ostringstream ostr;
            ostr << "Error: request to Geneva failed with status code=" << statusCode
                 << "; requestId=" << requestId << "; Response: " << responseString;
            Logger::LogError(ostr.str());

            // Only reset http client when the GCS service is not available and need reconnect later.
            if (status_codes::ServiceUnavailable == statusCode) {
                m_resetHttpClient = true;
            }
        }
        else {
            m_responseJsonVal = response.extract_json().get();

            // As long as the json object has the expected type, it is OK for http request.
            // Detailed data and validation need to be parsed from this json object.
            if (web::json::value::Object == m_responseJsonVal.type()) {
                retVal = true;
            }
            else {
                auto requestId = GetRequestIdFromResponse(responseString);
                auto jsonType = m_responseJsonVal.type();
                auto jsonTypeStr = mdsd::GcsUtil::GetJsonTypeStr(jsonType);
                std::ostringstream ostr;
                ostr << "Error: received response, but an unexpected result was returned; "
                     << "expected a JSON object, but received type "
                     << jsonType << " " << jsonTypeStr << "; requestId=" << requestId;
                Logger::LogError(ostr.str());
            }
        }
    }
    catch(const std::exception & ex) {
        Logger::LogError(std::string("Error: request failed with exception: ") + ex.what());
        m_resetHttpClient = true;
    }

    TRACEINFO(trace, "HandleServerResponse returned " << (retVal? "true" : "false"));
    return retVal;
}

bool
MdsRestInterface::GetGcsAccountData(GcsAccount & gcsAccount) const
{
    Trace trace(Trace::MdsCmd, "MdsRestInterface::GetGcsAccountData()");
    if (m_responseJsonVal.is_null()) {
        TRACEINFO(trace, "GCS account JSON object is null.");
        return false;
    }
    else {
        GcsJsonParser parser(m_responseJsonVal);
        return parser.Parse(gcsAccount);
    }
}
