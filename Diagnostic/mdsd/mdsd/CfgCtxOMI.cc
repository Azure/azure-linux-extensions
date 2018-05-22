// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "CfgCtxOMI.hh"
#include "CfgCtxError.hh"
#include "OmiTask.hh"
#include "MdsdConfig.hh"
#include "Utility.hh"
#include "StoreType.hh"
#include "PipeStages.hh"
#include "Trace.hh"
#include "EventType.hh"

#include <cstdlib>
#include <climits>

////////////////// CfgCtxOMI

subelementmap_t CfgCtxOMI::_subelements = {
	{ "OMIQuery", [](CfgContext* parent) -> CfgContext* { return new CfgCtxOMIQuery(parent); } }
};

std::string CfgCtxOMI::_name = "OMI";

////////////////// CfgCtxOMIQuery

void
CfgCtxOMIQuery::Enter(const xmlattr_t& properties)
{
    Trace trace(Trace::ConfigLoad, "CfgCtxOMIQuery::Enter");
    std::string eventName, account, omiNamespace, cqlQuery;
    Priority priority;
    time_t sampleRate = 0;
    bool NoPerNDay = false;

    _task = nullptr;
    _isOK = true;
    _storeType = StoreType::XTable;
    _doSchemaGeneration = true;

    for (const auto& item : properties) {
        if (item.first == "eventName") {
            if (MdsdUtil::NotValidName(item.second)) {
                ERROR("Invalid eventName attribute");
            } else {
                eventName = item.second;
            }
        } else if (item.first == "priority") {
            if (! priority.Set(item.second)) {
                WARNING("Ignoring unknown priority \"" + item.second + "\"");
            }
        } else if (item.first == "account") {
            if (MdsdUtil::NotValidName(item.second)) {
                ERROR("Invalid account attribute");
            } else {
                account = item.second;
            }
        } else if (item.first == "dontUsePerNDayTable") {
            NoPerNDay = MdsdUtil::to_bool(item.second);
        } else if (item.first == "omiNamespace") {
            omiNamespace = item.second;
        } else if (item.first == "cqlQuery") {
            cqlQuery = MdsdUtil::UnquoteXmlAttribute(item.second);
        } else if (item.first == "sampleRateInSeconds") {
            time_t requestedRate = std::stoul(item.second);
            if (requestedRate == 0) {
                ERROR("Invalid sampleRateInSeconds attribute - using default");
            } else {
                sampleRate = requestedRate;
            }
        } else if (item.first == "storeType") {
            _storeType = StoreType::from_string(item.second);
            _doSchemaGeneration = StoreType::DoSchemaGeneration(_storeType);
        } else {
            WARNING("Ignoring unexpected attribute " + item.first);
        }
    }

	try {
		// Build target on the stack, move it into the OmiTask
		auto target = MdsEntityName { eventName, NoPerNDay, Config, account, _storeType };
		_task = new OmiTask(Config, std::move(target), priority, omiNamespace, cqlQuery, sampleRate);
		// Centrally-stored events implicitly have Identity columns added to them as
		// defined in the <Management> element. Add them first thing so they're available
		// to subsequent stages (if any).
		if (_storeType != StoreType::Local) {
			_task->AddStage(new Pipe::Identity(Config->GetIdentityVector()));
		}
		Config->AddMonikerEventInfo(account, eventName, _storeType, "", mdsd::EventType::OMIQuery);
	}
	catch (const std::invalid_argument& ex) {
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
CfgCtxOMIQuery::Leave()
{
	Trace trace(Trace::ConfigLoad, "CfgCtxOMIQuery::Leave");
	if(_task) {
		// If not local/file, add a stage to push metadata into MDS. OMI queries should produce results with
		// the same schema each time. Doing an <Unpivot> doesn't change that.
		if (_doSchemaGeneration) {
			_task->AddStage(new Pipe::BuildSchema(Config, _task->Target(), true));
		}

		// Find/make the batch for this task; add a final pipeline stage to write to that batch;
		// add the task to the set of tasks in this config.
		Batch *batch = Config->GetBatch(_task->Target(), _task->FlushInterval());
        if (batch) {
            _task->AddStage(new Pipe::BatchWriter(batch, Config->GetIdentityVector(), Config->PartitionCount(), _storeType));
            Config->AddOmiTask(_task);
        } else {
            ERROR("Configuration error(s) detected; dropping this OMIQuery.");
            delete _task;
        }

	}
	return ParentContext;
}

const subelementmap_t&
CfgCtxOMIQuery::GetSubelementMap() const
{
        if (_isOK) { return _subelements; }
        else { return CfgCtxError::subelements; }
}


subelementmap_t CfgCtxOMIQuery::_subelements {
	{ "Unpivot", [](CfgContext* parent) -> CfgContext* { return new CfgCtxUnpivot(parent); } }
};

std::string CfgCtxOMIQuery::_name = "OMIQuery";

////////////////// CfgCtxUnpivot

void
CfgCtxUnpivot::Enter(const xmlattr_t& properties)
{
	_query = dynamic_cast<CfgCtxOMIQuery*>(ParentContext);
	if (!_query) {
		ERROR("<Unpivot> is not a valid subelement of <" + ParentContext->Name() + ">");
		_isOK = false;
		return;
	}

	// Bail if parent didn't parse right or didn't build an OmiTask instance
	if (! (_query->isOK() && _query->GetTask())) {
		_isOK = false;
		return;
	}

	for (const auto &iter : properties) {
		if (iter.first == "columnValue") {
			_valueAttrName = iter.second;
		} else if (iter.first == "columnName") {
			_nameAttrName = iter.second;
		} else if (iter.first == "columns") {
			_unpivotColumns = iter.second;
		} else {
			WARNING("Ignoring unexpected attribute " + iter.first);
		}
	}

	if (_valueAttrName.empty() || _nameAttrName.empty() || _unpivotColumns.empty()) {
		ERROR("Missing one or more required attributes (columnValue, columnName, columns)");
		_isOK = false;
		return;
	}
}

CfgContext*
CfgCtxUnpivot::Leave()
{
	if (_isOK) {
		auto unpivoter = new Pipe::Unpivot(_valueAttrName, _nameAttrName, _unpivotColumns, std::move(_transforms));
		_query->GetTask()->AddStage(unpivoter);
	}

	return ParentContext;
}

void
CfgCtxUnpivot::addTransform(const std::string& from, const std::string& to, double scale)
{
	_transforms.emplace(std::piecewise_construct, std::forward_as_tuple(from), std::forward_as_tuple(to, scale));
}

subelementmap_t CfgCtxUnpivot::_subelements {
	{ "MapName", [](CfgContext* parent) -> CfgContext* { return new CfgCtxMapName(parent); } }
};

std::string CfgCtxUnpivot::_name = "Unpivot";

////////////////// CfgCtxMapName

void
CfgCtxMapName::Enter(const xmlattr_t& properties)
{
	_unpivot = dynamic_cast<CfgCtxUnpivot*>(ParentContext);
	if (!_unpivot) {
		ERROR("<MapName> is not a valid subelement of <" + ParentContext->Name() + ">");
		_isOK = false;
		return;
	}

	for (const auto &iter : properties) {
		if (iter.first == "name") {
			_from = iter.second;
		} else if (iter.first == "scaleUp") {
			_scale *= std::stod(iter.second);
		} else if (iter.first == "scaleDown") {
			_scale /= std::stod(iter.second);
		} else {
			WARNING("Ignoring unexpected attribute " + iter.first);
		}
	}

	if (_from.empty()) {
		ERROR("Missing required \"from\" attribute");
		_isOK = false;
		return;
	}
}

// Process XML body; accumulate it as the value of the _to instance var
void
CfgCtxMapName::HandleBody(const std::string& body)
{
	if (_isOK) {
		_to += body;
	}
}

// Now that we have the target name for the translation, let's save it.
CfgContext*
CfgCtxMapName::Leave()
{
	if (_isOK) {
		if (_to.empty()) {
			_to = _from;
		}
		_unpivot->addTransform(_from, _to, _scale);
	} else {
		ERROR("Error(s) detected; ignoring this element");
	}

	return ParentContext;
}

subelementmap_t CfgCtxMapName::_subelements;

std::string CfgCtxMapName::_name = "MapName";

// vim: se sw=8 :
