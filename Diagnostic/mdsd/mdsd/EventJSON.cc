// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "EventJSON.hh"
#include <cstdio>
extern "C" {
#include <sys/time.h>
}
#include "EtwEvent.hh"
#include "Logger.hh"

using std::string;

bool
EventJSON::GetSource(string& value)
{
	cJSON* item = cJSON_GetObjectItem(_event, "SOURCE");
	if (!ValidateJSON("SOURCE", item, cJSON_String)) {
		return false;
	} else {
		value.assign(item->valuestring);

		if (value == EtwEvent::ETWName()) {
			if (!GetEtwEventSource(value)) {
				return false;
			}
			_isEtwEvent = true;
		}
		return true;
	}
}

string
EventJSON::GetSource()
{
	cJSON* item = cJSON_GetObjectItem(_event, "SOURCE");
	if (!ValidateJSON("SOURCE", item, cJSON_String)) {
		return std::string("");
	} else {
		std::string source = std::string(item->valuestring);
		if (source == EtwEvent::ETWName()) {
			if (!GetEtwEventSource(source)) {
				return source;
			}
			_isEtwEvent = true;
		}
		return source;
	}
}

bool
EventJSON::GetGuid(std::string& value)
{
	cJSON* guid = cJSON_GetObjectItem(_event, EtwEvent::GUIDName());
	if (!ValidateJSON(EtwEvent::GUIDName(), guid, cJSON_String)) {
		return false;
	}
	value.assign(guid->valuestring);
	return true;
}

bool
EventJSON::GetEventId(int & eventId)
{
	cJSON* obj = cJSON_GetObjectItem(_event, EtwEvent::EventIDName());
	if (!ValidateJSON(EtwEvent::EventIDName(), obj, cJSON_Number)) {
		return false;
	}
	eventId = obj->valueint;
	return true;
}

bool
EventJSON::GetEtwEventSource(std::string& value)
{
	std::string guidstr;
	int eventId = -1;
	if (!GetGuid(guidstr) || !GetEventId(eventId)) {
		return false;
	}
	value = EtwEvent::BuildLocalTableName(guidstr, eventId);
	return true;
}

bool
EventJSON::GetTag(string& value)
{
	cJSON* item = cJSON_GetObjectItem(_event, "TAG");
	if (!ValidateJSON("TAG", item, cJSON_String)) {
		return false;
	} else {
		value.assign(item->valuestring);
		return true;
	}
}

bool
EventJSON::ValidateJSON(const char* name, cJSON* obj, int expectedType)
{
    if (!obj) {
        Logger::LogError("Error: unexpected NULL pointer for cJSON object.");
        return false;
    }
    if (expectedType != obj->type) {
        std::ostringstream ss;
        ss << "Error: ";
        if (name) {
            ss << "'" << name << "' ";
        }
        ss << "JSON type: expected=" << expectedType << "; actual=" << obj->type << ".";
        Logger::LogError(ss.str());
        return false;
    }
    return true;
}


EventJSON::DataIterator
EventJSON::data_begin()
{
	cJSON* array = cJSON_GetObjectItem(_event, "DATA");
	if (!array || !(array->child)) {
		return EventJSON::DataIterator((cJSON*)0);
	} else {
		return EventJSON::DataIterator(array->child);
	}
}

unsigned int
EventJSON::data_count()
{
	cJSON* array = cJSON_GetObjectItem(_event, "DATA");
	if (array) {
		return cJSON_GetArraySize(array);
	} else {
		return 0;
	}
}

std::ostream&
operator<<(std::ostream& os, const EventJSON& ev)
{
	char *buf = cJSON_Print(ev._event);
	os << (const char*)buf;
	free(buf);
	return os;
}

// vim: se sw=8:
