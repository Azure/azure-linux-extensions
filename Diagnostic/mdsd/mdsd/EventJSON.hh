// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _EVENTCJSON_HH_
#define _EVENTCJSON_HH_

#include <iterator>
#include <string>
#include "Logger.hh"
#include "MdsTime.hh"

extern "C" {
#include "cJSON.h"
}
#include <cstdlib>

class EventJSON
{
public:
	EventJSON(cJSON* event) : _event(event), _isEtwEvent(false) {}
	void PrintEvent() { char *buf = cJSON_Print(_event); Logger::LogInfo(buf); free(buf); }
	bool GetSource(std::string& source);
	std::string GetSource();
	bool GetTag(std::string& tag);
	const MdsTime& GetTimestamp() const { return _timestamp; }

	bool GetGuid(std::string& guid);
	bool GetEventId(int & eventId);
	bool IsEtwEvent() const { return _isEtwEvent; }

	class DataIterator : public std::iterator<std::input_iterator_tag, cJSON*>
	{
	private:
		cJSON* _current;

	public:
		DataIterator(cJSON* item) : _current(item) {}
		DataIterator(const DataIterator& other) : _current(other._current) {}
		DataIterator& operator++() { _current = _current->next;	return *this; }
		DataIterator operator++(int) { DataIterator tmp(*this); operator++(); return tmp; }
		bool operator==(const DataIterator& other) { return _current == other._current; }
		bool operator!=(const DataIterator& other) { return _current != other._current; }
		cJSON& operator*() { return *_current; }
		cJSON* operator->() { return _current; }
	};

	DataIterator data_begin();
	DataIterator data_end() { return DataIterator((cJSON*)0); }
	unsigned int data_count();

	friend std::ostream& operator<<(std::ostream& os, const EventJSON& ev);

private:
	EventJSON();

	bool GetEtwEventSource(std::string& value);
	bool ValidateJSON(const char* name, cJSON* obj, int expectedType);

	cJSON* _event;
	MdsTime _timestamp;
	bool _isEtwEvent;
};

#endif //_EVENTCJSON_HH_

// vim: se sw=8:
