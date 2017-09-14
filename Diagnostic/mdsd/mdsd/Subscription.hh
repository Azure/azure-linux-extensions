// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _SUBSCRIPTION_HH_
#define _SUBSCRIPTION_HH_

#include <iostream>
#include "Priority.hh"
#include "MdsEntityName.hh"
#include "CanonicalEntity.hh"
#include "Pipeline.hh"
#include "ITask.hh"

class LocalSink;

class Subscription : public ITask
{
	friend std::ostream& operator<<(std::ostream& os, const Subscription& sub);

public:
	//Subscription(const std::string &ev, bool, const MdsdConfig*, const std::string &acct, StoreType::Type, Priority);
	Subscription(LocalSink *sink, const MdsEntityName& target, Priority, const MdsTime& interval);
	Subscription(LocalSink *sink, MdsEntityName&& target, Priority, const MdsTime& interval);
	~Subscription() { if (_head) delete _head; _head = nullptr; }

	void AddStage(PipeStage *stage);

	const MdsEntityName& target() const { return _target; }
	Priority priority() const { return _priority; }
	time_t Duration() const { return interval().to_time_t(); }

protected:
	// Returns the time at which the first call should be made
	MdsTime initial_start();

	// Invoked regularly to process data for the interval() seconds beginning at this time
	void execute(const MdsTime&);

private:
	Subscription();
	void common_constructor();

	LocalSink *_sink;
	const MdsEntityName _target;
	const Priority _priority;

	// Ingest processing pipeline. When the subscription is deleted, the destructor must tear
	// down the pipeline. The teardown is recursive; delete the head, and it'll delete its
	// successor before finishing up.
        PipeStage *_head;
        PipeStage *_tail;
};

std::ostream& operator<<(std::ostream& os, const Subscription& sub);

#endif // _SUBSCRIPTION_HH_

// vim: set ai sw=8 :
