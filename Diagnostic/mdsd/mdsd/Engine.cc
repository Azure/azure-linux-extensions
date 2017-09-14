// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "Engine.hh"
#include <iostream>
#include <cstdlib>
#include <ctime>
#include <cmath>
#include <functional>
#include <sstream>

#include "MdsValue.hh"
#include "TableSchema.hh"
#include "MdsdConfig.hh"
#include "Credentials.hh"
#include "EventJSON.hh"
#include "CanonicalEntity.hh"
#include "OmiTask.hh"
#include "Trace.hh"
#include "LocalSink.hh"
#include "EtwEvent.hh"
#include "Utility.hh"
#include "EventHubUploaderMgr.hh"

using std::string;

Engine::Engine() : blackholeEvents(false), _startTime(time(0)), current_config(nullptr)
{
}

Engine::~Engine() {
}

Engine* Engine::engine = 0;

void
Engine::SetConfiguration(MdsdConfig* newconfig)
{
	Trace trace(Trace::ConfigLoad, "Engine::SetConfiguration");
	
	Engine *current = Engine::GetEngine();

	static std::mutex mtx;
	std::unique_lock<std::mutex> lock(mtx);
	MdsdConfig *prev_config = current->current_config;
	current->current_config = newconfig;
	lock.unlock();

	//current->PushSchemas(newconfig);
	newconfig->Initialize();

	newconfig->StartScheduledTasks();

	if (prev_config) {
		prev_config->SelfDestruct(900);		// Old config will delete itself in 900 seconds
	}
}

#ifdef DOING_MEMCHECK
void
Engine::ClearConfiguration()
{
	current_config->StopScheduledTasks();
	delete current_config;
	current_config = nullptr;
}
#endif

void
Engine::ProcessEvent(EventJSON& event)
{
	Trace trace(Trace::EventIngest, "Engine::ProcessEvent");

	// Grab the config pointer at the beginning of processing; if the config gets
	// swapped while we're working, we won't care. The engine is careful to hold on
	// to previous MdsdConfig objects for a lengthy period of time after they're
	// swapped out.
	MdsdConfig* Config = GetConfig();

	if (blackholeEvents) {
		return;
	}

	// Actual processing goes here
	// Listener() did basic validation before calling ProcessEvent()
	string Source(event.GetSource());

	auto sink = LocalSink::Lookup(Source);
	if (!sink) {
		Logger::LogWarn("Received an event from source \"" + Source + "\" not used elsewhere in the active configuration");
		return;
	}

	if (event.IsEtwEvent()) {
		EtwEvent etwevt(event);
		etwevt.Process(sink);
		return;
	}

	TableSchema* Schema = Config->GetSchema(Source);
	if (!Schema) {
		Logger::LogWarn("Received an event from source \"" + Source + "\" with no defined schema.");
		return;
	}

	// Build the CanonicalEntity to hold this event by running through the elements of the input event
	// and using the metadata in the schema to add columns
	auto ce = std::make_shared<CanonicalEntity>( Schema->Size() );
	ce->SetPreciseTime(event.GetTimestamp());
	ce->SetSchemaId(sink->SchemaId());
	auto datum = event.data_begin();
	TableSchema::const_iterator iter = Schema->begin();
	while (datum != event.data_end() && iter != Schema->end()) {
		auto value = (*iter)->Convert(&(*datum));
		if (!value) {
			std::ostringstream msg;
			msg << "Bad event (source " << Source << ", schema " << Schema->Name() << "): couldn't convert value for ";
			msg << (*iter)->Name(); msg << " to " << (*iter)->MdsType();
			msg << ". Raw event: " << event;
			Logger::LogError(msg.str());
			return;
		}
		ce->AddColumn((*iter)->Name(), value);
		++datum;
		++iter;
	}
	if (datum != event.data_end() || iter != Schema->end()) {
		std::stringstream msg;
		msg << "Event from source '" << Source << "' contained unexpected number of columns. ";
		msg << Source << " has " << event.data_count() << "; ";
		msg << "Schema '" << Schema->Name() << "' has " << Schema->Size() << ".";
		Logger::LogError(msg.str());
	} else {
		// Add the CanonicalEntity object to the sink we found (above).
		sink->AddRow(ce);
	}
}

Engine*
Engine::GetEngine()
{
	if (!engine) {
		engine = new Engine();
	}
	return engine;
}

bool
Engine::GetConverter(const string& sourcetype, const string& targettype, typeconverter_t& converter)
{
	std::string inOutType;
	inOutType.reserve(sourcetype.size() + 1 + targettype.size());
	inOutType.append(sourcetype);
	inOutType.append(1, '/');
	inOutType.append(targettype);
	return GetConverter(inOutType, converter);
}

bool
Engine::GetConverter(const std::string & inOutType, typeconverter_t& converter)
{
	auto iter = convertermap.find(inOutType);
	if (iter == convertermap.end()) {
		return false;
	}
	converter = iter->second;
	return true;
}

std::string
Engine::ListConverters()
{
	std::ostringstream msg;
	bool isFirst = true;

	for (const auto& item : convertermap) {
		if (isFirst) {
			isFirst = false;
		} else {
			msg << " ";
		}
		msg << "'" << item.first << "'";
	}

	return msg.str();
}

std::map<std::string, typeconverter_t > Engine::convertermap = {
	{ "bool/mt:bool", [](cJSON * src) -> MdsValue* {
			if (src->type == cJSON_False) return new MdsValue(false);
			if (src->type == cJSON_True) return new MdsValue(true);
			return 0;
		}
	},
	{ "str/mt:bool", [](cJSON * src) -> MdsValue* {
		if (cJSON_String == src->type && src->valuestring) {
			bool b = MdsdUtil::to_bool(src->valuestring);
			return new MdsValue(b);
		}
		return nullptr;
	}
	},
	{ "str/mt:wstr", [](cJSON * src) -> MdsValue* {
		return (src->type == cJSON_String) ? ( new MdsValue(src->valuestring)) : 0;
	}
	}, 
	{ "double/mt:float64", [](cJSON * src) -> MdsValue* {
		return (src->type == cJSON_Number) ? ( new MdsValue(src->valuedouble)) : 0;
	}
	},
	{ "str/mt:float64", [](cJSON * src) -> MdsValue* {
		if (cJSON_String == src->type && src->valuestring) {
			return new MdsValue(atof(src->valuestring));
		}
		return nullptr;
	}
	},
	{ "int/mt:int32", [](cJSON * src) -> MdsValue* {
		return (src->type == cJSON_Number) ? ( new MdsValue(long(src->valueint))) : 0;
	}
	},
	{ "str/mt:int32", [](cJSON * src) -> MdsValue* {
		return (src->type == cJSON_String) ? ( new MdsValue(atol(src->valuestring))) : 0;
	}
	},
	{ "int/mt:int64", [](cJSON * src) -> MdsValue* {
		return (src->type == cJSON_Number) ? ( new MdsValue(src->valueint)) : 0;
	}
	},
	{ "str/mt:int64", [](cJSON * src) -> MdsValue* {
		return (src->type == cJSON_String) ? ( new MdsValue(strtoll(src->valuestring, NULL, 10))) : 0;
	}
	},
	{ "int-timet/mt:utc", [](cJSON * src) -> MdsValue* {
		return MdsValue::time_t_to_utc(src); 
	}
	},
	{ "double-timet/mt:utc", [](cJSON * src) -> MdsValue* {
		return MdsValue::double_time_t_to_utc(src);
	}
	},
	{ "str-rfc3339/mt:utc", [](cJSON * src) -> MdsValue* {
		return MdsValue::rfc3339_to_utc(src);
	}
	}

};

// vim: se sw=8 :
