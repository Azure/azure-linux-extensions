// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _OMITASK_HH_
#define _OMITASK_HH_

#include <string>
#include <mutex>
#include <map>
#include <stddef.h>
#include <boost/asio.hpp>
#include <boost/bind.hpp>
#include "Priority.hh"
#include "MdsTime.hh"
#include "MdsEntityName.hh"
#include "StoreType.hh"
#include "Pipeline.hh"
#include "SchemaCache.hh"

class OMIQuery;
class MdsdConfig;

class OmiTask
{
public:
	OmiTask(MdsdConfig *config, const MdsEntityName& target, Priority prio, 
		const std::string& nmspc, const std::string& qry, time_t sampleRate);
	// I want a move constructor...
	OmiTask(OmiTask &&orig);
	// But do not want a copy constructor nor a default constructor
	OmiTask(OmiTask &) = delete;
	OmiTask() = delete;

	~OmiTask();

	// void AddUnpivot(const std::string &valueAttrName, const std::string &nameAttrName, const std::string &unpivotColumns);
	void AddStage(PipeStage *stage);
	void Start();
	void Cancel();

	const MdsEntityName & Target() const { return _target; }
	int FlushInterval() const { return _priority.Duration(); }
	static SchemaCache::IdType SchemaId(const std::string & ns, const std::string &qry);

private:
	MdsdConfig *_config;
	MdsEntityName _target;
	Priority _priority;
	std::string _namespace;
	std::string _query;
	time_t _sampleRate;
	size_t _retryCount;
	MdsTime _firstTimeTaskStartTried;

	std::mutex _mutex;
	boost::asio::deadline_timer _timer;
	boost::posix_time::ptime _nextTime;
	bool _cancelled;
	MdsTime _qibase;

	static std::map<std::string, SchemaCache::IdType> _qryToSchemaId;

	// You may wonder "why is this allocated on the heap?"
	// Earlier in development, mdsd used a glib-based XML parser which returned Glib::ustring objects
	// instead of std::string. Various configuration classes stored those ustring objects and thus needed
	// the Glib-2.0 headers, which #define TRUE and FALSE; so, unfortunately, do the OMI headers. The
	// easiest solution to the compiler whining was to keep the OMI headers out of the MdsdConfig headers.
	// Using a pointer let us achieve that isolation.
	// In December 2015 we removed all use of Glib, so this was no longer an issue. At the time we
	// made that change, we decided it was safer to leave this as-is and clean it up in a subsequent
	// refactoring pass.
	OMIQuery *_omiConn;

	PipeStage *_head;
	PipeStage *_tail;

	void TryToStartAndRetryIfFailed(const boost::system::error_code& error);
	void DoWork(const boost::system::error_code& error);
};

#endif // _OMITASK_HH_

// vim: se sw=8 :
