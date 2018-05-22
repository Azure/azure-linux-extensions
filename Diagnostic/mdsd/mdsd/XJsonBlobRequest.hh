// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _XJSONBLOBREQUEST_HH_
#define _XJSONBLOBREQUEST_HH_

#include "XJsonBlobSink.hh"
#include "MdsTime.hh"
#include <string>
#include <vector>
#include <memory>
#include <mutex>

#include <was/storage_account.h>
#include <was/blob.h>
#include <was/common.h>

class XJsonBlobRequest
{
public:
	XJsonBlobRequest(
	        const XJsonBlobSink::RequestInfo& info,
	        const MdsTime& blobBaseTime,
	        const std::string& blobIntervalISO8601Duration,
	        const std::string& containerName,
	        const std::string& reqId,
	        const std::shared_ptr<BlockListT>& blocklist);

	~XJsonBlobRequest();

	static void Send(
	        std::shared_ptr<XJsonBlobRequest> req,
	        const std::string & connString);

	const std::string & UUID() const { return _requestId; }

	size_t EstimatedSize() const { return _totalDataBytes; }

	void AddJsonRow(std::string&& jsonRow);

	static void ReconstructBlockListIfNeeded(std::shared_ptr<XJsonBlobRequest> req);

private:
	static pplx::task<void> UploadNewBlockAsync(const std::shared_ptr<XJsonBlobRequest>& req);
	static pplx::task<void> UploadBlockListAsync(const std::shared_ptr<XJsonBlobRequest>& req);

	XJsonBlobSink::RequestInfo    _info;

	std::string _containerName;
	std::string _blobName;

	MdsTime _blobBaseTime;  // Base time for the current blob

	// As we add a new _rowbuf to the collection, we accumulate its size so we know when we hit
	// maximum length.

	size_t		_totalDataBytes;
	std::vector<std::string> _dataset;

	// UUID for this request; attached to storage request(s) end-to-end
	std::string _requestId;

	// Async request handling members
	azure::storage::cloud_block_blob _blobRef;
	std::shared_ptr<BlockListT> _blockList;
	std::string _newBlockId;
	std::string _newBlockContent;
};

#endif // _XJSONBLOBREQUEST_HH_

// vim: se ai sw=8 :
