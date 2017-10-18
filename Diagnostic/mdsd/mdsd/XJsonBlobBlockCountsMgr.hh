// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef __XJSONBLOBBLOCKCOUNTSMGR_HH__
#define __XJSONBLOBBLOCKCOUNTSMGR_HH__

#include <string>
#include <cpprest/pplx/pplxtasks.h>

// Singleton pattern
class XJsonBlobBlockCountsMgr
{
public:
    static XJsonBlobBlockCountsMgr& GetInstance();

    XJsonBlobBlockCountsMgr(const XJsonBlobBlockCountsMgr&) = delete;
    XJsonBlobBlockCountsMgr(XJsonBlobBlockCountsMgr&&) = delete;
    XJsonBlobBlockCountsMgr& operator=(const XJsonBlobBlockCountsMgr&) = delete;
    XJsonBlobBlockCountsMgr& operator=(XJsonBlobBlockCountsMgr&&) = delete;

    // Called from main() after mdsd_prefix is determined.
    void SetPersistDir(const std::string& persistDir, bool mdsdConfigValidationOnly);

    // Called from XJsonBlobSink::XJsonBlobSink()
    void CreatePersistDirIfNotDone();

    pplx::task<size_t> ReadBlockCountAsync(const std::string& containerName, const std::string& blobName) const;

    pplx::task<void> WriteBlockCountAsync(const std::string& containerName, const std::string& blobName, const size_t blockCount) const;

private:
    XJsonBlobBlockCountsMgr() : m_persistDirCreated(false), m_mdsdConfigValidationOnly(false) {}
    ~XJsonBlobBlockCountsMgr() {}

    bool m_persistDirCreated;
    bool m_mdsdConfigValidationOnly;
    std::string m_persistDir;   // e.g., "/var/run/mdsd/default_jsonblob_block_counts"
};

#endif // __XJSONBLOBBLOCKCOUNTSMGR_HH__
