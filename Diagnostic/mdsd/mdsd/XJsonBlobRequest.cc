// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "XJsonBlobRequest.hh"
#include "XJsonBlobBlockCountsMgr.hh"
#include <string>
#include <map>
#include "MdsTime.hh"
#include "Constants.hh"
#include "Crypto.hh"
#include "Logger.hh"
#include "Trace.hh"
#include "Utility.hh"
#include "AzureUtility.hh"
#include "Version.hh"
#include <cassert>
#include <type_traits>
#include <cstring>
#include <stdexcept>
#include <iomanip>
#include <chrono>

#include <stdafx.h>
#include <was/storage_account.h>
#include <was/blob.h>
#include <was/common.h>
#include <wascore/streams.h>

XJsonBlobRequest::XJsonBlobRequest(
        const XJsonBlobSink::RequestInfo& info,
        const MdsTime& blobBaseTime,
        const std::string& blobIntervalISO8601Duration,
        const std::string& containerName,
        const std::string& reqId,
        const std::shared_ptr<BlockListT>& blocklist)
	: _info(info), _blobBaseTime(blobBaseTime),
	  _containerName(containerName), _requestId(reqId), _totalDataBytes(0),
	  _blockList(blocklist)
{
	Trace trace(Trace::JsonBlob, "XJBR::XJBR, reqId=" + _requestId);

	if (blobIntervalISO8601Duration.empty()) {
		throw std::invalid_argument("Empty string param (blobIntervalISO8601Duration)");
	}
	if (containerName.empty()) {
		throw std::invalid_argument("Empty string param (containerName)");
	}
	if (reqId.empty()) {
		throw std::invalid_argument("Empty string param (reqId)");
	}
	if (!blocklist) {
		throw std::invalid_argument("Null blocklist");
	}

	// Blob name example: resourceId=test_resource_id/i=agentIdentityHash/y=2015/m=05/d=03/h=00/m=00/name=PT1H.json
	std::stringstream blobnamestr;
	if (!_info.primaryPartitionField.empty()) {
	    blobnamestr << _info.primaryPartitionField << '/';
	}
	if (!_info.agentIdentityHash.empty()) {
		blobnamestr << _info.agentIdentityHash << '/';
	}
	blobnamestr << blobBaseTime.to_strftime("y=%Y/m=%m/d=%d/h=%H/m=%M/");
	if (!_info.partitionFields.empty())	{
	    blobnamestr << _info.partitionFields << '/';
	}
	blobnamestr << blobIntervalISO8601Duration <<".json";
	_blobName = blobnamestr.str();
	TRACEINFO(trace, "Preliminary blobname " << _blobName);
}


XJsonBlobRequest::~XJsonBlobRequest()
{
    // Just to see that this fire-and-forget object is really destructed.
    Trace trace(Trace::JsonBlob, "XJBR::~XJBR, reqId=" + _requestId);
}


static const std::string jsonRowSeparator(",\n");

void
XJsonBlobRequest::AddJsonRow(std::string&& jsonRow)
{
    Trace trace(Trace::JsonBlob, "XJBR::AddJsonRow");

    if (jsonRow.empty()) {
        TRACEINFO(trace, "Empty jsonRow string passed. Nothing to do. Return");
        return;
    }

    if (!_dataset.empty()) {
        _totalDataBytes += jsonRowSeparator.length();
    }
    _totalDataBytes += jsonRow.size();
    _dataset.emplace_back(std::move(jsonRow));

    TRACEINFO(trace, "# rows in dataset = " << _dataset.size() << ", total data bytes = " << _totalDataBytes);
}


static std::string
GetStorageExceptionDetails(const azure::storage::storage_exception& e)
{
    std::ostringstream oss;
    oss << "Storage exception: " << e.what();

    azure::storage::request_result result = e.result();
    azure::storage::storage_extended_error err = result.extended_error();
    if (!err.message().empty()) {
        oss << ", Extended info: " << err.message();
    }

    oss << ", HTTP status code: " << std::to_string(result.http_status_code());

    return oss.str();
}


class XJBRAsyncTaskError : public std::runtime_error
{
public:
    XJBRAsyncTaskError(const std::string& taskName, const std::string& message)
        : std::runtime_error(message), _taskName(taskName) {}

    std::string GetTaskName() const { return _taskName; }

private:
    std::string _taskName;
};

// Used to synchronize access to a BlockList. A std::shared_ptr<BlockListOwner> should stay alive
// while exclusive access to the BlockList is needed across tasks/threads. The wrapping 
// std::shared_ptr<BlockListOwner> will provide copy counting, and will only deconstruct
// the BlockListOwner when the last instance of the wrapping std::shared_ptr<BlockListOwner> is 
// deconstructed.
struct BlockListOwner
{
    std::shared_ptr<BlockListT> _blockList;
    const std::string _ownerName;
    const std::string _requestId;

    BlockListOwner(std::shared_ptr<BlockListT> blockList, const std::string& ownerName, const std::string& requestId) : 
        _blockList(blockList), _ownerName(ownerName), _requestId(requestId)
    {
        Trace trace(Trace::JsonBlob, "BlockListOwner::BlockListOwner");
        TRACEINFO(trace, "Attempting to set block list owner for " << _requestId << " to " << _ownerName);
        _blockList->LockIfOwnedByNoneThenSetOwner(_ownerName);
        TRACEINFO(trace, "Set block list owner for " << _requestId << " to " << _ownerName);
    }
    ~BlockListOwner()
    {
        Trace trace(Trace::JsonBlob, "BlockListOwner::~BlockListOwner");
        TRACEINFO(trace, "Resetting block list owner for " << _requestId << " (currently " << _ownerName << ")");
        _blockList->ResetOwnerAndNotify();
    }
};


/*static*/ void
XJsonBlobRequest::Send(
        std::shared_ptr<XJsonBlobRequest> req,
        const std::string& connString)
{
	Trace trace(Trace::JsonBlob, "XJBR::Send id=" + req->_requestId);

	if (!req) {
        Logger::LogWarn("XJBR::Send(): Null request was passed. This shouldn't happen. Returning anyway...");
        return;
	}

	if (req->_dataset.empty()) {
	    Logger::LogWarn("Nothing to upload to the XJsonBlob blob " + req->_blobName + ". Returning...");
	    return;
	}

	try	{
	    TRACEINFO(trace, "Get reference to container/blob " << req->_containerName << "/" << req->_blobName);
	    auto cloudStorageAccount = azure::storage::cloud_storage_account::parse(connString);

	    // The endpoint URL and storage account are not really needed, but just for informational purpose...
	    auto endpointURL = cloudStorageAccount.blob_endpoint().primary_uri().to_string();
	    std::string storageAccountName = MdsdUtil::GetStorageAccountNameFromEndpointURL(endpointURL);

	    TRACEINFO(trace, "Storage endpoint URL: " << endpointURL << ", extracted storage account name: "
	            << storageAccountName << ", requestId: " << req->_requestId);

	    req->_blobRef =
	            cloudStorageAccount
	            .create_cloud_blob_client()
	            .get_container_reference(req->_containerName)
	            .get_block_blob_reference(req->_blobName);

        // Start only when the mutex is not owned by any other request.
        // Owner name really doesn't matter as long as it's non-empty. 
        // requestId is only for logging.
        auto blockListOwner = std::make_shared<BlockListOwner>(req->_blockList, req->_blobName, req->_requestId);

        XJsonBlobRequest::UploadNewBlockAsync(req)
        .then([req]() -> pplx::task<void>
        {
            // This is a value-based continuation, so if the previous task throws,
            // this task is not executed, so no need to do wait on prev_task.

            return XJsonBlobRequest::UploadBlockListAsync(req);
        })
        .then([req]() -> pplx::task<void>
        {
            // Another value-based continuation

            return XJsonBlobBlockCountsMgr::GetInstance().WriteBlockCountAsync(req->_containerName, req->_blobName, req->_blockList->get().size());
        })
        // Copy capture the BlockListOwner so that it stays alive through this
        // continuation task.
        .then([req, blockListOwner](pplx::task<void> prev_task)
        {
            // This is a task-based continuation, so this task will be executed
            // even if any previous task throws.

            Trace trace(Trace::JsonBlob, "XJBR::Send final continuation task, req id=" + req->_requestId);

            try {
                // Wait, to handle prev async task exceptions right away
                prev_task.wait();

                // There were no exceptions if we reached this point.
                if (trace.IsActive()) {
                    TRACEINFO(trace, "Added new block to blob [" << req->_blobName << "]. Now there are "
                            << req->_blockList->get().size() << " blocks in the blob.");
                }
            }
            catch (const XJBRAsyncTaskError& e) {
                Logger::LogError(e.GetTaskName().append(": ").append(e.what()));
            }
            catch (const std::exception& e) {
                Logger::LogError(std::string("[XJBR::UploadBlockListCompletion]: ").append(e.what()));
            }
            catch (...) {
                // Don't leak any exception from this async function body
                Logger::LogError("[XJBR::UploadBlockListCompletion]: Unknown exception");
            }
        });
	}
	catch (const azure::storage::storage_exception& e) {
        Logger::LogError("Storage exception generated while starting async blob write: " + GetStorageExceptionDetails(e));
	}
	catch (const std::exception& e) {
	    Logger::LogError(std::string("Exception generated while starting async blob write: ").append(e.what()));
	}
	catch (...) {
	    Logger::LogError("Unknown exception generated while starting async blob write");
	}
}

static std::string
GetBase64HashString(const std::string& content)
{
    azure::storage::core::hash_provider provider = azure::storage::core::hash_provider::create_md5_hash_provider();
    provider.write((const unsigned char*)content.c_str(), content.length());
    provider.close();
    return provider.hash();
}


static constexpr size_t maxBlocksInBlob = 50000;

static const std::string first_block_id = utility::conversions::to_base64(0);
static const std::string first_block_content = "{\"records\":[\n";
static const std::string last_block_id = utility::conversions::to_base64(maxBlocksInBlob - 1); // 49999
static const std::string last_block_content = "\n]}";


/*static*/ pplx::task<void>
XJsonBlobRequest::UploadNewBlockAsync(
        const std::shared_ptr<XJsonBlobRequest>& req)
{
    Trace trace(Trace::JsonBlob, "XJBR::UploadNewBlock id=" + req->_requestId);

    if (!req) {
        throw std::invalid_argument("Null shared_ptr<XJsonBlobRequest>");
    }

    // Handy references
    auto& blobRef = req->_blobRef;
    auto& blockList = req->_blockList->get();
    auto& blobName = req->_blobName;
    auto& newBlockId = req->_newBlockId;
    auto& newBlockContent = req->_newBlockContent;

    if (blockList.size() >= maxBlocksInBlob) {
        std::ostringstream ss;
        ss << "Can't add any more block to blob " << blobName
           << ". There are already max blobs (" << blockList.size() << ") in the blob.";
        throw XJBRAsyncTaskError("XJBR::UploadNewBlockAsync", ss.str());
    }

    if (!blockList.empty() && blockList.size() < 2) {
        throw XJBRAsyncTaskError("XJBR::UploadNewBlockAsync",
                "Blob format error: No first/last blocks in " + blobName + ".  Returning...");
    }

    if (!blockList.empty()
            && (blockList.front().id() != first_block_id || blockList.back().id() != last_block_id)) {
        throw XJBRAsyncTaskError("XJBR::UploadNewBlockAsync", "Blob format error: First block id ("
                + blockList.front().id() + ") or last block id ("
                + blockList.back().id() + ") is incorrect in " + blobName + ". Returning.");
    }

    std::vector<pplx::task<void>> blockUploadTasks; // maximum 3 uploads

    if (blockList.empty()) {
        TRACEINFO(trace, "Blob " << blobName << " is empty. Adding first/last blocks.");

        auto first_block_stream = concurrency::streams::bytestream::open_istream(first_block_content);
        auto taskUploadFirstBlock = blobRef.upload_block_async(first_block_id, first_block_stream, GetBase64HashString(first_block_content));
        blockUploadTasks.push_back(taskUploadFirstBlock);

        auto last_block_stream = concurrency::streams::bytestream::open_istream(last_block_content);
        auto taskUploadLastBlock = blobRef.upload_block_async(last_block_id, last_block_stream, GetBase64HashString(last_block_content));
        blockUploadTasks.push_back(taskUploadLastBlock);
    }

    // Add the new block. New block's id # is blockList.size() - 2 (first/last) + 1 (new block).
    // Above is correct only for non-empty block list. Empty block list case needs to be handled
    // as a special case, as we don't want to update the block list until blocks are really uploaded.
    size_t newBlockNum = blockList.empty() ? 1 : (blockList.size() - 1);
    newBlockId = utility::conversions::to_base64(newBlockNum);
    TRACEINFO(trace, "Adding a new block (numeric ID=" << newBlockNum
            << ", base64 ID=" << newBlockId << ") to blob " << blobName);

    // Construct the new block content.
    newBlockContent.reserve(req->_totalDataBytes + jsonRowSeparator.length());    // + 2 for possible preceding ",\n"
    if (blockList.size() > 2) {
        // Not the first content block, so prepend ","
        newBlockContent.append(jsonRowSeparator);
    }
    bool first = true;
    for (const auto& row : req->_dataset) {
        if (first) {
            first = false;
        }
        else {
            newBlockContent.append(jsonRowSeparator);
        }
        newBlockContent.append(row);
    }
    auto new_block_stream = concurrency::streams::bytestream::open_istream(newBlockContent);
    auto taskUploadContentBlock = blobRef.upload_block_async(newBlockId, new_block_stream, GetBase64HashString(newBlockContent));
    blockUploadTasks.push_back(taskUploadContentBlock);

    return pplx::when_all(blockUploadTasks.begin(), blockUploadTasks.end());
}


/*static*/ pplx::task<void>
XJsonBlobRequest::UploadBlockListAsync(const std::shared_ptr<XJsonBlobRequest>& req)
{
    Trace trace(Trace::JsonBlob, "XJBR::UploadBlockListAsync, req id=" + req->_requestId);

    // handy references
    auto& request = *req;
    auto& blockList = request._blockList->get();

    // Update block list only after block(s) is/are uploaded successfully
    if (blockList.empty()) {
        blockList.emplace_back(azure::storage::block_list_item(first_block_id));
        blockList.emplace_back(azure::storage::block_list_item(last_block_id));
    }
    blockList.insert(blockList.end() - 1, azure::storage::block_list_item(request._newBlockId));

    // Finally upload the block list!
    return request._blobRef.upload_block_list_async(blockList);
}


/*static*/ void
XJsonBlobRequest::ReconstructBlockListIfNeeded(std::shared_ptr<XJsonBlobRequest> req)
{
    Trace trace(Trace::JsonBlob, "XJBR::ReconstructBlockListIfNeeded");

    if (!req->_blockList->get().empty()) {
        throw std::runtime_error("XJBR::ReconstructBlockListIfNeeded: Block list is not empty.");
    }

    // Start only when the mutex is not owned by any other request.
    // Owner name really doesn't matter as long as it's non-empty.
    auto blockListOwner = std::make_shared<BlockListOwner>(req->_blockList, req->_blobName, req->_requestId);

    // Copy capture the BlockListOwner so that it stays alive through the
    // continuation task.
    XJsonBlobBlockCountsMgr::GetInstance().ReadBlockCountAsync(req->_containerName, req->_blobName)
    .then([req, blockListOwner](pplx::task<size_t> prev_task)
    {
        Trace trace(Trace::JsonBlob, "XJBR::ReconstructBlockListIfNeeded continuation");
        TRACEINFO(trace, "In XJBR::ReconstructBlockListIfNeeded continuation.");

        try {
            auto blockCount = prev_task.get();

            TRACEINFO(trace, "Obtained blockCount=" << blockCount
                    << " for container=" << req->_containerName << " and blob=" << req->_blobName);

            if (blockCount == 0) {
                return;
            }

            if (blockCount < 3  // A persisted block count is always at least 3 blocks.
                                // "{ ..." for first block, "}" for last block, at least one content block.
                    || blockCount > maxBlocksInBlob) {
                Logger::LogError(std::string("Invalid block count (").append(std::to_string(blockCount))
                        .append(") returned from XJBBlockCountsMgr::ReadBlockCount. "
                        "Valid block count is at least 3 and at most ").append(std::to_string(maxBlocksInBlob))
                        .append(". Block list won't be reconstructed."));
                return;
            }

            // Finally we can reconstruct the block list.
            auto& blockList = req->_blockList->get();
            blockList.emplace_back(azure::storage::block_list_item(first_block_id));
            size_t lastBlockNum = blockCount - 2;
            for (size_t blockNum = 1; blockNum <= lastBlockNum; blockNum++) {
                blockList.emplace_back(azure::storage::block_list_item(utility::conversions::to_base64(blockNum)));
            }
            blockList.emplace_back(azure::storage::block_list_item(last_block_id));
        }
        catch (std::exception& e) {
            Logger::LogError(std::string("Exception thrown from XJBBlockCountsMgr::ReadBlockCount. "
                    "Block list can't be reconstructed. Exception message: ").append(e.what()));
        }
        catch (...) {
            Logger::LogError("Unknown exception thrown from XJBBlockCountsMgr::ReadBlockCount. "
                    "Block list can't be reconstructed");
        }
    });
    TRACEINFO(trace, "After ReadBlockCountAsync.");
}


// vim: se sw=8 :
