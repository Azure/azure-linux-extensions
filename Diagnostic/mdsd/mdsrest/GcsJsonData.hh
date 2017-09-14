// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef __GCSJSONDATA_HH__
#define __GCSJSONDATA_HH__

#include <string>
#include <vector>
#include <unordered_map>
#include <sstream>
#include <functional>
#include <cpprest/json.h>
#include "GcsJsonParser.hh"

namespace mdsd {

template<typename T>
using itemparser_t = std::function<void (const std::string & name, const web::json::value & jsonObj, T& result)>;

struct EventHubKey
{
    std::string SasKey;
    std::string Uri;

    bool IsValid() const { return !SasKey.empty() && !Uri.empty(); }

    static std::unordered_map<std::string, itemparser_t<EventHubKey>> ParserMap;
};

std::ostream& operator<<(std::ostream & os, const EventHubKey& obj);

struct ServiceBusAccountKey
{
    std::string AccountGroupName;   // Geneva moniker name
    std::string AccountMonikerName; // Mapped moniker name

    // This map stores all EventHub Keys.
    // map key: Event Hub name. In GCS, each name is a hard-coded name for
    // different scenario:
    // "raw" -> Event Hub notification for CentralBond store type.,
    // "error" -> Top N service.
    // "distributedtracing" -> Distributed tracing service.
    // "eventpublisher" -> Event Hub data publisher.
    std::unordered_map<std::string, EventHubKey> EventHubKeys;

    bool IsValid() const;

    using parser_type = details::JsonObjectParser<ServiceBusAccountKey>;
    static std::unordered_map<std::string, itemparser_t<ServiceBusAccountKey>> ParserMap;
};

std::ostream& operator<<(std::ostream & os, const ServiceBusAccountKey& obj);

struct StorageSasKey
{
    std::string ResourceName;
    std::string SasKey;
    std::string SasKeyType;

    bool IsValid() const { return !ResourceName.empty() && !SasKey.empty() && !SasKeyType.empty(); }

    using parser_type = details::JsonObjectParser<StorageSasKey>;
    static std::unordered_map<std::string, itemparser_t<StorageSasKey>> ParserMap;
};

std::ostream& operator<<(std::ostream & os, const StorageSasKey& obj);

struct StorageAccountKey
{
    std::string StorageAccountName;
    std::string AccountGroupName;
    std::string AccountMonikerName;
    std::string BlobEndpoint;
    std::string QueueEndpoint;
    std::string TableEndpoint;
    std::vector<StorageSasKey> SasKeys;

    bool IsValid() const;

    using parser_type = details::JsonObjectParser<StorageAccountKey>;
    static std::unordered_map<std::string, itemparser_t<StorageAccountKey>> ParserMap;
};

std::ostream& operator<<(std::ostream & os, const StorageAccountKey& obj);


// GcsAccount contains GCS account data. Its tagId should never be empty.
// Its other values can be of two kinds:
// 1) none of the values are empty.
// 2) all the values are empty.
struct GcsAccount
{
    std::vector<std::string> MaSigningPublicKeys;
    std::string SasKeysExpireTimeUtc;
    std::vector<ServiceBusAccountKey> ServiceBusAccountKeys;
    std::vector<StorageAccountKey> StorageAccountKeys;
    std::string TagId;

    bool IsValid() const;

    // Return true if all values (ignoring TagId) are empty; return false otherwise.
    bool IsEmpty() const;

    static std::unordered_map<std::string, itemparser_t<GcsAccount>> ParserMap;
};

std::ostream& operator<<(std::ostream & os, const GcsAccount& obj);

}

#endif // __GCSJSONDATA_HH__
