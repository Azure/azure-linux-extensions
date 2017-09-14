// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#ifndef _LISTENER_HH_
#define _LISTENER_HH_

#include "Logger.hh"
//#include "PoolMgmt.hh"
#include <string>
#include <ctime>
#include <unordered_set>
#include <stddef.h>
#include <boost/asio.hpp>
#include <boost/bind.hpp>
#include <exception>
#include <memory>

extern "C" {
#include "cJSON.h"
}

// Instances of Listener (and derived classes) *must* be referenced via shared_ptr. The thread startproc
// and timerhandler functions race to be the last one with a pointer to the instance once ProcessLoop()
// returns, and it's not even the timerhandler that holds the last pointer; it's boost::deadline_timer that
// is often the last holder. We need to ensure the _timer object remains valid until deadline_timer lets
// go of it.
class Listener
{
private:
	typedef std::unordered_set<std::string> tag_set;
	typedef enum { rotate, cleanup } TimerTask;

	Listener(const Listener&) = delete;		// Do not define; copy construction forbidden
	Listener& operator=(const Listener &) = delete;	// Ditto for assignment
	void Shutdown();

	void LogBadJSON(cJSON* event, const std::string&);
	bool IsNewTag(cJSON* jsTAG);
	void EchoTag(char* tag);
	void DumpBuffer(std::ostream& os, const char* start, const char* end);
	void RotateTagSets();
	void ScrubTagSets();
	bool TryParseEvent(cJSON* event);
	bool TryParseEcho(cJSON* event);

	int clientfd;
	tag_set *tagsAgedOut;
	tag_set *tagsOldest;
	tag_set *tagsOld;
	tag_set *tagsCurr;

	static unsigned int checkpointSeconds;

	boost::asio::deadline_timer _timer;
	boost::asio::deadline_timer& Timer() { return _timer; }
	static void timerhandler(std::shared_ptr<Listener>, TimerTask);

	bool _finished;
	std::string _name;

protected:
	const char * ParseBuffer(const char* start, const char* end);
	int fd() const { return clientfd; }

public:
	Listener(int fd);
	virtual ~Listener();

	virtual void * ProcessLoop() { Logger::LogError("Listener::ProcessLoop() was called"); return 0; }

	static void * handler(void *);	// Thread proc for all listeners

	bool IsFinished() const { return _finished; }
	const std::string& Name() const { return _name; }

	static void setDupeWindow(unsigned long seconds) { checkpointSeconds = seconds / 2; }

	class exception : public std::exception
	{
	public:
		exception(const std::string & msg) : std::exception(), _what(msg) {}
		exception(const std::ostringstream &msg) : std::exception(), _what(msg.str()) {}
		exception(const char * msg) : std::exception(), _what(msg) {}

		virtual const char * what() const noexcept { return _what.c_str(); }
	private:
		std::string _what;
	};
};

// vim: set ai sw=8:
#endif // _LISTENER_HH_
