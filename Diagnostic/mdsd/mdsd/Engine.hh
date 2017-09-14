// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _ENGINE_HH_
#define _ENGINE_HH_

#include <map>
#include <string>
#include <functional>
#include <set>
#include <utility>
#include <mutex>
#include "MdsValue.hh"
#include "EventJSON.hh"
#include "MdsSchemaMetadata.hh"
#include "MdsEntityName.hh"

class MdsdConfig;
class Credentials;

class Engine
{
public:
	~Engine();

	/// <summary>
	/// Get the singleton Engine instance. Not thread-safe for creation.
	/// </summary>
	static Engine* GetEngine();

	/// <summary>Cause incoming events to be blackholed instead of being sent to MDS</summary>
	void BlackholeEvents() { blackholeEvents = true; }

	/// <summary>Process an event</summary>
	/// <param name="event">The event to be processed</param>
	void ProcessEvent(EventJSON& event);

	/// <summary>
	/// Transfer a configuration into the active engine. The previous configuration will remain undeleted
	/// for a time; when the engine believes it's no longer in use, the engine will delete it.
	/// </summary>
	/// <param name="newconfig">The new configuration object.</param>
	static void SetConfiguration(MdsdConfig* newconfig);

	/// <summary>Fetch type converter. Returns false if sourcetype can't be converted to targettype</summary>
	/// <param name="sourcetype">Name of the original (JSON) type (e.g. "str", "int-timet")</param>
	/// <param name="targettype">Name of the destination (MDS) type (e.g. "mt_bool")</param>
	/// <param name="converter">The type converter function, if one was found</param>
	bool GetConverter(const std::string& sourcetype, const std::string& targettype, typeconverter_t& converter);

	/// <summary>Fetch type converter. Return false if inOutType cannot be found.</summary>
	/// <param name="inOutType">Name pairs in the format of "jsonType/mdsType". (e.g. "bool/mt:bool") </param>
	/// <param name="converter">The type converter function, if one was found</param>
	bool GetConverter(const std::string & inOutType, typeconverter_t& converter);

	/// <summary>Get a list of all configured type converters, suitable for display in error messages.</summary>
	static std::string ListConverters();

	MdsdConfig* GetConfig() { return current_config; }

	/// <summary>Determines if the schema has been pushed for this account and tablename. Calling this
	/// method updates the cache of which schemas have been pushed.</summary>
	/// <return>True if this is the first time NeedsPush has been called with these args.</return>
	//bool NeedsPush(Credentials* creds, const MdsEntityName& target, const MdsSchemaMetadata*);

#ifdef DOING_MEMCHECK
	void ClearPushedCache() { std::unique_lock<std::mutex> lock(_schemaCacheMutex);_pushedEvents.clear(); }
	void ClearConfiguration();
#endif

private:
	Engine();

	static Engine* engine;
	bool blackholeEvents;
	time_t _startTime;

	MdsdConfig* current_config;

	static std::map<std::string, typeconverter_t > convertermap;

	std::set<std::pair<const std::string, const MdsSchemaMetadata *> > _pushedEvents;
	std::mutex _schemaCacheMutex;
};

#endif //_ENGINE_HH_

// vim: se sw=8 :
