// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _TRACE_HH_
#define _TRACE_HH_

#include <string>
#include <sstream>

#define NOTE(MSG) Note(__FILE__, __LINE__, MSG)
#define NOTEWARN(MSG) Note(__FILE__, __LINE__, MSG, Trace::Type::WARN)
#define NOTEERR(MSG) Note(__FILE__, __LINE__, MSG, Trace::Type::ERROR)

#define TRACEINFO(trace,body) trace.IsActive() && (trace.Prefix(__FILE__, __LINE__, Trace::Type::INFO) << body).flush()
#define TRACEWARN(trace,body) trace.IsActive() && (trace.Prefix(__FILE__, __LINE__, Trace::Type::WARN) << body).flush()
#define TRACEERROR(trace,body) trace.IsActive() && (trace.Prefix(__FILE__, __LINE__, Trace::Type::ERROR) << body).flush()

class Trace
{
public:
	enum Flags
	{
		None= 0, ConfigLoad=1, EventIngest=2, CanonicalEvent=4,
		Batching=8, XTable=0x10, Scheduler=0x20, OMIIngest=0x40, Credentials=0x80,
		Daemon = 0x100, ConfigUse=0x200, SignalHandlers=0x400, EntityName=0x800,
		QueryPipe = 0x1000, Local = 0x2000, DerivedEvent = 0x4000,
		Extensions = 0x8000, AppInsights = 0x10000, MdsCmd = 0x20000,
		Bond = 0x40000, SchemaCache = 0x80000, BondDetails = 0x100000,
		IngestContents = 0x200000, JsonBlob = 0x400000
	};

	enum Type {INFO, WARN, ERROR};

	Trace(Flags trace_level, const char * calling_fn);
	Trace(Flags trace_level, std::string calling_fn);
	~Trace();

	void Note(const char * filename, int lineno, const std::string& msg) const;
	void Note(const char * filename, int lineno, const std::string& msg, Type level) const;
	bool IsActive() const { return _active; }
	bool IsAlsoActive(Flags flags) const { return (flags & _interests) == flags; }
	Flags Covers() const { return _covers; }

	// Pushes the tracing line prefix into the accumulated message
	Trace& Prefix(const char * filename, int lineno, Type level);
	// Adds the item to the stream holding the accumulated message
	template <typename T> friend Trace& operator<<(Trace& trace, const T & item)
	{
		if (trace.IsActive()) { trace._msg << item; } return trace;
	}

	bool flush();

	static std::string TruncateFilename(const std::string&);
	static void SetInterests(Flags flags) { _interests = flags; }
#define SCUI(foo) static_cast<unsigned int>(foo)
	static void AddInterests(Flags flags) { _interests = static_cast<Flags>(SCUI(_interests) | SCUI(flags)); }
#undef SCUI

private:
	Flags _covers;
	std::string _fn;
	bool _active;			// True if the calling function covers any of the tasks of interest

	std::ostringstream _msg;	// Accumulates a trace message
	Type _level;			// The severity level of the message being accumulated

	static Flags _interests;
};

#endif // _TRACE_HH_

// vim: set tabstop=4 softtabstop=4 shiftwidth=4 noexpandtab :
