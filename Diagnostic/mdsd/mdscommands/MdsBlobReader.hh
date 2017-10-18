// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef __MDSBLOBREADER__HH__
#define __MDSBLOBREADER__HH__

#include <string>
#include <vector>
#include <cpprest/streams.h>
#include <cpprest/pplx/pplxtasks.h>

#include "MdsException.hh"
#include "MdsCmdLogger.hh"

namespace azure
{
    namespace storage {
        class cloud_blob;
    }
} // namespace azure

namespace mdsd { namespace details
{

/// <summary>
/// Implement a class to read blob from azure storage related to MDS.
/// </summary>
class MdsBlobReader
{
public:
    /// <summary>
    /// Construct a new blob reader.
    /// <param name="storageUri"> The absolute URI to the blob root container</param>
    /// <param name="blobName"> blob name </param>
    /// <param name="parentPath"> the given blob's parent container name</param>
    /// </summary>
    MdsBlobReader(std::string storageUri,
                  std::string blobName = "",
                  std::string parentPath = "");

    ~MdsBlobReader() {}

    MdsBlobReader(const MdsBlobReader& other) = default;
    MdsBlobReader(MdsBlobReader&& other) = default;
    MdsBlobReader& operator=(const MdsBlobReader& other) = default;
    MdsBlobReader& operator=(MdsBlobReader&& other) = default;

    /// <summary> Read current blob object to a given file. </summary>
    void ReadBlobToFile(const std::string & filepath) const;

    /// <summary>
    /// Read current blob object to a string.
    /// Return the blob content, or empty string if any error.
    /// </summary>
    std::string ReadBlobToString() const;

    /// <summary>
    /// Start async reading of current blob object to a string.
    /// Return the task whose result will be the string.
    /// </summary>
    pplx::task<std::string> ReadBlobToStringAsync() const;

    /// <summary>
    /// Returns the read blob's LMT (# seconds since epoch).
    /// 0 will be returned if blob doesn't exist
    /// or if any exception is thrown (e.g., storage exception)
    /// </summary>
    uint64_t GetLastModifiedTimeStamp(
            std::function<void(const MdsBlobReader*,
                    const BlobNotFoundException&)> blobNotFoundExHandler) const;

    /// <summary>
    /// Start async reading of blob's LMT (# seconds since epoch).
    /// Return the task whose result will be the the blob's LMT.
    /// </summary>
    pplx::task<uint64_t> GetLastModifiedTimeStampAsync(
            std::function<void(const MdsBlobReader*,
                    const BlobNotFoundException&)> blobNotFoundExHandler) const;

    // Typical BlobNotFoundException handlers provided here
    static void DoNothingBlobNotFoundExHandler(const MdsBlobReader*, const BlobNotFoundException&) {}
    static void LogWarnBlobNotFoundExHandler(const MdsBlobReader*, const BlobNotFoundException& ex)
    {
        MdsCmdLogWarn("Specified blob is not found: " + std::string(ex.what()));
    }

private:
    /// <summary>
    /// Get current blob object.
    /// </summary>
    azure::storage::cloud_blob GetBlob() const;

private:
    std::string m_storageUri;
    std::string m_blobName;
    std::string m_parentPath;
};

} // namespace details
} // namespace mdsd

#endif // __MDSBLOBREADER__HH__
