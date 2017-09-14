// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "EventHubType.hh"
#include <map>
#include <stdexcept>

static std::map<mdsd::EventHubType, std::string> & GetType2NameMap()
{
    static auto m = new std::map<mdsd::EventHubType, std::string> (
    {
        { mdsd::EventHubType::Notice, "EventNotice" },
        { mdsd::EventHubType::Publish, "EventPublish" }
    });
    return *m;
}

std::string
mdsd::EventHubTypeToStr(EventHubType type)
{
    auto m = GetType2NameMap();
    auto iter = m.find(type);
    if (iter != m.end()) {
        return iter->second;
    }
    return "unknown";
}

static std::map<std::string, mdsd::EventHubType> & GetName2TypeMap()
{
    static auto m = new std::map<std::string, mdsd::EventHubType>(
    {
        { "EventNotice", mdsd::EventHubType::Notice },
        { "EventPublish", mdsd::EventHubType::Publish }
    });
    return *m;
}

mdsd::EventHubType
mdsd::EventHubTypeFromStr(const std::string & s)
{
    auto m = GetName2TypeMap();
    auto iter = m.find(s);
    if (iter != m.end()) {
        return iter->second;
    }
    throw std::runtime_error("Invalid EventHubType name: " + s);
}
