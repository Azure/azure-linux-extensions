// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "CfgCtxDerived.hh"
#include "CfgCtxError.hh"
#include "MdsdConfig.hh"
#include "Utility.hh"
#include "StoreType.hh"
#include "PipeStages.hh"
#include "LADQuery.hh"
#include "Priority.hh"
#include "Trace.hh"
#include "EventType.hh"

////////////////// CfgCtxDerived

subelementmap_t CfgCtxDerived::_subelements = {
	{ "DerivedEvent", [](CfgContext* parent) -> CfgContext* { return new CfgCtxDerivedEvent(parent); } }
};

std::string CfgCtxDerived::_name = "DerivedEvents";

////////////////// CfgCtxDerivedEvent

void
CfgCtxDerivedEvent::Enter(const xmlattr_t& properties)
{
	Trace trace(Trace::ConfigLoad, "CfgCtxDerivedEvent::Enter");
	std::string eventName, account, source, durationString;
	MdsTime duration { 0 };
	bool NoPerNDay = false, isFullName = false;
	Priority priority { "Normal" };

	_task = nullptr;
	_isOK = true;
	_storeType = StoreType::XTable;
	_doSchemaGeneration = true;

	for (const auto & iter : properties) {
		if (iter.first == "eventName") {
			if (MdsdUtil::NotValidName(iter.second)) {
				ERROR("Invalid eventName attribute");
			} else {
				eventName = iter.second;
			}
		} else if (iter.first == "priority") {
			if (! priority.Set(iter.second)) {
				WARNING("Ignoring unknown priority \"" + iter.second + "\"");
			}
		} else if (iter.first == "account") {
			if (MdsdUtil::NotValidName(iter.second)) {
				ERROR("Invalid account attribute");
			} else {
				account = iter.second;
			}
		} else if (iter.first == "dontUsePerNDayTable") {
			NoPerNDay = MdsdUtil::to_bool(iter.second);
		} else if (iter.first == "isFullName") {
			isFullName = MdsdUtil::to_bool(iter.second);
		} else if (iter.first == "duration") {
			MdsTime requestedDuration = MdsTime::FromIS8601Duration(iter.second);
			if (!requestedDuration) {
				ERROR("Invalid duration attribute");
				_isOK = false;
			} else {
				duration = requestedDuration;
				durationString = iter.second;
			}
		} else if (iter.first == "storeType") {
			_storeType = StoreType::from_string(iter.second);
			_doSchemaGeneration = StoreType::DoSchemaGeneration(_storeType);
		} else if (iter.first == "source") {
			if (MdsdUtil::NotValidName(iter.second)) {
				ERROR("Invalid account attribute");
			} else {
				source = iter.second;
			}
		} else {
			WARNING("Ignoring unexpected attribute " + iter.first);
		}
	}

	if (!duration) {
		ERROR("The duration attribute is required");
		_isOK = false;
	}

	if (!_isOK) {
		return;
	}

	try {
		// Build target on the stack, move it into the DerivedTask
		auto target = MdsEntityName { eventName, NoPerNDay, Config, account, _storeType, isFullName };

		_task = new DerivedEvent(Config, std::move(target), priority, duration, source);
		// Centrally-stored events implicitly have Identity columns added to them as
		// defined in the <Management> element. Add them first thing so they're available
		// to subsequent stages (if any).
		if (_storeType != StoreType::Local) {
			_task->AddStage(new Pipe::Identity(Config->GetIdentityVector()));
		}
		Config->AddMonikerEventInfo(account, eventName, _storeType, source, mdsd::EventType::DerivedEvent);
		Config->SetDurationForEventName(eventName, durationString);
	}
	catch (const std::exception& ex) {
		ERROR(ex.what());
		_isOK = false;
		return;
	}
	catch (...) {
		FATAL("Unknown exception; skipping");
		_isOK = false;
		return;
	}
}

CfgContext*
CfgCtxDerivedEvent::Leave()
{
	Trace trace(Trace::ConfigLoad, "CfgCtxDerivedEvent::Leave");

	if(_task) {
		// If not local, add a stage to push metadata into MDS. Derived queries should produce results with
		// the same schema each time. Doing an <LADQuery> doesn't change that.
		if (_doSchemaGeneration && _storeType != StoreType::Local) {
			_task->AddStage(new Pipe::BuildSchema(Config, _task->Target(), true));
		}

		// Find/make the batch for this task; add a final pipeline stage to write to that batch;
		// add the task to the set of tasks in this config.
		Batch *batch = Config->GetBatch(_task->Target(), _task->FlushInterval());
		if (batch) {
			_task->AddStage(new Pipe::BatchWriter(batch, Config->GetIdentityVector(),
								Config->PartitionCount(), _storeType));
			Config->AddTask(_task);
		} else {
			ERROR("Configuration error(s) detected; dropping this DerivedEvent.");
			delete _task;
		}
	}
	return ParentContext;
}

const subelementmap_t&
CfgCtxDerivedEvent::GetSubelementMap() const
{
	if (_isOK) { return _subelements; }
	else { return CfgCtxError::subelements; }
}


subelementmap_t CfgCtxDerivedEvent::_subelements {
	{ "LADQuery", [](CfgContext* parent) -> CfgContext* { return new CfgCtxLADQuery(parent); } }
};

std::string CfgCtxDerivedEvent::_name = "DerivedEvent";

////////////////// CfgCtxLADEvent

void
CfgCtxLADQuery::Enter(const xmlattr_t& properties)
{
	Trace trace(Trace::ConfigLoad, "CfgCtxLADQuery::Enter");
	std::string valueAttrName, nameAttrName, partitionKey, uuid;

	CfgCtxDerivedEvent* query = dynamic_cast<CfgCtxDerivedEvent*>(ParentContext);
	if (!query) {
		ERROR("<LADQuery> is not a valid subelement of <" + ParentContext->Name() + ">");
		return;
	}

	// Bail if parent didn't parse right or didn't build an OmiTask instance
	if (! (query->isOK() && query->GetTask())) {
		return;
	}

	for (const auto& item : properties) {
		if (item.first == "columnValue") {
			valueAttrName = item.second;
		} else if (item.first == "columnName") {
			nameAttrName = item.second;
		} else if (item.first == "partitionKey") {
			partitionKey = item.second;
		} else if (item.first == "instanceID") {
			uuid = item.second;
		} else {
			WARNING("Ignoring unexpected attribute " + item.first);
		}
	}

	if (valueAttrName.empty() || nameAttrName.empty() || partitionKey.empty()) {
		ERROR("Missing one or more required attributes (columnValue, columnName, partitionKey)");
		return;
	}
	// An empty or unset uuid attribute is permitted (and meaningful)

	auto task = query->GetTask();
	task->AddStage(new Pipe::LADQuery(std::move(valueAttrName), std::move(nameAttrName),
	                                              std::move(partitionKey), std::move(uuid)));
	// Centrally-stored events implicitly have Identity columns added to them as
	// defined in the <Management> element. The LADQuery stage strips them off;
	// we should put them back in.
	if (! (query->isStoredLocally()) ) {
		task->AddStage(new Pipe::Identity(Config->GetIdentityVector()));
	}
	query->SuppressSchemaGeneration();	// LAD queries don't generate entries in SchemasTable
}

subelementmap_t CfgCtxLADQuery::_subelements;

std::string CfgCtxLADQuery::_name = "LADQuery";

// vim: se sw=8 :
