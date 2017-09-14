// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "EventHubUploaderMgr.hh"
#include "EventHubUploaderId.hh"
#include "Utility.hh"
#include "Trace.hh"
#include "Logger.hh"
#include <stdexcept>
#include <set>
#include <cpprest/pplx/threadpool.h>

using namespace mdsd;
using namespace mdsd::details;

EventHubUploaderMgr&
EventHubUploaderMgr::GetInstance()
{
    // Because EventHubUploader's destructor will use pplx threadpool tasks, make sure
    // the static threadpool is created first. First created will be last destroyed.
    crossplat::threadpool::shared_instance();
    static EventHubUploaderMgr s_instance;
    return s_instance;
}

bool
EventHubUploaderMgr::SetTopLevelPersistDir(
    const std::string& persistDirTopLevel
    )
{
    try {
        MdsdUtil::ValidateDirRWXByUser(persistDirTopLevel);
    }
    catch(std::exception& ex) {
        Logger::LogError("Error: failed to access directory '" + persistDirTopLevel + "'. Reason: " + ex.what());
        return false;
    }
    m_persistDirTopLevel = persistDirTopLevel;
    return true;
}

std::string
EventHubUploaderMgr::CreateAndGetPersistDir(
    EventHubType ehtype,
    const std::string& moniker,
    const std::string& eventname
    )
{
    if (m_persistDirTopLevel.empty())
    {
        throw std::runtime_error("Root directory path string for persisting EventHub messages is empty");
    }

    std::string persistDirPath = m_persistDirTopLevel;
    persistDirPath += "/" + EventHubTypeToStr(ehtype);
    MdsdUtil::CreateDirIfNotExists(persistDirPath, 01755);
    persistDirPath += "/" + moniker;
    MdsdUtil::CreateDirIfNotExists(persistDirPath, 01755);
    persistDirPath += "/" + eventname;
    MdsdUtil::CreateDirIfNotExists(persistDirPath, 01755);

    return persistDirPath;
}

EventHubUploader*
EventHubUploaderMgr::GetUploader(
    const std::string & uploaderId
    )
{
    // support multiple reader threads
    boost::shared_lock<boost::shared_mutex> lk(m_mapMutex);
    auto findResult = m_ehUploaders.find(uploaderId);
    if (findResult == m_ehUploaders.end()) {
        return nullptr;
    }
    return findResult->second.get();
}

// This API assumes m_mapMutex shared lock is already held.
std::set<std::pair<std::string, std::string>>
EventHubUploaderMgr::GetNewItemSet(
    EventHubType ehtype,
    const std::unordered_map<std::string, std::unordered_set<std::string>> & eventMonikerMap
    )
{
    Trace trace(Trace::MdsCmd, "EventHubUploaderMgr::GetNewItemSet");

    std::set<std::pair<std::string, std::string>> newItemSet;
    for (const auto & item : eventMonikerMap) {
        auto & eventname = item.first;
        auto & monikers = item.second;
        for (const auto & moniker: monikers) {
            auto findResult = m_ehUploaders.find(EventHubUploaderId(ehtype, moniker, eventname));

            if (findResult == m_ehUploaders.end()) {
                newItemSet.insert(std::make_pair(moniker, eventname));
            }
            else {
                TRACEINFO(trace, "Found existing EventHubUploader for moniker=" << moniker << ", event=" << eventname);
            }
        }
    }
    return newItemSet;
}

// This API assumes m_mapMutex shared lock is already held.
std::set<std::pair<std::string, std::string>>
EventHubUploaderMgr::GetDroppedItemSet(
    EventHubType ehtype,
    const std::unordered_map<std::string, std::unordered_set<std::string>> & eventMonikerMap
    )
{
    Trace trace(Trace::MdsCmd, "EventHubUploaderMgr::GetDroppedItemSet");

    std::set<std::pair<std::string, std::string>> droppedItemSet;

    for (const auto & item : m_ehUploaders) {
        EventHubUploaderId ehid(item.first);
        if (ehid.m_ehtype != ehtype) {
            continue;
        }
        auto iter = eventMonikerMap.find(ehid.m_eventname);
        if (iter == eventMonikerMap.end()) {
            TRACEINFO(trace, "Event '" << ehid.m_eventname << "' is dropped in MdsdConfig.");
            droppedItemSet.insert(std::make_pair(ehid.m_moniker, ehid.m_eventname));
        }
        else {
            auto & monikers = iter->second;
            for (const auto & moniker: monikers) {
                if (moniker != ehid.m_moniker) {
                    TRACEINFO(trace, "Event " << ehid.m_eventname << "'s moniker '" << ehid.m_moniker
                        << "' is dropped in MdsdConfig.");
                    droppedItemSet.insert(std::make_pair(ehid.m_moniker, ehid.m_eventname));
                }
            }
        }
    }
    return droppedItemSet;
}

void
EventHubUploaderMgr::CreateUploaders(
    EventHubType ehtype,
    const std::unordered_map<std::string, std::unordered_set<std::string>> & eventMonikerMap
    )
{
    Trace trace(Trace::MdsCmd, "EventHubUploaderMgr::CreateUploaders");
    if (m_persistDirTopLevel.empty()) {
        Logger::LogError("Error: EventHub persist directory shouldn't be empty.");
        return;
    }
    try {
        // This function could be called in multi-threads, or signal handler. use lock to protect.
        boost::upgrade_lock<boost::shared_mutex> slock(m_mapMutex);

        auto newItemSet = GetNewItemSet(ehtype, eventMonikerMap);
        auto droppedItemSet = GetDroppedItemSet(ehtype, eventMonikerMap);

        // Do exclusive lock on the EH uploader map
        if (!newItemSet.empty() || !droppedItemSet.empty()) {
            boost::upgrade_to_unique_lock< boost::shared_mutex > uniqueLock(slock);
            for (const auto & item : newItemSet) {
                auto & moniker = item.first;
                auto & eventname = item.second;
                EventHubUploaderId uploaderId(ehtype, moniker, eventname);
                auto persistDir = CreateAndGetPersistDir(ehtype, moniker, eventname);
                EhUploader_t newUploader(new EventHubUploader(persistDir));
                m_ehUploaders[uploaderId] = std::move(newUploader);
                TRACEINFO(trace, "Created EventHubUploader for moniker=" << moniker << ", event=" << eventname);
            }

            for (const auto & item: droppedItemSet) {
                auto & moniker = item.first;
                auto & eventname = item.second;
                m_ehUploaders.erase(EventHubUploaderId(ehtype, moniker, eventname));
                TRACEINFO(trace, "Removed EventHubUploader for moniker=" << moniker << ", event=" << eventname);
            }
        }
    }
    catch(std::exception& ex) {
        Logger::LogError("Error: failed to create EventHub uploaders. Reason: " + std::string(ex.what()));
    }
}

bool
EventHubUploaderMgr::SetSasAndStart(
    const EventHubUploaderId& uploaderId,
    const std::string & ehSas
    )
{
    const std::string funcname = "EventHubUploaderMgr::SetSasAndStart";
    Trace trace(Trace::MdsCmd, funcname);

    if (ehSas.empty()) {
        throw std::invalid_argument(funcname + ": unexpected empty SasKey");
    }

    try {
        auto uploaderObj = GetUploader(uploaderId);
        if (!uploaderObj) {
            TRACEINFO(trace, "Cannot find uploader " << uploaderId << "'. Mdsd xml doesn't define it.");
            return false;
        }
        else {
            TRACEINFO(trace, "SetSasAndStart for " << uploaderId);
            uploaderObj->SetSasAndStart(ehSas);
            return true;
        }
    }
    catch(std::exception& ex) {
        Logger::LogError("Error: EventHubUploaderMgr::SetSasAndStart() failed. Reason: " + std::string(ex.what()));
        return false;
    }
}

bool
EventHubUploaderMgr::AddMessageToUpload(
    const EventHubUploaderId& uploaderId,
    EventDataT&& eventData
    )
{
    const std::string funcname = "EventHubUploaderMgr::AddMessageToUpload";
    Trace trace(Trace::Bond, funcname);

    if (eventData.empty()) {
        throw std::invalid_argument(funcname + ": unexpected empty EventHub data");
    }

    // The actual data sent to EventHub is a serialized version of EventDataT::GetData().
    // However, because EventDataT::GetData() is std::string, and serialization doesn't
    // change the size of std::string, use the std::string's size to do validation.
    if (eventData.GetData().size() > EventDataT::GetMaxSize()) {
        TRACEWARN(trace, "Data size(" << eventData.GetData().size()
            << ") exceeds max supported size(" << EventDataT::GetMaxSize() << "). Drop it.");
        return false;
    }

    auto uploaderObj = GetUploader(uploaderId);
    if (!uploaderObj) {
        std::ostringstream oss;
        oss << "Error: " << funcname << " cannot find uploader '" << uploaderId << "'.";
        Logger::LogError(oss.str());
        return false;
    }

    uploaderObj->AddData(std::move(eventData));
    TRACEINFO(trace, "Msg added to EventHubUploader, persistDir: " + uploaderObj->GetPersistDir());
    return true;
}

void
EventHubUploaderMgr::WaitForFinish(
    int32_t maxMilliSeconds
    )
{
    Trace trace(Trace::MdsCmd, "EventHubUploaderMgr::WaitForFinish");
    for (auto & iter : m_ehUploaders) {
        iter.second->WaitForFinish(maxMilliSeconds);
    }
}

// vim: se sw=8 :
