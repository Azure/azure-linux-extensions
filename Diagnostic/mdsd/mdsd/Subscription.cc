// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "Subscription.hh"
#include "Batch.hh"
#include "Credentials.hh"
#include "MdsEntityName.hh"
#include "PipeStages.hh"
#include "LocalSink.hh"
#include "Trace.hh"

Subscription::Subscription(LocalSink *sink, const MdsEntityName &target, Priority pr, const MdsTime& interval)
	: ITask(interval), _sink(sink), _target(target), _priority(pr), _head(nullptr), _tail(nullptr)
{
	Trace trace(Trace::ConfigLoad, "Subscription constructor(table ref)");

	common_constructor();
}

Subscription::Subscription(LocalSink *sink, MdsEntityName &&target, Priority pr, const MdsTime& interval)
	: ITask(interval), _sink(sink), _target(target), _priority(pr), _head(nullptr), _tail(nullptr)
{
	Trace trace(Trace::ConfigLoad, "Subscription constructor(table move)");

	common_constructor();
}

void
Subscription::common_constructor()
{
	Trace trace(Trace::ConfigLoad, "Subscription common constructor path");

	_sink->SetRetentionPeriod(interval());

	if (trace.IsActive()) {
		std::ostringstream msg;
		msg << "Retention period " << _sink->RetentionSeconds();
		trace.NOTE(msg.str());
	}

}

// Initial start time is a few seconds past the end of the current interval
MdsTime
Subscription::initial_start()
{
        Trace trace(Trace::EventIngest, "Subscription::initial_start");

        MdsTime start;  // Default constructor sets it to "now"

        start += interval();
        start = start.Round(interval().to_time_t());
        start += MdsTime(2 + random()%5, random()%1000000);

        if (trace.IsActive()) {
                std::ostringstream msg;
                msg << "Initial time for event: " << start;
                trace.NOTE(msg.str());
        }

        return start;
}

void
Subscription::AddStage(PipeStage *stage)
{
        if (! _tail) {
                // This is the first stage in the pipeline; set the head to point here
                _head = stage;
        } else {
                // There's already a pipeline; make the old tail point to the newly-added stage
                _tail->AddSuccessor(stage);
        }
        // Either way, we have a new tail in the pipeline
        _tail = stage;
}

// Pull everything in the sink on the interval [start, start+duration)
// For each event, call _head->Process(new CanonicalEntity(event))
void
Subscription::execute(const MdsTime& startTime)
{
        Trace trace(Trace::EventIngest, "Subscription::execute");

        if (trace.IsActive()) {
                std::ostringstream msg;
                msg << "Start time " << startTime << ", end time " << startTime + interval();
                trace.NOTE(msg.str());
        }

	_head->Start(startTime);
	try {
		_sink->Foreach(startTime, interval(), [this](const CanonicalEntity& ce){ _head->Process(new CanonicalEntity(ce)); });
	}
	catch (std::exception & ex) {
		trace.NOTE(std::string("Exception leaked: ") + ex.what());
	}
	trace.NOTE("All lines processed");
	_sink->Flush();		// Tell the sink to do its housekeeping
        _head->Done();
}

std::ostream&
operator<<(std::ostream& os, const Subscription& sub)
{
	os << &sub << " (Event " << sub._target << ", interval " << sub._priority.Duration() << ")";

	return os;
}

// vim: se sw=8 :
