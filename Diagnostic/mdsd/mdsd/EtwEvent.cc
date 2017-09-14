// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "EtwEvent.hh"
#include "Logger.hh"
#include "Trace.hh"
#include "CanonicalEntity.hh"
#include "LocalSink.hh"
#include "MdsValue.hh"
#include "Engine.hh"

#include <sstream>

std::unordered_map<std::string, SchemaCache::IdType> EtwEvent::m_schemaIdMap;

void
EtwEvent::Process(LocalSink *sink)
{
    Trace trace(Trace::EventIngest, "EtwEvent::Process");
    if (!sink) {
        Logger::LogError("Error: unexpected NULL pointer for LocalSink.");
        return;
    }

    if (!m_event.IsEtwEvent()) {
        Logger::LogError("Error: the input event is not an ETW event. Do nothing.");
        return;
    }

    std::string guidstr = ParseGuid();
    if (guidstr.empty()) {
        return;
    }

    int eventId = ParseEventId();
    if (eventId < 0) {
        return;
    }

    unsigned int ncolumns = m_event.data_count() + 2;
    CanonicalEntity ce(ncolumns);
    ce.SetPreciseTime(m_event.GetTimestamp());

    auto schemaId = GetSchemaId(guidstr, eventId);
    ce.SetSchemaId(schemaId);

    bool hasError = false;

    auto datum = m_event.data_begin();
    while(datum != m_event.data_end()) {
        std::string name;
        auto mdsValue = ConvertData(&(*datum), name);
        if (!mdsValue) {
            hasError = true;
            break;
        }
        ce.AddColumn(name, mdsValue);
        ++datum;
    }
    if (!hasError) {
        sink->AddRow(ce, 0);
    }
}

// input cJSON is an array with 3 elements ["Name", "Value", "srctype/mdstype"]
MdsValue*
EtwEvent::ConvertData(cJSON* tuple, std::string & name)
{
    if (!ValidateJSON(tuple, cJSON_Array)) {
        return nullptr;
    }

    const int ETW_TUPLE_SIZE = 3;
    int arraySize = cJSON_GetArraySize(tuple);

    if (ETW_TUPLE_SIZE != arraySize) {
        std::ostringstream ss;
        ss << "Error: invalid data format: expected ETW tuple size=" << ETW_TUPLE_SIZE << "; actual size=" << arraySize;
        Logger::LogError(ss.str());
        return nullptr;
    }

    cJSON* head = tuple->child;
    if (!head || !GetJSONString(head, name)) {
        return nullptr;
    }
    head = head->next;

    cJSON * jvalue = head;
    if (!jvalue) {
        return nullptr;
    }

    head = head->next;
    std::string inOutType;
    if (!head || !GetJSONString(head, inOutType)) {
        return nullptr;
    }

    typeconverter_t converter;
    if (! Engine::GetEngine()->GetConverter(inOutType, converter)) {
        std::ostringstream ss;
        ss << "Error: failed to get type converter '" << inOutType << "'. Supported converters: " << Engine::ListConverters();
        Logger::LogError(ss.str());
        return nullptr;
    }

    return converter(jvalue);
}


std::string
EtwEvent::ParseGuid()
{
    std::string guidstr;
    if (!m_event.GetGuid(guidstr)) {
        std::ostringstream ss;
        ss << "Error: invalid event format: no expected '" << s_GUIDName << "' found. Do nothing.";
        Logger::LogError(ss.str());
        return std::string();
    }
    return guidstr;
}

int
EtwEvent::ParseEventId()
{
    int eventId = -1;
    if (!m_event.GetEventId(eventId)) {
        std::ostringstream ss;
        ss << "Error: invalid event format: no expected '" << s_EventIdName << "' found. Do nothing.";
        Logger::LogError(ss.str());
        return -1;
    }
    return eventId;
}

bool
EtwEvent::GetJSONString(cJSON* obj, std::string& value)
{
    if (!ValidateJSON(obj, cJSON_String)) {
        return false;
    }
    value.assign(obj->valuestring);
    return true;
}

bool
EtwEvent::ValidateJSON(cJSON* obj, int expectedType)
{
    if (!obj) {
        Logger::LogError("Error: unexpected NULL pointer for cJSON object.");
        return false;
    }
    if (expectedType != obj->type) {
        std::ostringstream ss;
        ss << "Error: cJSON type: expected=" << expectedType << "; actual=" << obj->type << ".";
        Logger::LogError(ss.str());
        return false;
    }
    return true;
}

SchemaCache::IdType
EtwEvent::GetSchemaId(const std::string & guidstr, int eventid)
{
    auto key = guidstr + std::to_string(eventid);

    const auto & iter = m_schemaIdMap.find(key);
    if (iter == m_schemaIdMap.end()) {
        auto id = SchemaCache::Get().GetId();
        m_schemaIdMap[key] = id;
        return id;
    }
    else {
        return iter->second;
    }
}
