// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once

#ifndef __ETWEVENT_HH__
#define __ETWEVENT_HH__

#include <string>
#include <unordered_map>
#include "EventJSON.hh"
#include "SchemaCache.hh"

class LocalSink;
class MdsValue;

/// This class implements functions to parse ETW JSON events. Each JSON message will
/// follow a format like below:
/// {"TAG":"<tag>",
/// "SOURCE":"ETW",
/// "EVENTID" : <id>,
/// "GUID" : "<guid>", // NOTE: there is no {} around <guid>
/// "DATA":[["name1","val1", "jsonType/mdsType"],["name2", "val2", "jsonType/mdsType"]]}

class EtwEvent
{
public:
    EtwEvent(EventJSON& event) : m_event(event) {}
    ~EtwEvent() {}

    /// <summary>
    /// Process current event. Create a new CanonicalEntity object with the event
    /// data. Then save the CanonicalEntity into the given sink.
    /// If there is any error with the event data, nothing will be saved to sink.
    /// </summary>
    /// <param name='sink'> Sink to save CanonicalEntity </param>
    void Process(LocalSink* sink);

    static const char* ETWName() { return s_ETWName; }
    static const char* GUIDName() { return s_GUIDName; }
    static const char* EventIDName() { return s_EventIdName; }

    /// <summary>
    /// Build and return a local table name given ETW GUID and EventID.
    /// </summary>
    static std::string BuildLocalTableName(const std::string & guid, int eventId)
    {
        return (std::string(s_ETWName) + "_" + guid + "_" + std::to_string(eventId));
    }

private:
    std::string ParseGuid();
    int ParseEventId();
    MdsValue* ConvertData(cJSON* item, std::string & name);
    bool GetJSONString(cJSON* obj, std::string& value);
    bool ValidateJSON(cJSON* obj, int expectedType);

    static SchemaCache::IdType GetSchemaId(const std::string & guidstr, int eventid);

private:
    EventJSON& m_event;

    // Each ETW guid/eventid should correspond to a specific schema
    static std::unordered_map<std::string, SchemaCache::IdType> m_schemaIdMap;

    constexpr static const char* s_ETWName = "ETW";
    constexpr static const char* s_GUIDName = "GUID";
    constexpr static const char* s_EventIdName = "EVENTID";
};


#endif // __ETWEVENT_HH__
