// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include <vector>
#include <bond/core/bond.h>
#include <stddef.h>
#include <boost/asio.hpp>

#include "BinaryWriter.hh"
#include "EventHubPublisher.hh"
#include "MdsCmdLogger.hh"
#include "Trace.hh"
#include "PublisherStatus.hh"
#include "MdsException.hh"

using namespace mdsd::details;
using namespace web::http;
using namespace web::http::client;

static std::vector<byte>
SerializeData(
    const std::string & text
    )
{
    std::vector<byte> v;
    BinaryWriter writer(v);
    writer.Write(text);
    return v;
}

static bool
DisableWeakSslCiphers(
    const std::string & url,
    web::http::client::native_handle handle
)
{
    const std::string https = "https:";
    if (url.size() <= https.size()) {
        return true;
    }
    bool isHttps = (0 == strncasecmp(url.c_str(), https.c_str(), https.size()));
    if (!isHttps) {
        return true;
    }

    bool resultOK = true;
    boost::asio::ssl::stream<boost::asio::ip::tcp::socket &>* streamobj =
        static_cast<boost::asio::ssl::stream<boost::asio::ip::tcp::socket &>* >(handle);

    if (streamobj)
    {
        SSL* ssl = streamobj->native_handle();
        if (ssl)
        {
            const int isOK = 1;
            const std::string cipherList = "HIGH:!DSS:!RC4:!aNULL@STRENGTH";
            if (::SSL_set_cipher_list(ssl, cipherList.c_str()) != isOK) {
                MdsCmdLogError("Error: failed to disable weak ciphers: " + cipherList + "; URL: " + url);
                resultOK = false;
            }
        }
    }
    return resultOK;
}

EventHubPublisher::EventHubPublisher(
    const std::string & hostUrl,
    const std::string & eventHubUrl,
    const std::string & sasToken) :
    m_hostUrl(hostUrl),
    m_eventHubUrl(eventHubUrl),
    m_sasToken(sasToken),
    m_httpclient(nullptr),
    m_resetHttpClient(false)
{

}

// The actual data sent to EventHub is a serialized version of EventDataT::GetData().
// However, because EventDataT::GetData() is std::string, and serialization doesn't
// change the size of std::string, use the std::string's size to do validation.
static void
ValidateData(
    const mdsd::EventDataT & data
    )
{
    if (data.GetData().size() > mdsd::EventDataT::GetMaxSize()) {
        std::ostringstream strm;
        strm << "EventHub data is too big: max=" << mdsd::EventDataT::GetMaxSize()
             << " B; input=" << data.GetData().size() << " B. Drop it.";
        throw mdsd::TooBigEventHubDataException(strm.str());
    }
}

http_request
EventHubPublisher::CreateRequest(
    const EventDataT & data
    )
{
    ValidateData(data);
    auto serializedData = SerializeData(data.GetData());

    http_request req;
    req.set_request_uri(m_eventHubUrl);
    req.set_method(methods::POST);
    req.headers().add("Authorization", m_sasToken);
    req.headers().add("Content-Type", "application/atom+xml;type=entry;charset=utf-8");

    req.set_body(serializedData);

    for (const auto & it : data.Properties()) {
        req.headers().add(it.first, it.second);
    }

    return req;
}

void
EventHubPublisher::ResetClient()
{
    Trace trace(Trace::MdsCmd, "EventHubPublisher::ResetClient");

    if (m_httpclient) {
        trace.NOTE("Http client will be reset due to previous failure.");
        m_httpclient.reset();
        m_resetHttpClient = false;
    }

    auto lambda = [this](web::http::client::native_handle handle)->void
    {
        (void) DisableWeakSslCiphers(m_hostUrl, handle);
    };

    http_client_config httpClientConfig;
    httpClientConfig.set_timeout(std::chrono::seconds(30)); // http request timeout value
    httpClientConfig.set_nativehandle_options(lambda);
    m_httpclient = std::move(std::unique_ptr<http_client>(new http_client(m_hostUrl, httpClientConfig)));
}

bool
EventHubPublisher::Publish(
    const EventDataT& data
    )
{
    if (data.empty()) {
        MdsCmdLogWarn("Empty data is passed to publisher. Drop it.");
        return true;
    }

    try {
        if (!m_httpclient || m_resetHttpClient) {
            ResetClient();
        }

        auto postRequest = CreateRequest(data);
        auto httpResponse = m_httpclient->request(postRequest).get();
        return HandleServerResponse(httpResponse, false);
    }
    catch(const mdsd::TooBigEventHubDataException & ex)
    {
        MdsCmdLogWarn(ex.what());
        return true;
    }
    catch(const std::exception & ex)
    {
        MdsCmdLogError("Error: EH publish to " + m_eventHubUrl + " failed: " + ex.what());
    }
    catch(...)
    {
        MdsCmdLogError("Error: EH publish to " + m_eventHubUrl +" has unknown exception.");
    }

    m_resetHttpClient = true;
    return false;
}

pplx::task<bool>
EventHubPublisher::PublishAsync(
    const EventDataT& data
    )
{
    if (data.empty()) {
        MdsCmdLogWarn("Empty data is passed to async publisher. Drop it.");
        return pplx::task_from_result(true);
    }
    try {
        if (!m_httpclient || m_resetHttpClient) {
            ResetClient();
        }

        auto postRequest = CreateRequest(data);
        auto shThis = shared_from_this();

        return m_httpclient->request(postRequest)
        .then([shThis](pplx::task<http_response> responseTask)
        {
            return shThis->HandleServerResponseAsync(responseTask);
        });
    }
    catch(const mdsd::TooBigEventHubDataException & ex)
    {
        MdsCmdLogWarn(ex.what());
        return pplx::task_from_result(true);
    }
    catch(const std::exception & ex)
    {
        MdsCmdLogError("Error: EH async publish to " + m_eventHubUrl + " failed: " + ex.what());
    }

    m_resetHttpClient = true;
    return pplx::task_from_result(false);
}

bool
EventHubPublisher::HandleServerResponseAsync(
    pplx::task<http_response> responseTask
    )
{
    try {
        return HandleServerResponse(responseTask.get(), true);
    }
    catch(const std::exception & e)
    {
        MdsCmdLogError("Error: EH async publish to " + m_eventHubUrl +
            " failed with http response: " + e.what());
    }
    m_resetHttpClient = true;
    return false;
}

bool
EventHubPublisher::HandleServerResponse(
    const http_response & response,
    bool isFromAsync
    )
{
    Trace trace(Trace::MdsCmd, "EventHubPublisher::HandleServerResponse");
    PublisherStatus pubStatus = PublisherStatus::Idle;

    auto statusCode = response.status_code();
    TRACEINFO(trace, "Http response status_code=" << statusCode << "; Reason='" << response.reason_phrase() << "'");

    const int HttpStatusThrottled = 429;

    std::string errDetails;

    switch(statusCode) {
        case status_codes::Created: // 201. According to MSDN, 201 means success.
        case status_codes::OK:
            pubStatus = PublisherStatus::PublicationSucceeded;
            break;
        case status_codes::BadRequest:
            pubStatus = PublisherStatus::PublicationFailedWithBadRequest;
            break;
        case status_codes::Unauthorized:
        case status_codes::Forbidden:
            pubStatus = PublisherStatus::PublicationFailedWithAuthError;
            errDetails += " SAS: '" + m_sasToken + "'";
            break;
        case status_codes::ServiceUnavailable:
            pubStatus = PublisherStatus::PublicationFailedServerBusy;
            m_resetHttpClient = true;
            break;
        case HttpStatusThrottled:
            pubStatus = PublisherStatus::PublicationFailedThrottled;
            break;
        default:
            pubStatus = PublisherStatus::PublicationFailedWithUnknownReason;
            break;
    }

    if (PublisherStatus::PublicationSucceeded != pubStatus) {
        std::ostringstream strm;
        strm << "Error: EH publish to " << m_eventHubUrl << errDetails << " failed with status="
             << pubStatus << std::boolalpha << ". isAsync=" << isFromAsync;
        MdsCmdLogError(strm);
    }
    else {
        TRACEINFO(trace, "publication succeeded. isAsync=" << std::boolalpha << isFromAsync);
    }
    return (PublisherStatus::PublicationSucceeded == pubStatus);
}
