// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef __EVENTPERSISTMGR__HH__
#define __EVENTPERSISTMGR__HH__

#include <string>
#include <memory>
#include <atomic>
#include <queue>
#include <functional>
#include "EventData.hh"
#include <pplx/pplxtasks.h>

namespace mdsd { namespace details
{

class PersistFiles;
class EventHubPublisher;

/// <summary>
/// This class implements the functionality to persist events
/// that are failed to be sent to Event Hub. It will save given
/// event to persistence and do regular retry on them. When retry
/// succeeds, the event will be removed from persistence.
/// An event has a max persistence time. After that time, it will
/// be removed from persistence.
/// </summary>
class EventPersistMgr : public std::enable_shared_from_this<EventPersistMgr>
{
    /// <summary>
    /// Construct a new object.
    /// <param name="persistDir"> Directory name to persist data</param>
    /// <param name="maxKeepSeconds"> Max seconds to keep the data. After this time,
    /// It could be removed at any time. </param>
    /// </summary>
    EventPersistMgr(const std::string & persistDir,
                    int32_t maxKeepSeconds);

public:
    static std::shared_ptr<EventPersistMgr> create(
        const std::string & persistDir,
        int32_t maxKeepSeconds)
    {
        return std::shared_ptr<EventPersistMgr>(new EventPersistMgr(persistDir, maxKeepSeconds));
    }

    /// <summary>
    /// NOTE: because this class defines a unique_ptr with forward-declared type,
    /// the destructor must be implemented in the *cc file.
    /// </summary>
    ~EventPersistMgr();

    // movable but not copyable
    EventPersistMgr(const EventPersistMgr& other) = delete;
    EventPersistMgr(EventPersistMgr&& other) = default;
    EventPersistMgr& operator=(const EventPersistMgr& other) = delete;
    EventPersistMgr& operator=(EventPersistMgr&& other) = default;

    /// <summary>
    /// Save given data as persistence object.
    /// Return true if success, false if any error.
    /// If data is empty, return true and do nothing.
    /// </summary>
    bool Add(const EventDataT & data);

    /// <summary> Return number of files on the disk</summary>
    size_t GetNumItems() const;

    /// <summary>
    /// Return number of files read and processed from persist dir.
    /// This doesn't include files deleted when they are too old to keep.
    /// </summary>
    size_t GetNumFileProcessed() const { return m_nFileProcessed; }

    /// <summary>
    /// Go through each persistence object: if it is too old (beyond
    /// max keep time), it will be removed. if it is not too old, it
    /// will be uploaded. If the upload succeeds, it will be removed.
    /// If upload fails, do nothing to it.
    /// Return true if success, false if any error.
    /// </summary>
    bool UploadAllSync(std::shared_ptr<EventHubPublisher> publisher) const;

    /// <summary>
    /// Upload all events asynchronously. This is a "fire and forget"
    /// function. It doesn't wait for the async tasks to finish.
    /// Upload failure will be logged but won't be show in this function
    /// return status.
    /// Return true if success, false if any error.
    /// </summary>
    bool UploadAllAsync(std::shared_ptr<EventHubPublisher> publisher) const;

private:
    /// <summary>
    /// Process the data read from file, including publishing the data to EventHub.
    /// If data are empty, do nothing.
    /// </summary>
    void ProcessFileData(std::shared_ptr<EventHubPublisher> publisher, const std::string & item,
        const EventDataT & itemdata) const;

    /// <summary>
    /// Handle any GetAsync() task failures.
    /// </summary>
    void HandleReadTaskFailure(pplx::task<void> readTask, const std::string & item) const;

    /// <summary>
    /// Return the names of the file to be uploaded. The files that are too old to upload
    /// will be removed from disk.
    /// </summary>
    std::shared_ptr<std::queue<std::string>> GetAllFiles() const;

    pplx::task<bool> UploadOneFile(std::shared_ptr<EventHubPublisher> publisher,
        const std::string & filePath) const;

    void UploadFileBatch(std::shared_ptr<EventHubPublisher> publisher,
        std::shared_ptr<std::queue<std::string>> flist) const;

private:
    std::string m_dirname;                   // Persistence directory full path.
    std::unique_ptr<PersistFiles> m_persist; // The persist mgr persists the data to files.
    int32_t m_maxKeepSeconds;                // max seconds to keep the data.
    mutable std::atomic<size_t> m_nFileProcessed; // number of files read from persistence dir.
};

} // namespace details
} // namespace mdsd

#endif // __EVENTPERSISTMGR__HH__
