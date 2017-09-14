// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "CfgCtxMdsdEvents.hh"
#include "MdsdConfig.hh"
#include "MdsEntityName.hh"
#include "Subscription.hh"
#include "Utility.hh"
#include "Priority.hh"
#include "PipeStages.hh"
#include "LocalSink.hh"
#include <iterator>
#include "CfgCtxParser.hh"
#include "EventType.hh"

////////////////// CfgCtxMdsdEvents

subelementmap_t CfgCtxMdsdEvents::_subelements = {
	{ "MdsdEventSource", [](CfgContext* parent) -> CfgContext* { return new CfgCtxMdsdEventSource(parent); } }
};

std::string CfgCtxMdsdEvents::_name = "MdsdEvents";

////////////////// CfgCtxMdsdEventSource

void
CfgCtxMdsdEventSource::Enter(const xmlattr_t& properties)
{
	for (const auto& item : properties) {
		if (item.first == "source") {
			_source = item.second;
		} else {
			WARNING("Ignoring unexpected attribute " + item.first);
		}
	}

	if (_source.empty()) {
		ERROR("Missing required source attribute");
		return;
	}

	if (!Config->IsValidSource(_source) && !Config->IsValidDynamicSchemaSource(_source)) {
		ERROR("Undefined source \"" + _source + "\"");
		_source.clear();	// Puts the entire element in error state
	}
	else {
		// The LocalSink object should be already created
		_sink = LocalSink::Lookup(_source);
		if (!_sink) {
			ERROR("Failed to find LocalSink for MdsdEventSource \"" + _source + "\"");
		}
	}
}

subelementmap_t CfgCtxMdsdEventSource::_subelements = {
	{ "RouteEvent", [](CfgContext* parent) -> CfgContext* { return new CfgCtxRouteEvent(parent); } }
};

std::string CfgCtxMdsdEventSource::_name = "MdsdEventSource";

////////////////// CfgCtxRouteEvent

// Construct a Subscription object to query the event sink. Build the front of the pipeline to
// process entities fetched from the sink.
// The duration attribute is optional. If it's not set, a duration based on priority is used.
// If priority is not explicitly set, there's a default for that, which then governs the duration.
void
CfgCtxRouteEvent::Enter(const xmlattr_t& properties)
{
	_subscription = 0;
	_storeType = StoreType::XTable;
	_doSchemaGeneration = true;
	bool addIdentity = true;

	_ctxEventSource = dynamic_cast<CfgCtxMdsdEventSource*>(ParentContext);
	if (!_ctxEventSource) {
		FATAL("Found <RouteEvent> in <" + ParentContext->Name() + ">; that can't happen");
		return;
	}

	CfgCtx::CfgCtxParser parser(this);
	if (!parser.ParseEvent(properties, CfgCtx::EventType::RouteEvent)) {
		return;
	}

	std::string eventName = parser.GetEventName();
	Priority priority = parser.GetPriority();
	std::string account = parser.GetAccount();
	bool NoPerNDay = parser.IsNoPerNDay();
	time_t interval = parser.GetInterval();

	if (parser.HasStoreType()) {
		_storeType = parser.GetStoreType();
		_doSchemaGeneration = StoreType::DoSchemaGeneration(_storeType);
		addIdentity = StoreType::DoAddIdentityColumns(_storeType);
	}

	try {
		// Build target on the stack, move it into the Subscription task
		auto target = MdsEntityName { eventName, NoPerNDay, Config, account, _storeType };
		assert(interval != 0);
		_subscription = new Subscription( _ctxEventSource->Sink(), std::move(target), priority, MdsTime(interval) );
		if (addIdentity) {
			// When we add custom identity columns per-subscription, sub them in here
			_subscription->AddStage(new Pipe::Identity(Config->GetIdentityVector()));
		}
		Config->AddMonikerEventInfo(account, eventName, _storeType, _ctxEventSource->Source(), mdsd::EventType::RouteEvent);
	}
	catch (const std::invalid_argument& ex) {
		ERROR(ex.what());
		return;
	}
	catch (...) {
		FATAL("Unknown exception; skipping");
		return;
	}
}

CfgContext*
CfgCtxRouteEvent::Leave()
{
	if (! _subscription) {
		return ParentContext;
	}

	// Non-local/file targets need to have a schema constructed and pushed. The schema for
	// events from a given external source is fixed, so it only needs to be computed once
	// and pushed once per Nday period
	if (_doSchemaGeneration) {
		_subscription->AddStage(new Pipe::BuildSchema(Config, _subscription->target(), true));
	}

	// Find/make the batch for this task; add a final pipeline stage to write to that batch;
	// add the subscription to the config.
	Batch *batch = Config->GetBatch(_subscription->target(), _subscription->Duration());
	if (batch) {
		_subscription->AddStage(new Pipe::BatchWriter(batch, Config->GetIdentityVector(),
		                                              Config->PartitionCount(), _storeType));

		// Config->AddSubscription(_ctxEventSource->Source(), _subscription);
		Config->AddTask(_subscription);
	} else {
		ERROR("Unable to create routing for this event");
	}
	return ParentContext;
}

subelementmap_t CfgCtxRouteEvent::_subelements = {
	{ "Filter", [](CfgContext* parent) -> CfgContext* { return new CfgCtxFilter(parent); } }
};

std::string CfgCtxRouteEvent::_name = "RouteEvent";

////////////////// CfgCtxFilter

subelementmap_t CfgCtxFilter::_subelements;

std::string CfgCtxFilter::_name = "Filter";


// vim: se sw=8 :
