// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "Logger.hh"
#include "Trace.hh"
#include "LADQuery.hh"
#include "CanonicalEntity.hh"
#include "Utility.hh"
#include <iomanip>
#include <sstream>
#include <cctype>

namespace Pipe {

const std::string LADQuery::_name { "LADQuery" };

void
LADQuery::FullAggregate::Sample(double value)
{
	_total += value;
	_last = value;
	if (_count) {
		if (value > _maximum)
			_maximum = value;
		if (value < _minimum)
			_minimum = value;
	} else {
		_maximum = _minimum = value;
	}
	_count += 1;
}


// The core DerivedEvent task pulls entities from the source that fall within the just-completed
// time window (based on duration). The LADQuery looks like this:
// 1) Group by the value in the nameAttrName column; mark that column to be preserved
// 2) Compute aggregate stats for the value in the valueAttrName column and pass the single aggregate row down the pipe
// 3) Add a column with the specified partition key
// 4) Send the CanonicalEntity down the pipe twice, once with each of the two distinct row keys as defined for the LAD query
//
// The strings are pass-by-value; the initializers use move semantics to move the copies into the member variables.
// If the compiler can determine the actual parameters are temporaries, or about to go out of scope, it can optimize
// the copy away, thus giving us the move semantics we actually want. Worst case, we're still doing only a single
// copy (to prepare the passed values).
LADQuery::LADQuery(std::string valueAN, std::string nameAN, std::string pkey, std::string uuid)
	: _valueAttrName(std::move(valueAN)), _nameAttrName(std::move(nameAN)), _pkey(std::move(pkey)),
	  _uuid(std::move(uuid)), _lastSampleTime(0), _startOfSample(0)
{
}

void
LADQuery::Start(const MdsTime QIbase)
{
	// Prepare to process all the rows in this sample period
	_lastSampleTime = QIbase;
	_startOfSample = QIbase;

	// Do whatever the base class needs
	PipeStage::Start(QIbase);
}

void
LADQuery::Process(CanonicalEntity *item)
{
	Trace trace(Trace::QueryPipe, "LADQuery::Process");

	// Get the value of the nameAttrName column
	// Look in the savedStats map for the FullAggregate object associated with that name
	//    if there is none, make one and then use it
	// Update the FullAggregate based on the value of the valueAttrName column
	MdsValue* value = item->Find(_valueAttrName);
	MdsValue* name = item->Find(_nameAttrName);
	if (!(value && name)) {
		trace.NOTE("Name or Value column missing; skipping entity");
	} else if (! name->IsString()) {
		Logger::LogWarn("Name column is not a string");
	} else if (! value->IsNumeric()) {
		Logger::LogWarn("Value column is not numeric");
	} else {
		_savedStats[*(name->strval)].Sample(value->ToDouble());
		_lastSampleTime = item->PreciseTime();
	}

	delete item;	// No longer needed; we've updated the correct aggregation object
}

void
LADQuery::Done()
{
	Trace trace(Trace::DerivedEvent, "LADQuery::Done");
	// For each savedStats object in the map:
	//   Build a new CE with the full set of stats
	//   Add the _partitionKey to the CE
	//   Dupe the CE
	//   Put one of the LAD keys on the original CE; put the other key on the dupe
	//   Send both rows to the successor pipe
	//
	// Call Done on the successor pipe

	std::string descendingTicks = MdsdUtil::ZeroFill(MdsTime::MaxDateTimeTicks - _startOfSample.to_DateTime(), 19);

	for (const auto & iter : _savedStats) {
		auto entity = new CanonicalEntity(10);
		entity->SetPreciseTime(MdsTime::Now());	// For the "time" field in Jsonblob

		entity->AddColumn(_nameAttrName, new MdsValue(iter.first));
		entity->AddColumn("Total", new MdsValue(iter.second.Total()));
		entity->AddColumn("Minimum", new MdsValue(iter.second.Minimum()));
		entity->AddColumn("Maximum", new MdsValue(iter.second.Maximum()));
		entity->AddColumn("Average", new MdsValue(iter.second.Average()));
		entity->AddColumn("Count", new MdsValue(iter.second.Count()));
		entity->AddColumn("Last", new MdsValue(iter.second.Last()));

		entity->AddColumn("PartitionKey", _pkey);

		auto dupe = new CanonicalEntity(*entity);
		dupe->SetPreciseTime(entity->PreciseTime());	// For the "time" field in Jsonblob

		std::string metric = EncodeAndHash(iter.first, 256);

		std::ostringstream key1, key2;
		key1 << descendingTicks << "__" << metric;
		key2 << metric << "__" << descendingTicks;
		if (_uuid.length()) {
			key1 << "__" << _uuid;
			key2 << "__" << _uuid;
		}

		trace.NOTE("Aggregation rowkey " + key1.str());
		entity->AddColumn("RowKey", key1.str());
		PipeStage::Process(entity);
		trace.NOTE("Aggregation rowkey (dupe) " + key2.str());
		dupe->AddColumn("RowKey", key2.str());
		dupe->SetSourceType(CanonicalEntity::SourceType::Duplicated);
		PipeStage::Process(dupe);
	}
	PipeStage::Done();	// Pass the "done" signal to the next stage

	// Empty the map now to free memory, rather than waiting for the next Start() call
	_savedStats.clear();
}

std::string
LADQuery::EncodeAndHash(const std::string &name, size_t limit)
{
	Trace trace(Trace::DerivedEvent, "LADQuery::EncodeAndHash");

	trace.NOTE("EncodeAndHash(\"" + name + "\")");
	std::string result;
	for (const char c : name) {
		if (isalpha(c) || isdigit(c)) {
			result.push_back(c);
		} else {
			std::ostringstream encoded;
			encoded << ":" << std::hex << std::uppercase << std::setw(4) << std::setfill('0') << (unsigned short)c;
			result.append(encoded.str());
		}
	}
	if (result.size() > limit) {
		trace.NOTE("Hashing required...");
		auto hash = MdsdUtil::MurmurHash64(result, 0);
		std::ostringstream hashstr;
		const size_t charcnt = sizeof(hash)*2;
		hashstr << "|" << std::hex << std::setw(charcnt) << std::setfill('0') << hash;
		result.replace(limit - (1 + charcnt), std::string::npos, hashstr.str());
	}
	trace.NOTE("Encoded to \"" + result + "\"");
	return result;
}

// End of namespace
}

// vim: se ai sw=8 :
