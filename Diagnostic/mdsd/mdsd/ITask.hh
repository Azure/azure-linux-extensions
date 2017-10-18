// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _ITASK_HH_
#define _ITASK_HH_

#include <mutex>
#include <stddef.h>
#include <boost/asio.hpp>
#include <boost/bind.hpp>
#include "MdsTime.hh"

class MdsdConfig;

// Interface for regularly-scheduled tasks. When an ITask is created, the interval at which it should be
// executed is set. Once the ITask::start() method is invoked, a timer is set to cause the virtual ITask::on_start()
// method to be invoked at the requested frequency (every _interval seconds), until the ITask::cancel() method
// is invoked.
class ITask
{
public:
	// Task should run every _interval_ seconds
	ITask(const MdsTime &interval);
	// I want a move constructor...
	ITask(ITask &&orig);
	// But do not want a copy constructor nor a default constructor
	ITask(ITask &) = delete;
	ITask() = delete;

	virtual ~ITask();

	// Requests that this repeating task be scheduled for execution
	void start();

	// Requests that the task be stopped. Any execution already in progress (or for which the timer has already
	// tripped but execution still awaits scheduling on a thread) will take place, but the _cancelled boolean
	// can be observed.
	//
	// Once cancelled(), a task cannot be restarted; that is, you cannot call start() again. You must instead
	// create a new instance of the task object. This is due to the boost deadline timer not being restartable,
	// which itself arises from enabling cancellation in the first place, near as I can tell.
	void cancel();

	MdsTime interval() const { return _interval; }

protected:
	// Subclasses *must* override the execute() method, which is called to perform the actual
	// time-scheduled class.
	virtual void execute(const MdsTime&) = 0;

	// Subclass gets notified via this callout when start() is called. If the subclass returns false,
	// the start operation aborts. In this case, start() can be called again; a failed startup is different
	// from a successful start followed by a cancel().
	virtual bool on_start() { return true; }

	// Subclass gets notified when cancel() is called.
	virtual void on_cancel() { }

	// When start() is called, a time for the initial task invocation must be determined.
	// By default, wait 2-7 second; the randomness prevents all the tasks from being started
	// at the same time when running through all tasks scheduled for a given config. Any
	// derived class can override this function, e.g. if the task needs to run within 5 seconds
	// of the beginning of the next "interval".
	virtual MdsTime initial_start() { return MdsTime::Now() + MdsTime(2 + random()%5, random()%1000000); }

	// Subclass can check to see if cancellation has been requested
	bool is_cancelled() { return _cancelled; }

private:
	MdsTime _interval;

	std::mutex _mutex;
	boost::asio::deadline_timer _timer;
	boost::posix_time::ptime _nextTime;
	bool _cancelled;
	MdsTime _intervalStart;

	void DoWork(const boost::system::error_code& error);
};

#endif // _ITASK_HH_

// vim: se sw=8 :
