// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include <stdexcept>
#include <sstream>
#include <random>
#include <chrono>
#include <iostream>
#include <was/blob.h>
#include <wascore/basic_types.h>

#include "MdsBlobReader.hh"
#include "Trace.hh"

extern "C" {
#include <unistd.h>
}

using namespace azure::storage;
using namespace mdsd::details;

MdsBlobReader::MdsBlobReader(
    std::string storageUri,
    std::string blobName,
    std::string parentPath
    ) :
    m_storageUri(std::move(storageUri)),
    m_blobName(std::move(blobName)),
    m_parentPath(std::move(parentPath))
{
    if (m_storageUri.empty()) {
        throw MDSEXCEPTION("Storage URI cannot be empty.");
    }

    if (!m_parentPath.empty() && m_blobName.empty()) {
        throw MDSEXCEPTION("Blob name cannot be empty when inside a container.");
    }
}

/// Get exception message from exception_ptr
static std::string
GetEptrMsg(std::exception_ptr eptr) // passing by value is ok
{
    try {
        if (eptr) {
            std::rethrow_exception(eptr);
        }
    }
    catch(const std::exception& e) {
        return e.what();
    }
    return std::string();
}

static void
HandleStorageException(
    const storage_exception& ex
    )
{
    auto result = ex.result();
    auto httpcode = result.http_status_code();

    std::ostringstream strm;
    strm << "Error: storage exception in reading MDS blob: "
         << "Http status code=" << httpcode << "; "
         << "Message: " << ex.what() << ". ";

    auto err = result.extended_error();
    if (!err.message().empty()) {
        strm << "Extended info: " << err.message() << ". ";
    }

    auto innerEx = GetEptrMsg(ex.inner_exception());
    if (!innerEx.empty()) {
        strm << "Inner exception: " << innerEx << ".";
    }

    MdsCmdLogError(strm);
}

static operation_context
CreateOperationContext(const std::string& reqId)
{
    operation_context op;
    op.set_client_request_id(reqId);
    return op;
}

static blob_request_options
BlobRequestOptionsWithRetry()
{
    auto requestOpt = blob_request_options();
    exponential_retry_policy retryPolicy;
    requestOpt.set_retry_policy(retryPolicy);
    return requestOpt;
}

cloud_blob
MdsBlobReader::GetBlob() const
{
    Trace trace(Trace::MdsCmd, "MdsBlobReader::GetBlob");

    web::http::uri webUri = {m_storageUri};
    storage_uri uriObj = {webUri};
    cloud_blob blob;
    cloud_blob_container containerObj(uriObj);

    if (m_parentPath.empty()) {
        blob = containerObj.get_blob_reference(m_blobName);
    }
    else {
        auto dirObj = containerObj.get_directory_reference(m_parentPath);

        if (!dirObj.is_valid()) {
            std::ostringstream strm;
            strm << "Failed to get container directory '" << m_parentPath << "'.";
            throw BlobNotFoundException(strm.str());
        }

        blob = dirObj.get_blob_reference(m_blobName);
    }
    auto requestId = utility::uuid_to_string(utility::new_uuid());
    auto op = CreateOperationContext(requestId);

    if (!blob.exists(BlobRequestOptionsWithRetry(), op)) {
        std::ostringstream strm;
        strm << "Failed to find blob '" << m_blobName << "' in parent path '" << m_parentPath << "'."
             << "Request id: " << requestId << ".";
        throw BlobNotFoundException(strm.str());
    }

    return blob;
}

void
MdsBlobReader::ReadBlobToFile(
    const std::string & filepath
    ) const
{
    if (filepath.empty()) {
        throw MDSEXCEPTION("Filepath name to save blob data cannot be empty.");
    }

    std::string requestId;
    try {
        auto blob = GetBlob();
        requestId = utility::uuid_to_string(utility::new_uuid());
        auto op = CreateOperationContext(requestId);
        blob.download_to_file(filepath, access_condition(), BlobRequestOptionsWithRetry(), op);
    }
    catch(const storage_exception & ex)
    {
        HandleStorageException(ex);
        if (!requestId.empty()) {
            MdsCmdLogError("Request id: " + requestId);
        }
    }
    catch(const BlobNotFoundException& ex)
    {
        MdsCmdLogWarn("Specified blob " + m_blobName + " is not found: " + ex.what());
    }
}

std::string
MdsBlobReader::ReadBlobToString() const
{
    Trace trace(Trace::MdsCmd, "MdsBlobReader::ReadBlobToString");

    std::string requestId;

    try {
        auto blob = GetBlob();
        requestId = utility::uuid_to_string(utility::new_uuid());
        auto op = CreateOperationContext(requestId);
        auto streamObj = blob.open_read(access_condition(), BlobRequestOptionsWithRetry(), op);
        concurrency::streams::container_buffer<std::string> cbuf;
        streamObj.read_to_end(cbuf).get();
        streamObj.close();
        return cbuf.collection();
    }
    catch(const storage_exception & ex)
    {
        HandleStorageException(ex);
        if (!requestId.empty()) {
            MdsCmdLogError("Request id: " + requestId);
        }
    }
    catch(const BlobNotFoundException & ex)
    {
        MdsCmdLogWarn("Specified blob " + m_blobName + " is not found: " + ex.what());
    }

    return std::string();
}

pplx::task<std::string>
MdsBlobReader::ReadBlobToStringAsync() const
{
    Trace trace(Trace::MdsCmd, "MdsBlobReader::ReadBlobToStringAsync");

    std::string requestId;

    try {
        auto blob = GetBlob();
        requestId = utility::uuid_to_string(utility::new_uuid());
        auto op = CreateOperationContext(requestId);
        auto asyncReadTask = blob.open_read_async(access_condition(), BlobRequestOptionsWithRetry(), op);
        return asyncReadTask.then([=](concurrency::streams::istream streamObj)
        {
            try
            {
                concurrency::streams::container_buffer<std::string> cbuf;
                streamObj.read_to_end(cbuf).get();
                streamObj.close();
                return cbuf.collection();
            }
            catch (const storage_exception& ex)
            {
                HandleStorageException(ex);
                if (!requestId.empty()) {
                    MdsCmdLogError("Request id: " + requestId);
                }
            }
            return std::string();
        });
    }
    catch(const storage_exception & ex)
    {
        HandleStorageException(ex);
        if (!requestId.empty()) {
            MdsCmdLogError("Request id: " + requestId);
        }
    }
    catch(const BlobNotFoundException & ex)
    {
        MdsCmdLogWarn("Specified blob " + m_blobName + " is not found: " + ex.what());
    }

    return pplx::task<std::string>([](){ return std::string(); });
}


uint64_t
MdsBlobReader::GetLastModifiedTimeStamp(
        std::function<void(const MdsBlobReader*,
                const BlobNotFoundException&)> blobNotFoundExHandler) const
{
    uint64_t lastModifiedTimeStamp = 0;

    std::string requestId;
    try
    {
        auto blob = GetBlob();
        requestId = utility::uuid_to_string(utility::new_uuid());
        auto op = CreateOperationContext(requestId);
        blob.download_attributes(access_condition(), BlobRequestOptionsWithRetry(), op);
        lastModifiedTimeStamp = blob.properties().last_modified().to_interval();
    }
    catch(const storage_exception & ex)
    {
        HandleStorageException(ex);
        if (!requestId.empty()) {
            MdsCmdLogError("Request id: " + requestId);
        }
    }
    catch(const BlobNotFoundException & ex)
    {
        blobNotFoundExHandler(this, ex);
    }

    return lastModifiedTimeStamp;
}


pplx::task<uint64_t>
MdsBlobReader::GetLastModifiedTimeStampAsync(
        std::function<void(const MdsBlobReader*,
                const BlobNotFoundException&)> blobNotFoundExHandler) const
{
    uint64_t lastModifiedTimeStamp = 0;

    std::string requestId;
    try
    {
        auto blob = GetBlob();
        requestId = utility::uuid_to_string(utility::new_uuid());
        auto op = CreateOperationContext(requestId);
        auto asyncAttrDownloadTask = blob.download_attributes_async(access_condition(), BlobRequestOptionsWithRetry(), op);
        return asyncAttrDownloadTask.then([=]()
        {
            return blob.properties().last_modified().to_interval();
        });
    }
    catch(const storage_exception & ex)
    {
        HandleStorageException(ex);
        if (!requestId.empty()) {
            MdsCmdLogError("Request id: " + requestId);
        }
    }
    catch(const BlobNotFoundException & ex)
    {
        blobNotFoundExHandler(this, ex);
    }

    return pplx::task<uint64_t>([=]()
    {
        return lastModifiedTimeStamp; // = 0
    });
}
