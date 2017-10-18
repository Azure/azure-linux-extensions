// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include <ostream>
#include <map>
#include "PublisherStatus.hh"

using namespace mdsd::details;

// To prevent static initialization order fiasco.
// see https://isocpp.org/wiki/faq/ctors#static-init-order-on-first-use
static std::map<PublisherStatus, std::string> & GetPublisherStatusMap()
{
    static auto enumMap = new std::map<PublisherStatus, std::string>(
    {
        { PublisherStatus::Idle, "Idle" },
        { PublisherStatus::PublicationSucceeded, "PublicationSucceeded" },
        { PublisherStatus::PublicationFailedWithUnknownReason, "PublicationFailedWithUnknownReason" },
        { PublisherStatus::PublicationFailedWithBadRequest, "PublicationFailedWithBadRequest" },
        { PublisherStatus::PublicationFailedWithAuthError, "PublicationFailedWithAuthError" },
        { PublisherStatus::PublicationFailedServerBusy, "PublicationFailedServerBusy" },
        { PublisherStatus::PublicationFailedThrottled, "PublicationFailedThrottled" }
    });
    return *enumMap;
}

std::ostream&
operator<<(
    std::ostream& os,
    PublisherStatus status
    )
{
    auto enumMap = GetPublisherStatusMap();
    auto iter = enumMap.find(status);
    if (iter == enumMap.end()) {
        os << "Unknown PublisherStatus";
    }
    else {
        os << iter->second;
    }

    return os;
}
