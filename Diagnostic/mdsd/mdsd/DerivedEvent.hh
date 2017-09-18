// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _DERIVEDEVENT_HH_
#define _DERIVEDEVENT_HH_

#include "ITask.hh"
#include "MdsEntityName.hh"
#include "Priority.hh"

class MdsdConfig;
class PipeStage;
class LocalSink;

class DerivedEvent : public ITask
{
public:
	DerivedEvent(MdsdConfig * config, const MdsEntityName &target, Priority prio, const MdsTime &interval,
		std::string source);
	// I want a move constructor...
	DerivedEvent(DerivedEvent &&orig);
	// But do not want a copy constructor nor a default constructor
	DerivedEvent(DerivedEvent &) = delete;
	DerivedEvent() = delete;

	virtual ~DerivedEvent();

	const MdsEntityName & Target() const { return _target; }
	int FlushInterval() const { return _prio.Duration(); }
	void AddStage(PipeStage *);

protected:
	// Subclasses *must* override the execute() method, which is called to perform the actual
	// time-scheduled class.
	virtual void execute(const MdsTime&);

#if 0
// Dunno if I need these....

	// Subclass gets notified via this callout when start() is called. If the subclass returns false,
	// the start operation aborts. In this case, start() can be called again; a failed startup is different
	// from a successful start followed by a cancel().
	virtual bool on_start() { return true; }

	// Subclass gets notified when cancel() is called.
	virtual void on_cancel() { }
#endif

	// We'll want the initial start time to be shortly after the end of the next "interval".
	// We'll add some hysteresis to that start time.
	virtual MdsTime initial_start();

private:
	MdsdConfig *_config;
	MdsEntityName _target;
	Priority _prio;
	LocalSink *_localSink;

	PipeStage *_head;
	PipeStage *_tail;
};

#endif // _DERIVEDEVENT_HH_

// vim: se sw=8 :
