// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "Trace.hh"
#include "Logger.hh"
#include <sstream>

Trace::Flags Trace::_interests = Trace::Flags::None;

Trace::Trace(Flags covers, const char *calling_fn)
	:  _covers(covers), _fn(calling_fn), _active((_interests & covers) != 0)
{
	if (_active) {
		Logger::LogInfo("Entering " + _fn);
	}
}

Trace::Trace(Flags covers, std::string calling_fn)
	:  _covers(covers), _fn(std::move(calling_fn)), _active((_interests & covers) != 0)
{
	if (_active) {
		Logger::LogInfo("Entering " + _fn);
	}
}

Trace::~Trace()
{
	if (_active) {
		Logger::LogInfo("Leaving " + _fn);
	}
}

void
Trace::Note(const char *filename, int lineno, const std::string& msg) const
{
    return Note(filename, lineno, msg, Type::INFO);
}

std::string
Trace::TruncateFilename(const std::string & filename)
{
	size_t slash = filename.find_last_of('/');
	if (slash == std::string::npos || slash <= 1) {
		return filename;
	}
	slash = filename.find_last_of('/', slash-1);
	if (slash == std::string::npos || slash == 0) {
		return filename;
	}
	return std::string("...").append(filename.substr(slash));
}

void
Trace::Note(const char *filename, int lineno, const std::string& msg, Type level) const
{
	if (_active) {
		std::ostringstream message;
		message << _fn << " (" << TruncateFilename(filename) << " +" << lineno << ") " << msg;
		if (level >= Type::INFO) {
		    Logger::LogInfo(message.str());
		}
		if (level >= Type::WARN) {
		    Logger::LogWarn(message.str());
		}
		if (level >= Type::ERROR) {
		    Logger::LogError(message.str());
		}
	}
}

Trace&
Trace::Prefix(const char * filename, int lineno, Trace::Type level = Trace::Type::INFO)
{
	if (IsActive()) {
		_msg << _fn << " (" << TruncateFilename(filename) << " +" << lineno << ") ";
		_level = level;
	}
	return *this;
}

bool
Trace::flush()
{
	if (IsActive()) {
		auto msg = _msg.str();
		Logger::LogInfo(msg);
		if (_level == Trace::Type::WARN) {
			Logger::LogWarn(msg);
		} else if (_level == Trace::Type::ERROR) {
			Logger::LogError(msg);
		}

		_msg.str("");
		_msg.clear();
		_level = Trace::Type::INFO;
	}
	return true;
}


// vim: se sw=8 :
