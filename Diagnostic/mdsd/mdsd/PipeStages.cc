// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "Logger.hh"
#include "Trace.hh"
#include "PipeStages.hh"
#include "Batch.hh"
#include "CanonicalEntity.hh"
#include "IdentityColumns.hh"
#include "Credentials.hh"
#include "MdsdConfig.hh"
#include "MdsSchemaMetadata.hh"
#include "StoreType.hh"
#include "Utility.hh"
#include "MdsTime.hh"
#include <boost/tokenizer.hpp>

namespace Pipe {

const std::string Unpivot::_name { "Unpivot" };

Unpivot::Unpivot(const std::string &valueName, const std::string &nameName, const std::string &columns,
		std::unordered_map<std::string, ColumnTransform>&& transforms)
    :	_valueName(valueName), _nameName(nameName), _transforms(transforms)
{
	Trace trace(Trace::QueryPipe, "Unpivot constructor");

	typedef boost::tokenizer<boost::char_separator<char> > tokenizer_t;

	boost::char_separator<char> delim(", ");	// space and comma
	tokenizer_t tokens(columns, delim);
	for (const auto &item : tokens) {
		_columns.insert(item);
	}
	if (_columns.empty()) {
		throw std::invalid_argument("No column names specified for <Unpivot>");
	} else if (_valueName.empty()) {
		throw std::invalid_argument("Invalid name for unpivot value");
	} else if (_nameName.empty()) {
		throw std::invalid_argument("Invalid name for unpivot name column");
	}

	if (trace.IsActive()) {
		std::ostringstream msg;
		msg << "Unpivoting these columns: ";
		for (const std::string &name : _columns) {
			msg << "[" << name;
			const auto& iter = _transforms.find(name);
			if (iter != _transforms.end()) {
				ColumnTransform& xform = iter->second;
				msg << " --> " << xform.Name;
				if (xform.Scale != 1.0) {
					msg << " scale " << xform.Scale;
				}
			}
			msg << "]";
		}
		trace.NOTE(msg.str());
	}
}

// Tear apart the input item to produce multiple output items.
void
Unpivot::Process(CanonicalEntity *item)
{
	Trace trace(Trace::QueryPipe, "Unpivot::Process");

	// 1: Run through the item and build a master CanonicalEntity which has only the
	//    columns that are *not* to be unpivoted. Count the pivoted columns.
	CanonicalEntity master;
	master.SetPreciseTime(item->GetPreciseTimeStamp());
	unsigned pivotCount = 0;
	for (auto col = item->begin(); col != item->end(); col++) {
		if (_columns.count(col->first)) {
			pivotCount++;
		} else {
			master.AddColumn(col->first, col->second);
			// col->second is an MdsValue* and it's now owned by master;
			// update item's ownership
			col->second = nullptr;
		}
	}

	// 2: If there were no pivoted columns, emit a warning, drop it on the floor,
	//    and return. (If we needed to send it to the pipeline, we'd have to dupe
	//    it from master into a heap-allocated copy and send that, since we'd
	//    already have torn all of the columns into master.)
	if (!pivotCount) {
		std::ostringstream msg;
		msg << "<Unpivot> matched no columns for this event: " << *item;
		Logger::LogWarn(msg);
		delete item;
		return;
	}
	if (trace.IsActive()) {
		std::ostringstream msg;
		msg << "Unpivoting " << pivotCount << " columns.";
		trace.NOTE(msg.str());
	}

	// 3: Run through the item again. Each time a column-to-be-unpivoted is found, duplicate
	//    the master CE, add the "name" and "value" columns, and send the row to our
	//    successor. Apply any translations to "name" at this time.
	for (auto col = item->begin(); col != item->end(); col++) {
		if (_columns.count(col->first)) {
			CanonicalEntity *ce = new CanonicalEntity { master };
			const auto & iter = _transforms.find(col->first);
			if (iter == _transforms.end()) {
				// No transform; use as-is
				ce->AddColumn(_nameName, col->first);
			} else {
				// iter points to a pair<string, ColumnTransform>
				// So iter->second is a ColumnTransform
				ColumnTransform& xform = iter->second;
				ce->AddColumn(_nameName, xform.Name);
				// Apply the scale factor stored in the transform. MdsValue::scale() does appropriate
				// type conversion and does nothing, silently, if the value is not numeric.
				col->second->scale(xform.Scale);
			}
			ce->AddColumn(_valueName, col->second);
			// col->second is an MdsValue* and it's now owned by the dupe ce;
			// update item's ownership
			col->second = nullptr;

			PipeStage::Process(ce);
		}
	}

	// 4. At this point we're done with the original item, which itself is not forwarded
	//    down the pipeline. Delete it.
	delete item;
}

const std::string BatchWriter::_name { "BatchWriter" };

BatchWriter::BatchWriter(Batch * b, const ident_vect_t * idvec, unsigned int pcount, StoreType::Type storeType)
	: _batch(b), _idvec(idvec), _identString(), _storeType(storeType)
{
	std::vector<std::string> identValues;
	bool firstTime = true;

	for (const auto &iter : *(_idvec)) {
		if (!firstTime)
			_identString.append("___");
		_identString.append(iter.second);
		firstTime = false;
	}

	// If the CanonicalEntity has identity columns, it may need partition and row keys.
	// The identity column data is sufficient to form the standard MDS partition and row keys,
	// which we do here. Only the data sink knows whether these keys are actually needed.
	_Nstr = MdsdUtil::ZeroFill(MdsdUtil::EasyHash(_identString) % (unsigned long long)pcount, 19);
}


// End of the processing pipeline. Adding the item to a batch is defined as a "copy" operation,
// so we should throw away the "original" after that.
void
BatchWriter::Process(CanonicalEntity *item)
{
	Trace trace(Trace::QueryPipe, "BatchWriter::Process");
	// Based on the target store type, ensure the proper keys are set
	if (_storeType == StoreType::XTable) {
		trace.NOTE("Adding XTable columns");
		bool doDefaultColumns = false;
		std::string rowIndex = MdsdUtil::ZeroFill(RowIndex::Get(), 19);
		if (item->PartitionKey().empty()) {
			item->AddColumn("PartitionKey", _Nstr + "___" + MdsdUtil::ZeroFill(_qibase.to_DateTime(), 19));
			doDefaultColumns = true;
		}
		if (item->RowKey().empty()) {
			item->AddColumn("RowKey", _identString +"___" + rowIndex);
			doDefaultColumns = true;
		}
		if (doDefaultColumns) {
			item->AddColumn("PreciseTimeStamp", new MdsValue(item->GetPreciseTimeStamp()));
			item->AddColumn("N", _Nstr);
			item->AddColumn("RowIndex", rowIndex);
		}
		item->AddColumn("TIMESTAMP", new MdsValue(_qibase));
	}

	_batch->AddRow(*item);
	delete item;
}

// Let the batch know we're done writing for now
void
BatchWriter::Done()
{
	_batch->Flush();
}

const std::string Identity::_name { "Identity" };

// Add identity columns to a CanonicalEntity
void
Identity::Process(CanonicalEntity *item)
{
	std::vector<std::string> identValues;

	for (const auto &iter : *(_idvec)) {
		item->AddColumn(iter.first, iter.second);
		identValues.push_back(iter.second);
	}

	PipeStage::Process(item);
}

const std::string BuildSchema::_name { "BuildSchema" };

// Track which event schemas have been pushed to the appropriate central SchemasTable

// This unordered set tracks the pushed schemas. The key is a string with these components
// separated by single forward slashes ("/"):
//	MDS account moniker (*not* XStore account name)
//	Full table name (augmented by namespace prefix and NDay suffix as appropriate)
//	MD5 checksum of the canonicalized schema
// This cache is global and never reset (except by agent restart).
std::unordered_set<std::string> BuildSchema::_pushedSchemas;

// The "target" metadata tells us where the corresponding SchemasTable should be. The
// "fixed" flag, if true, claims that all events sent to this stage will have exactly
// the same schema. When it is fixed, it need only be computed once at startup and,
// if the table rolls every N days, at the beginning of each N day period.
BuildSchema::BuildSchema(MdsdConfig *config, const MdsEntityName &target, bool fixed)
	: _target(target), _schemaIsFixed(fixed), _schemaRequired(false), _lastFullName()
{
	// In order to upload MDS schema metadata, we must use the target's credentials to write to
	// an arbitrary table. Local and File table have no credentials at all.
	const Credentials *creds = target.GetCredentials();
	if (creds && creds->accessAnyTable()) {
		// We need to write the schema. All we need to do is get a Batch pointer to which we
		// can write the SchemasTable entry.
		_schemaRequired = true;
		MdsEntityName schemaTarget { config, creds };
		_batch = config->GetBatch(schemaTarget, 60);
		_moniker = creds->Moniker();
		_agentIdentity = config->AgentIdentity();
	}
}

void
BuildSchema::Process(CanonicalEntity *item)
{
	if (item && _schemaRequired) {
		Trace trace(Trace::XTable, "Pipe::BuildSchema::Process");

		// This preamble does its best to bail out of schema writing as early and cheaply
		// as possible. We're silent from a tracing standpoint when taking the bailouts.
		std::string fullName = _target.Name();
		if (_schemaIsFixed && (fullName == _lastFullName)) {
			// Schema is constant, and we've already written it for this tablename
			// (Example: schemas defined by <Schema>)
			// State for this is managed below
			goto done;
		}

		// Construct the key used to see if we've pushed this schema already
		auto metadata = MdsSchemaMetadata::GetOrMake(_target, item);
		if (!metadata) {
			goto done;
		}
		std::string key = _moniker + "/" + fullName + "/" + metadata->GetMD5();
		if (_pushedSchemas.count(key)) {
			// We've already written it for this schema and tablename
			// (Example: schema computed from an OMI reply and written to a 10day table)
			goto done;
		}

		// OK, push the metadata and record it
		CanonicalEntity schemaCE { 12 };

		std::string physicalTableName = _target.PhysicalTableName();
		std::string rowkey = physicalTableName + "___" + metadata->GetMD5();
		std::string N = MdsdUtil::ZeroFill(physicalTableName.size() % 10, 19);
		std::string pkey = N + "___" + MdsdUtil::ZeroFill(MdsTime::FakeTimeStampTicks, 19);
		trace.NOTE("Schema row: pkey " + pkey + " rowkey " + rowkey);
		utility::datetime timestamp1601;
		timestamp1601 = timestamp1601 + 1;

		schemaCE.AddColumn("PartitionKey", pkey);
		schemaCE.AddColumn("RowKey", rowkey);
		schemaCE.AddColumn("TIMESTAMP", new MdsValue(timestamp1601));
		schemaCE.AddColumn("N", N);
		schemaCE.AddColumn("PhysicalTableName", physicalTableName);
		schemaCE.AddColumn("MD5Hash", metadata->GetMD5());
		schemaCE.AddColumn("Schema", metadata->GetXML());
		schemaCE.AddColumn("Uploader", _agentIdentity);
		schemaCE.AddColumn("UploadTS", new MdsValue(MdsTime::Now()));
		schemaCE.AddColumn("Reserved1", "");
		schemaCE.AddColumn("Reserved2", "");
		schemaCE.AddColumn("Reserved3", "");

		_batch->AddRow(schemaCE);
		_pushedSchemas.insert(key);

		// If the input to this pipeline is always the same (i.e. fixed schema), then
		// we only have to do this once (or, perhaps, once every N days).
		if (_schemaIsFixed) {
			// Manage the state required by the bailout-early preamble
			if (_target.IsConstant()) {
				_schemaRequired = false;	// Never have to do it again
			} else {
				_lastFullName = fullName;
			}
		}
		trace.NOTE("Finished; passing item to next stage");
	}

	done:
	PipeStage::Process(item);
}


// End of namespace
}

// vim: se ai sw=8 :
