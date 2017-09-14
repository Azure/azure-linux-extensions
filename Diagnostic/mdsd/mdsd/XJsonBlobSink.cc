// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "XJsonBlobSink.hh"
#include "XJsonBlobRequest.hh"
#include "XJsonBlobBlockCountsMgr.hh"

#include <iterator>
#include <sstream>

#include "CanonicalEntity.hh"
#include "MdsdConfig.hh"
#include "Credentials.hh"
#include "Utility.hh"
#include "AzureUtility.hh"
#include "RowIndex.hh"
#include "Trace.hh"
#include "Logger.hh"
#include "MdsdMetrics.hh"
#include "StoreType.hh"
#include "Constants.hh"
#include "MdsTime.hh"
#include "CfgOboDirectConfig.hh"

#include <wascore/basic_types.h>


XJsonBlobSink::XJsonBlobSink(MdsdConfig* config, const MdsEntityName &target, const Credentials* c)
    : IMdsSink(StoreType::Type::XJsonBlob), _template(target), _creds(c)
    , _namespace(config->Namespace()), _firstReqCreated(false)
    , _blobBaseTime(0) // Make sure to set _blobBaseTime to a past long time ago when constructing
{
    Trace trace(Trace::JsonBlob, "XJBS::Constructor");

    if (!config) {
        throw std::invalid_argument("Null MdsdConfig* config");
    }
    if (!c) {
        throw std::invalid_argument("Null Credentials* c");
    }

    auto eventName = target.EventName();

    try {
        auto oboDirectConfig = config->GetOboDirectConfig(eventName); // May throw std::out_of_range if eventName is not a key stored in the map.
        InitializeForOboDirect(config, oboDirectConfig);
    }
    catch (const std::out_of_range& e) {
        // No OboDirect config. It's LAD JsonBlob sink scenario.
    	InitializeForLadWithoutOboDirect(config);
    }

    // Finally, fill in duration/tenant/role/roleInstance (for metric Json content)
    _template.duration = config->GetDurationForEventName(eventName);
    config->GetIdentityValues(_template.tenant, _template.role, _template.roleInstance);

    XJsonBlobBlockCountsMgr::GetInstance().CreatePersistDirIfNotDone();
}


static void
AppendBlobPathComponent(
		const std::string& fieldName,
		const std::string& fieldNameInBlobPath,
		MdsdConfig* config,
		std::string& blobPathComponentString)
{
	if (fieldName.empty()) {
		throw std::invalid_argument("AppendBlobPathComponent(): fieldName cannot be empty");
	}

	auto fieldValue = config->GetOboDirectPartitionFieldValue(fieldName);
	if (fieldValue.empty()) {
		std::string msg = "No CentralJson blob path field value found for field name "
				+ fieldName + ". Make sure that your mdsd config XML contains "
				"OboDirectPartitionField element with the corresponding field name "
				"attribute in Management/Identity section.";
		Logger::LogError(msg);
		throw std::runtime_error(msg);
	}
	if (!blobPathComponentString.empty()) {
		blobPathComponentString.append("/");
	}
	blobPathComponentString.append(fieldNameInBlobPath).append("=").append(fieldValue);
}


void
XJsonBlobSink::InitializeForOboDirect(MdsdConfig* config, const std::shared_ptr<mdsd::OboDirectConfig>& oboDirectConfig)
{
    _blobIntervalISO8601Duration = oboDirectConfig->timePeriods;
    _blobIntervalSec = MdsTime::FromIS8601Duration(_blobIntervalISO8601Duration).to_time_t();
    if (0 == _blobIntervalSec)
    {
        //Logger::LogError("Invalid ISO8601 duration (" + blobIntervalISO8601Duration + ") given. This shouldn't happen. Default 'PT1H' will be used.");
        _blobIntervalSec = 60*60; // 1 hour
        _blobIntervalISO8601Duration = "PT1H";
    }

    const auto& primaryPartitionFieldName = oboDirectConfig->primaryPartitionField; // handy reference
    if (!primaryPartitionFieldName.empty())
    {
    	// Compose primaryPartitionField (e.g., "name1=xxx")
    	AppendBlobPathComponent(primaryPartitionFieldName, primaryPartitionFieldName, config, _template.primaryPartitionField);
    }

    if (!oboDirectConfig->partitionFields.empty())
    {
        // Compose partitionFields (e.g., "name1=xxx/name2=yyy")
        std::istringstream iss(oboDirectConfig->partitionFields); // oboDirectConfig.partitionFields is e.g., 'name1,name2'
        while (iss.good())
        {
            std::string partitionFieldName;
            getline(iss, partitionFieldName, ',');
            if (!partitionFieldName.empty()) {
                AppendBlobPathComponent(partitionFieldName, partitionFieldName, config, _template.partitionFields);
            }
        }
    }
}


void
XJsonBlobSink::InitializeForLadWithoutOboDirect(MdsdConfig* config)
{
	// LAD JsonBlob's interval is fixed to 1 hour.
    _blobIntervalSec = 60*60; // 1 hour
    _blobIntervalISO8601Duration = "PT1H";

    AppendBlobPathComponent("resourceId", "resourceId", config, _template.primaryPartitionField);
    AppendBlobPathComponent("agentIdentityHash", "i", config, _template.agentIdentityHash);
}


void
XJsonBlobSink::ComputeConnString()
{
    Trace trace(Trace::JsonBlob, "XJBS::ComputeConnString");

    const MdsEntityName& Target = _template.target;	// Easy to use reference

    // This is pretty easy for XJsonBlob; we currently support shared-key creds only.
    // expires & eventName don't apply to XJsonBlob (at least yet), so just dummy vars passed.

    MdsTime expires;
    std::string eventName;

    if (_creds->ConnectionString(Target, Credentials::ServiceType::Blob, eventName, _connString, expires) ) {
        TRACEINFO(trace, Target << "=[" << _connString << "] expires " << expires << "(N/A for XJsonBlob)");
    } else {
        Logger::LogError("Error: Couldn't construct connection string for XJsonBlob eventName " + Target.Basename());
    }
}

// The only credentials that need to be validated are "Shared key" or an account SAS; if we have a service SAS or Autokey,
// we'll find out if they work when we try to use them. We can validate shared key credentials
// by creating the container for the eventName, if it doesn't already exist.  Since this gets
// called only during config load, it's reasonable to perform the operation synchronously.
void
XJsonBlobSink::ValidateAccess()
{
    Trace trace(Trace::JsonBlob, "XJBS::ValidateAccess");

    auto sasCreds = dynamic_cast<const CredentialType::SAS*>(_creds);
    if (_creds->Type() == Credentials::SecretType::Key
            || (sasCreds && sasCreds->IsAccountSas())) {
        ComputeConnString();	// Force computation, since this is called at config time
        // "Container name will be the concatenation of namespace, event name, and event version if present."
        // "For example: obodirectnamespacetestevent1ver2v0"
        // from https://microsoft.sharepoint.com/teams/SPS-AzMon/Shared Documents/Design Documents/Direct Mode Design.docx?web=1
        _containerName = MdsdUtil::to_lower(_namespace + _template.target.Basename()); // Azure Storage allows lowercase only in container name
        MdsdUtil::CreateContainer(_connString, _containerName);
    }
}

XJsonBlobSink::~XJsonBlobSink()
{
    Trace trace(Trace::JsonBlob, "XJBS::Destructor");
}

// Convert the CanonicalEntity to Json and add it to the accumulated buffer. Flush it
// if it fills up.
//
// Note that AddRow() doesn't keep the CanonicalEntity; we copy anything we need from it.
void
XJsonBlobSink::AddRow(const CanonicalEntity &row, const MdsTime& qibase)
{
    Trace trace(Trace::JsonBlob, "XJBS::AddRow");

    TRACEINFO(trace, "containerName = " << _containerName << ", blob basetime = " << _blobBaseTime << ", blob interval (sec) = " << _blobIntervalSec << ", qibase = " << qibase);

    // If the query interval is beyond blob base time + blob interval,
    // we should flush the current block and reset the base time accordingly.
    if (qibase >= _blobBaseTime + _blobIntervalSec)
    {
        Flush();
        _blobBaseTime = qibase.Round(_blobIntervalSec); // Make sure to round down to the specified blob interval
        _blockList.reset();
        TRACEINFO(trace, "New blob basetime = " << _blobBaseTime);
    }

    // If we have no in-progress request, either because we just flushed or because we're just
    // starting up, make one.
    if (!_request) {
        try {
            std::string requestId = utility::uuid_to_string(utility::new_uuid());
            if (!_blockList) {
                _blockList = std::make_shared<BlockListT>();
            }
            _request.reset(new XJsonBlobRequest(_template, _blobBaseTime, _blobIntervalISO8601Duration,
                    _containerName, requestId, _blockList));
            // This is the only place we create any XJBReq, so we must check if this is the first time
            // to see if we need to try to reconstruct the block list from a persisted block count file.
            // If there are other places where XJBReq is created, this must be done there as well...
            if (!_firstReqCreated) {
                XJsonBlobRequest::ReconstructBlockListIfNeeded(_request);
                _firstReqCreated = true;
            }
        } catch (std::exception & ex) {
            std::ostringstream msg;
            msg << "Exception (" << ex.what() << ") caught while creating new XJsonBlobRequest; dropping row";
            trace.NOTE(msg.str());
            Logger::LogError(msg.str());
            MdsdMetrics::Count("Dropped_Entities");
            return;
        }
    }

    // The XJsonBlobRequest object stores generated json rows that
    // correspond to the generated rows. The object also contains the metadata needed to
    // determine the name of the blob when it gets written. (This includes a sequence number;
    // if the blob fills, we flush it and start accumulating a new one with an
    // incremented sequence.)

    TRACEINFO(trace, "Adding row to request ID " << _request->UUID() << ": " << row);

    std::string jsonRow;
    try {
        jsonRow = row.GetJsonRow(_template.duration, _template.tenant, _template.role, _template.roleInstance);
    }
    catch (std::exception& e) {
        Logger::LogError(e.what());
        return;
    }

    _request->AddJsonRow(std::move(jsonRow));

    TRACEINFO(trace, "Block now contains " << _request->EstimatedSize() << " bytes");

    // If the size of the accumulated data is "close" to the maximum size of a JSON blob block,
    // flush the block and prepare for the next one

    if (_request->EstimatedSize() > _targetBlockSize) {
        TRACEINFO(trace, "Size of accumulated rows is larger than block size limit; flushing");
        Flush();
    }
}

// Flush any data we're holding. We might never have allocated a request, or it might
// be empty, or we might have data.
// Post-condition: _request is nullptr. Next call to AddRow() will create a new request on demand.
void
XJsonBlobSink::Flush()
{
    Trace trace(Trace::JsonBlob, "XJBS::Flush");

    TRACEINFO(trace, "Begin XJBS::Flush on containerName = " << _containerName);

    if (nullptr == _request) {
        // First time through. Just make the post-condition true
        TRACEINFO(trace, "Null _request; no action.");
        return;
    }
    // XJsonBlob must flush if there's any data. Otherwise, just return.
    if (_request->EstimatedSize() == 0) {
        TRACEINFO(trace, "No data to flush; no action.");
        return;
    }

    TRACEINFO(trace, "Flush() request ID " + _request->UUID());

    if (_request->EstimatedSize() > 0) {
        // Detach the request and send it. Send() is fire-and-forget; the request object
        // is responsible for deleting itself after that point.
        try {
            XJsonBlobRequest::Send(std::move(_request), _connString);
        }
        catch (std::exception & ex) {
            trace.NOTE(std::string("Exception leaked from XJBR Send: ") + ex.what());
        }
    } else {
        // Since we create these on demand, this really shouldn't happen.
        TRACEINFO(trace, "Empty _request; no action (deleting).");
        _request.reset();
    }
}
// vim: se sw=4 expandtab ts=4 :
