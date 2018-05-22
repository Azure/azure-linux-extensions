// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "XJsonBlobBlockCountsMgr.hh"
#include "Utility.hh"
#include "Trace.hh"
#include <stdexcept>
#include <memory>
#include <system_error>
#include <sstream>
#include <cpprest/filestream.h>
#include <cpprest/containerstream.h>
#include <stdio.h>


XJsonBlobBlockCountsMgr&
XJsonBlobBlockCountsMgr::GetInstance()
{
    static XJsonBlobBlockCountsMgr s_instance;
    return s_instance;
}


void
XJsonBlobBlockCountsMgr::SetPersistDir(const std::string& persistDir, bool mdsdConfigValidationOnly)
{
    Trace trace(Trace::JsonBlob, "XJsonBlobBlockCountsMgr::SetPersistDir");

    TRACEINFO(trace, "persistDir=\"" << persistDir << "\"");

    if (persistDir.empty()) {
        throw std::invalid_argument("persistDir can't be empty.");
    }
    m_persistDir = persistDir;
    m_mdsdConfigValidationOnly = mdsdConfigValidationOnly;
}


void
XJsonBlobBlockCountsMgr::CreatePersistDirIfNotDone()
{
    Trace trace(Trace::JsonBlob, "XJsonBlobBlockCountsMgr::CreatePersistDirIfNotDone");

    if (m_persistDirCreated || m_mdsdConfigValidationOnly) {
        return;
    }

    if (m_persistDir.empty()) {
        throw std::runtime_error("Jsonblob block counts persist dir is not set.");
    }

    MdsdUtil::CreateDirIfNotExists(m_persistDir, 01755);

    m_persistDirCreated = true;
}


pplx::task<size_t>
XJsonBlobBlockCountsMgr::ReadBlockCountAsync(
        const std::string& containerName,
        const std::string& blobName) const
{
    Trace trace(Trace::JsonBlob, "XJsonBlobBlockCountsMgr::ReadBlockCountAsync");

    if (m_mdsdConfigValidationOnly) {
        throw std::runtime_error("XJsonBlobBlockCountsMgr::ReadBlockCountAsync: Can't be called when mdsd config validation only");
    }

    if (containerName.empty()) {
        throw std::invalid_argument("XJsonBlobBlockCountsMgr::ReadBlockCountAsync: containerName can't be empty.");
    }
    if (blobName.empty()) {
        throw std::invalid_argument("XJsonBlobBlockCountsMgr::ReadBlockCountAsync: blobName can't be empty.");
    }

    std::string file_path(m_persistDir);
    file_path.append("/").append(containerName);

    // If there's no block-count file, then the block count is just 0.
    if (!MdsdUtil::IsRegFileExists(file_path)) {
        return pplx::task_from_result((size_t)0);
    }

    return concurrency::streams::fstream::open_istream(file_path)
    .then([=](concurrency::streams::istream inFile) -> pplx::task<size_t>
    {
        concurrency::streams::container_buffer<std::string> streamBuffer;
        return inFile.read_to_end(streamBuffer)
        .then([=](size_t bytesRead) -> pplx::task<size_t>
        {
            if (bytesRead == 0 && inFile.is_eof()) {
                // Invalid file format. Treat it silently as 0 block count.
                return pplx::task_from_result((size_t)0);
            }

            std::istringstream iss(streamBuffer.collection());
            std::string blobNameInFile;
            iss >> blobNameInFile;

            if (blobNameInFile != blobName) {
                // Persisted block count is for the past, so the block count for the current blob should be 0.
                return pplx::task_from_result((size_t)0);
            }

            size_t blockCountInFile;
            iss >> blockCountInFile;
            return pplx::task_from_result(blockCountInFile);
        })
        .then([=](size_t blockCount) -> pplx::task<size_t>
        {
            return inFile.close()
            .then([=]() -> pplx::task<size_t>
            {
                return pplx::task_from_result(blockCount);
            });
        });
    });
}


pplx::task<void>
XJsonBlobBlockCountsMgr::WriteBlockCountAsync(
        const std::string& containerName,
        const std::string& blobName,
        const size_t blockCount) const
{
    Trace trace(Trace::JsonBlob, "XJsonBlobBlockCountsMgr::WriteBlockCountAsync");

    if (m_mdsdConfigValidationOnly) {
        throw std::runtime_error("XJsonBlobBlockCountsMgr::WriteBlockCountAsync: Can't be called when mdsd config validation only");
    }

    if (containerName.empty()) {
        throw std::invalid_argument("XJsonBlobBlockCountsMgr::WriteBlockCountAsync: containerName can't be empty.");
    }
    if (blobName.empty()) {
        throw std::invalid_argument("XJsonBlobBlockCountsMgr::WriteBlockCountAsync: blobName can't be empty.");
    }
    if (blockCount == 0) {
        throw std::invalid_argument("XJsonBlobBlockCountsMgr::WriteBlockCountAsync: 0 blockCount is not allowed.");
    }

    // m_persistDir + "/" + containerName is the full file path.
    // blobName and blockCount are the only content in the file.
    // First write to a tmp file path and then rename it to the correct path
    std::string file_path(m_persistDir);
    file_path.append("/").append(containerName);
    std::string file_path_tmp(file_path);
    file_path_tmp.append(".tmp");

    return concurrency::streams::fstream::open_ostream(file_path_tmp)
    .then([=](concurrency::streams::ostream outFile) -> pplx::task<void>
    {
        std::string content(blobName);
        content.append("\n").append(std::to_string(blockCount)).append("\n");
        return outFile.print(content)
        .then([=](size_t) -> pplx::task<void>
        {
            return outFile.close();
        });
    })
    .then([=]() -> pplx::task<void>
    {
        if (-1 == rename(file_path_tmp.c_str(), file_path.c_str())) {
            auto errnum = errno;
            std::error_code ec(errnum, std::system_category());
            throw std::runtime_error(std::string("XJsonBlobBlockCountsMgr::WriteBlockCountAsync: "
                    "rename(").append(file_path_tmp).append(", ").append(file_path).append(" failed. "
                            "Reason: ").append(ec.message()));
        }

        return pplx::task_from_result();
    });
}
