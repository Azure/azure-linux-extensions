// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _EVENTHUBUPLOADERMGR_HH_
#define _EVENTHUBUPLOADERMGR_HH_

#include "EventHubUploader.hh"
#include "EventHubType.hh"
#include <string>
#include <unordered_map>
#include <map>
#include <set>
#include <unordered_set>
#include <memory>
#include <utility>
#include <boost/thread/shared_mutex.hpp>

namespace mdsd {

struct EventHubUploaderId;

// Using the singleton pattern
class EventHubUploaderMgr
{
public:
    static EventHubUploaderMgr& GetInstance();

    EventHubUploaderMgr(const EventHubUploaderMgr &) = delete;
    EventHubUploaderMgr(EventHubUploaderMgr&&) = delete;
    EventHubUploaderMgr& operator=(const EventHubUploaderMgr&) = delete;
    EventHubUploaderMgr& operator=(EventHubUploaderMgr&&) = delete;

    bool SetTopLevelPersistDir(const std::string& persistDirTopLevel);
    /// <summary>
    /// Create EventHub uploaders for different EventHubType, moniker, eventname.
    /// </summary>
    /// <param name="eventMonikerMap">key: eventname; value: monikernames. </param>
    void CreateUploaders(EventHubType ehtype,
        const std::unordered_map<std::string, std::unordered_set<std::string>> & eventMonikerMap);

    /// <summary>
    /// Set SAS Key for given EventHub uploader identified by an id string.
    /// Return true if the SAS key is set; return false otherwise.
    /// </summary>
    bool SetSasAndStart(const EventHubUploaderId& uploaderId, const std::string & ehSas);

    /// <summary>
    /// Add an EventHub data item to EventHub data uploader identified by an id string.
    /// Return true if data is added to uploader; return false otherwise.
    /// <summary>
    bool AddMessageToUpload(const EventHubUploaderId& uploaderId, EventDataT&& eventData);

    size_t GetNumUploaders() const { return m_ehUploaders.size(); }

    /// <summary>
    /// Wait for given time for all data to be uploaded.
    /// Return until all data are uploaded or timed out.
    /// maxMilliSeconds=-1 means forever.
    /// </summary>
    void WaitForFinish(int32_t maxMilliSeconds);

private:
    EventHubUploaderMgr() {}
    ~EventHubUploaderMgr() {}

    // Top-level directory for persisting EventHub messages.
    // There'll be a subdirectory for each accountmoniker/eventname combination.
    std::string m_persistDirTopLevel;    // e.g., "/var/mdsd"

    // Collection of all EHUploader objects
    typedef std::unique_ptr<EventHubUploader> EhUploader_t;
    std::map<std::string, EhUploader_t> m_ehUploaders;

    // multiple readers single writer locks for EH uploaders map.
    // NOTE: C++14 has std::shared_timed_mutex that can do the same thing. But it is not
    // available until GCC5.0.
    boost::shared_mutex m_mapMutex;

    std::string CreateAndGetPersistDir(EventHubType ehtype, const std::string& moniker,
        const std::string& eventname);

    EventHubUploader* GetUploader(const std::string & uploaderId);


    std::set<std::pair<std::string, std::string>> GetNewItemSet(
        EventHubType ehtype,
        const std::unordered_map<std::string, std::unordered_set<std::string>> & eventMonikerMap);

    std::set<std::pair<std::string, std::string>> GetDroppedItemSet(
        EventHubType ehtype,
        const std::unordered_map<std::string, std::unordered_set<std::string>> & eventMonikerMap);

};

} // namespace mdsd

#endif // _EVENTHUBUPLOADERMGR_HH_
