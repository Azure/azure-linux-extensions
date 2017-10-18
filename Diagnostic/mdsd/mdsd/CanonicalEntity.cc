// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "CanonicalEntity.hh"
#include "MdsSchemaMetadata.hh"
//#include <algorithm>
#include "Utility.hh"

#include "Engine.hh" // To get the mdsd config
#include "MdsdConfig.hh"

#include <unordered_map>

using std::string;
using std::make_pair;

// Clone the src entity. Usually used when some operation plans to add columns to a reduced-size
// "master" entity, so reserve some extra space just in case.
CanonicalEntity::CanonicalEntity(const CanonicalEntity& src)
	: _timestamp(src._timestamp), _pkey(src._pkey), _rkey(src._rkey), _schemaId(src._schemaId),
    _srctype(src._srctype)
{
	_entity.reserve(2 + src._entity.size());

	// std::for_each(src._entity.cbegin(), src._entity.cend(), [this](const col_t& col){this->CopyAddColumn(col);});
	for (const auto & col : src._entity) {
		AddColumn(col.first, new MdsValue(*(col.second)));
	}
}

CanonicalEntity::~CanonicalEntity()
{
	for (col_t col : _entity) {
		if (col.second) {
			delete col.second;
		}
	}
}

// AddColumn "owns" the MdsValue* once it's passed in. We can keep it, or move from it and destroy it.
void
CanonicalEntity::AddColumn(const std::string name, MdsValue* val)
{
    if (name == "PartitionKey") {
        _pkey = std::move(*(val->strval));
        delete val;
    } else if (name == "RowKey") {
        _rkey = std::move(*(val->strval));
        delete val;
	} else {
		_entity.push_back(std::make_pair(name, val));
	}
}

// Add column only if the column name isn't a MetaData column.
void
CanonicalEntity::AddColumnIgnoreMetaData(const std::string name, MdsValue* val)
{
    if (MdsSchemaMetadata::MetadataColumns.count(name)) {
        delete val;
    } else {
        _entity.push_back(std::make_pair(name, val));
    }
}

MdsValue*
CanonicalEntity::Find(const std::string &name) const
{
	for (auto iter : _entity) {
		if (iter.first == name) {
			return iter.second;
		}
	}
	return nullptr;
}

std::ostream&
operator<<(std::ostream& os, const CanonicalEntity& ce)
{
	int count = ce._entity.size();

	os << "(" << count << " columns, time " << ce.GetPreciseTimeStamp() << ", _pKey ";
	if (ce._pkey.empty()) {
		os << "{empty}";
	} else {
		os << ce._pkey;
	}
	os << ", _rkey ";
	if (ce._pkey.empty()) {
		os << "{empty}";
	} else {
		os << ce._rkey;
	}
	os << ", [";
	for (auto iter : ce._entity) {
		os << iter.first << "=";
		if (iter.second) {
			os << *(iter.second);
		} else {
			os << "<nullptr>";
		}
		if (--count) {
			os << ", ";
		}
	}
	os << "])";

	return os;
}


std::string
CanonicalEntity::GetJsonRow(
		const std::string& timeGrain,
		const std::string& tenant,
		const std::string& role,
		const std::string& roleInstance) const
{
    const std::string& resourceId = Engine::GetEngine()->GetConfig()->GetResourceId();

    if (resourceId.empty()) {
        throw std::runtime_error("Empty resourceId (OboDirectPartitionField) when a JSON event is requested");
    }

	// Check if this row is for metric or for log.
	// A metric event must include "CounterName" and "Last" columns.
	// Its timeGrain shouldn't be empty.
	bool counterNameExists = false, lastExists = false;
	for (auto item : _entity) {
		if (item.first == "CounterName") {
			counterNameExists = true;
		}
		else if (item.first == "Last") {
			lastExists = true;
		}
	}
	bool isMetricRow = counterNameExists && lastExists && !timeGrain.empty();
	return isMetricRow ? GetJsonRowForMetric(resourceId, timeGrain, tenant, role, roleInstance)
                       : GetJsonRowForLog(resourceId);
}


/* Example return Json string:

{ "time" : "2016-12-21T01:06:04.9067290Z",
  "resourceId": "/subscriptions/xxx-xxx-xxx-xxx/resourceGroups/myrg/providers/Microsoft.Compute/VirtualMachines/myvm",
  "properties" : {
    "Column1Name": "Column1Value",
    "Column2Name": "Column2Value",
    "ColumnNName": "ColumnNValue"
  },
  "category": "user",
  "level": "info",
  "operationName": "some_name_depending_on_detected_event_type"
}

*/
std::string
CanonicalEntity::GetJsonRowForLog(const std::string& resourceId) const
{
    std::ostringstream oss;

    oss << "{ \"time\" : \"" << GetPreciseTimeStamp() << "\",\n"
           "  \"resourceId\" : \"" << resourceId << "\",\n"
	       "  \"properties\" : {\n";
	bool first = true;
	std::string category = "\"Unknown\"", level = "\"Unknown\"", operationName = "\"Unknown\"";
	for (auto iter : _entity) {
		if (first) {
			first = false;
		} else {
			oss << ",\n";
		}
		if (iter.second) {
			oss << "    \"" << iter.first << "\" : " << iter.second->ToJsonSerializedString();
			// We consider this event to be from syslog if there's a field named "Facility".
			// Set the related Azure Monitor required fields (category, level, operationName) accordingly.
			if (iter.first == "Facility") {
				category = iter.second->ToJsonSerializedString(); // Let's use syslog facility as Azure Monitor "category".
				operationName = "\"LinuxSyslogEvent\""; // Change this later as necessary
			} else if (iter.first == "Severity") {
				// Let's use syslog severity as Azure Monitor "level".
				if (iter.second->IsNumeric()) {
					level = MdsdUtil::GetSyslogSeverityStringFromValue((int)iter.second->ToDouble());
				} else {
					// iter.second->IsString(), which is the case when syslog events are
				    // routed from fluentd's in_syslog & out_mdsd.
					level = iter.second->ToJsonSerializedString();
				}
			}
		}
	}
    oss << "\n  },\n"
           "  \"category\" : " << category << ",\n"
           "  \"level\" : " << level << ",\n"
           "  \"operationName\" : " << operationName << "\n"
           "}";

    return oss.str();
}


/* Example return Json string:

{ "time" : "2016-12-21T01:06:04.9067290Z",
  "resourceId": "/subscriptions/xxx-xxx-xxx-xxx/resourceGroups/myrg/providers/Microsoft.Compute/VirtualMachines/myvm",
  "timeGrain" : "PT1M",
  "dimensions" : {
    "Tenant": "JsonBlobTestTenantName",
    "Role": "JsonBlobTestRoleName",
    "RoleInstance": "JsonBlobTestRoleinstanceName"
  },
  "metricName": "\\Processor\\PercentProcessorTime",
  "last": 0
}

*/
std::string
CanonicalEntity::GetJsonRowForMetric(
        const std::string& resourceId,
		const std::string& timeGrain,
		const std::string& tenant,
		const std::string& role,
		const std::string& roleInstance) const
{
    std::ostringstream oss;
    oss << "{ \"time\" : \"" << GetPreciseTimeStamp() << "\",\n";
    oss << "  \"resourceId\" : \"" << resourceId << "\",\n";
    oss << "  \"timeGrain\" : \"" << timeGrain << "\",\n";
    oss << "  \"dimensions\": {\n"
           "     \"Tenant\": \"" << tenant << "\",\n"
           "     \"Role\": \"" << role << "\",\n"
           "     \"RoleInstance\": \"" << roleInstance << "\"\n"
           "  }";

    static std::unordered_map<std::string, std::string> columnNameTranslations = {
        { "CounterName", "metricName" },
        { "Average", "average" },
        { "Minimum", "minimum" },
        { "Maximum", "maximum" },
        { "Total", "total" },
        { "Last", "last" },
        { "Count", "count" }
    };

    size_t countOfTranslations = 0;
    for (const auto & nameValue : _entity) {
        auto translationPair = columnNameTranslations.find(nameValue.first);
        if (translationPair != columnNameTranslations.end()) {
            oss << ",\n  \"" << translationPair->second << "\": " << nameValue.second->ToJsonSerializedString();
            countOfTranslations++;
        }
    }

    if (columnNameTranslations.size() != countOfTranslations) {
        std::ostringstream msg;
        msg << "Dropping invalid CanonicalEntity for metric (missing required column(s)): " << *this;
        throw std::runtime_error(msg.str());
    }

    oss << "\n}";
    return oss.str();
}

// vim: se sw=8 :
