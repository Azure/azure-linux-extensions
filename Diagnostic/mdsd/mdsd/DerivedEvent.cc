// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "DerivedEvent.hh"
#include "MdsdConfig.hh"
#include "Pipeline.hh"
#include "CanonicalEntity.hh"
#include "Logger.hh"
#include "Trace.hh"
#include "LocalSink.hh"

DerivedEvent::DerivedEvent(MdsdConfig * config, const MdsEntityName &target, Priority prio, const MdsTime &interval,
                std::string source)
	: ITask(interval), _config(config), _target(target), _prio(prio), _head(nullptr), _tail(nullptr)
{
	Trace trace(Trace::DerivedEvent, "DerivedEvent constructor");

	// Find the source; make sure it exists

	_localSink = LocalSink::Lookup(source);
	if (! _localSink) {
		std::ostringstream msg;
		msg << "DerivedEvent " << target << " references undefined source " << source;
		Logger::LogError(msg.str());
		throw std::runtime_error(msg.str());
	}
	_localSink->SetRetentionPeriod(interval);
}

DerivedEvent::~DerivedEvent()
{
}

// Initial start time is a few seconds past the end of the current interval
MdsTime
DerivedEvent::initial_start()
{
	Trace trace(Trace::DerivedEvent, "DerivedEvent::initial_start");

	MdsTime start;	// Default constructor sets it to "now"

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
DerivedEvent::AddStage(PipeStage *stage)
{       
	Trace trace(Trace::DerivedEvent, "DerivedEvent::AddStage");

        if (trace.IsActive()) {
                std::ostringstream msg;
                msg << "DerivedEvent " << this << " adding stage " << stage->Name();
                trace.NOTE(msg.str());
        }

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

// Pull all the CanonicalEntity instances from the source that match the interval and send a dupe
// into the processing pipeline; signal "done" after the last instance.
void
DerivedEvent::execute(const MdsTime& startTime)
{
	Trace trace(Trace::DerivedEvent, "DerivedEvent::execute");

	if (trace.IsActive()) {
		std::ostringstream msg;
		msg << "Start time " << startTime << ", end time " << startTime + interval();
		trace.NOTE(msg.str());
	}

	auto head = _head;

	_head->Start(startTime);
	_localSink->Foreach(startTime, interval(), [head](const CanonicalEntity& ce){ head->Process(new CanonicalEntity(ce)); });
	_localSink->Flush();		// Tell the sink to do its housekeeping
	_head->Done();
}

// vim: se sw=8 :
