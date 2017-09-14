// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "ITask.hh"
#include "Logger.hh"
#include "Trace.hh"
#include <cpprest/pplx/threadpool.h>

ITask::ITask(const MdsTime &interval)
	: _interval(interval), _timer(crossplat::threadpool::shared_instance().service()), _cancelled(false)
{
	assert(interval != MdsTime(0));
	Trace trace(Trace::Scheduler, "ITask Constructor");
}

ITask::~ITask()
{
}

void
ITask::start()
{
	using namespace boost::posix_time;

	Trace trace(Trace::Scheduler, "ITask::Start");

	// Call subclass on_start() method. Last minute initialization happens there, and the subclass
	// can call the whole thing off by returning false.
	if (! on_start()) {
		Logger::LogError("Task refused startup");
		return;
	}

	MdsTime start { initial_start() };
	time_t spanSeconds = _interval.to_time_t();
	_intervalStart = start.Round(spanSeconds) - _interval;
	if (trace.IsActive()) {
		std::ostringstream msg;
		msg << this << " requested start@" << start << " for interval beginning at " << _intervalStart;
		msg << " of size " << spanSeconds << " seconds";
		trace.NOTE(msg.str());
	}
	_nextTime = start.to_ptime();
	_timer.expires_at(_nextTime);
	_timer.async_wait(boost::bind(&ITask::DoWork, this, boost::asio::placeholders::error));
}

void
ITask::cancel()
{
	Trace trace(Trace::Scheduler, "ITask::Cancel");
	if (_cancelled) {
		trace.NOTE("Already cancelled; ignoring");
		return;
	} else {
		std::lock_guard<std::mutex> lock(_mutex);
		_cancelled = true;
		_timer.cancel();
	}

	on_cancel();	// Called with mutex NOT locked
}

void
ITask::DoWork(const boost::system::error_code& error)
{
	Trace trace(Trace::Scheduler, "ITask::DoWork");
	MdsTime start { _intervalStart };

	if (error == boost::asio::error::operation_aborted) {
		// If the timer was cancelled, we have to assume the entire configuration may have been
		// deleted; don't touch it. When an MdsdConfig object is told to self-destruct, it first
		// cancels all timer-driven actions, then it waits some period of time, then it actually
		// deletes the object. When the timers are cancelled, the handlers are called with the
		// cancellation message. The MdsdConfig object is *probably* still valid, and as long
		// as the timer isn't rescheduled, all should be well. But I'm playing it safe here
		// and assuming an explicit cancel operation means "the config is gone".
		//
		// Of course, if the MdsdConfig is deleted, all the associated objects, including this
		// very ITask object, get deleted as well. Thus, the "don't touch nothin'" rule.
		trace.NOTE("Timer cancelled");
		return;
	} else {
		std::lock_guard<std::mutex> lock(_mutex);
		if (error || _cancelled) {
			return;
		}

		trace.NOTE("Rescheduling");
		_intervalStart += _interval;
		_nextTime = _nextTime + _interval.to_duration();
		_timer.expires_at(_nextTime);
		_timer.async_wait(boost::bind(&ITask::DoWork, this, boost::asio::placeholders::error));
	}

	// Note that, as written, we do NOT hold the lock here; our use of the class instance
	// needs to be readonly. If that changes, revisit this locking pattern.
	execute(start);
}

// vim: se sw=8 :
