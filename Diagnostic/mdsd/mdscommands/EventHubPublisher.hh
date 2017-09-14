// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef __EVENTHUBPUBLISHER__HH__
#define __EVENTHUBPUBLISHER__HH__

#include <string>
#include <memory>
#include <cstdlib>
#include <cpprest/http_client.h>
#include <pplx/pplxtasks.h>
#include "EventData.hh"

namespace mdsd { namespace details
{

/// <summary>
/// This class implements functions to publish data to EventHub
/// service using https.
/// </summary>
class EventHubPublisher : public std::enable_shared_from_this<EventHubPublisher>
{
public:
    static std::shared_ptr<EventHubPublisher> create(
        const std::string & hostUrl,
        const std::string & eventHubUrl,
        const std::string & sasToken
        )
    {
        return std::shared_ptr<EventHubPublisher>(new  EventHubPublisher(hostUrl, eventHubUrl, sasToken));
    }

    virtual ~EventHubPublisher() {}

    EventHubPublisher(const EventHubPublisher &) = delete;
    EventHubPublisher(EventHubPublisher&&) = default;

    EventHubPublisher& operator=(EventHubPublisher&) = delete;
    EventHubPublisher& operator=(EventHubPublisher&&) = default;

    /// <summary>
    /// Publish the data to Event Hub service synchronously.
    /// Return true if success, false if any error.
    /// If input data is empty, drop it and return true.
    /// </summary>
    virtual bool Publish(const EventDataT & data);

    /// <summary>
    /// Publish the data to Event Hub service asynchronously.
    /// Return true if success, false if any error.
    /// If input data is empty, drop it and return true.
    /// </summary>
    virtual pplx::task<bool> PublishAsync(const EventDataT & data);

    /// <summary>
    /// Create http request for EventHub data uploading.
    /// Throw exception if any error for the input data.
    /// </summary>
    web::http::http_request CreateRequest(const EventDataT & data);

protected:
    EventHubPublisher(
        const std::string & hostUrl,
        const std::string & eventHubUrl,
        const std::string & sasToken);

private:
    void ResetClient();
    bool HandleServerResponse(const web::http::http_response & response, bool isFromAsync);
    bool HandleServerResponseAsync(pplx::task<web::http::http_response> responseTask);

private:
    std::string m_hostUrl;       // Event Hub host URL
    std::string m_eventHubUrl;   // Event Hub service URL
    std::string m_sasToken;      // Event Hub SAS token

    std::unique_ptr<web::http::client::http_client> m_httpclient;
    bool m_resetHttpClient;     // if true, reset the http client.
};

} // namespace details
} // namespace mdsd

#endif // __EVENTHUBPUBLISHER__HH__
