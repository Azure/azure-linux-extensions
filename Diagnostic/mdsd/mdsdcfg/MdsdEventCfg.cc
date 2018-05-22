// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include <stdexcept>

#include "MdsdEventCfg.hh"
#include "Trace.hh"

using namespace mdsd;

void
MdsdEventCfg::AddEventSinkCfgInfoItem(
    const EventSinkCfgInfo & item
    )
{
    if (!item.IsValid()) {
        throw std::invalid_argument("MdsdEventCfg::AddEventSinkCfgInfoItem(): item param must be valid.");
    }
    m_eventSinkCfgInfoList.push_back(item);
    m_dataUpdated = true;
}

void
MdsdEventCfg::SetEventAnnotationTypes(
    std::unordered_map<std::string, EventAnnotationType::Type>&& eventtypes
    )
{
    m_eventAnnotationTypes = std::move(eventtypes);

    for (const auto & item : m_eventAnnotationTypes) {
        if (item.second & EventAnnotationType::EventPublisher) {
            m_eventPublishers.insert(item.first);
        }
    }
    m_dataUpdated = true;
}

void
MdsdEventCfg::UpdateMoniker(
    const std::string & eventName,
    const std::string & oldMoniker,
    const std::string & newMoniker
    )
{
    Trace trace(Trace::ConfigUse, "MdsdEventCfg::UpdateMoniker");

    if (eventName.empty()) {
        throw std::invalid_argument("MdsdEventCfg::UpdateMoniker(): eventName param cannot be empty.");
    }

    if (oldMoniker.empty()) {
        throw std::invalid_argument("MdsdEventCfg::UpdateMoniker(): oldMoniker param cannot be empty.");
    }

    if (newMoniker.empty()) {
        throw std::invalid_argument("MdsdEventCfg::UpdateMoniker(): newMoniker param cannot be empty.");
    }

    for (auto & item : m_eventSinkCfgInfoList) {
        if (eventName == item.m_eventName && oldMoniker == item.m_moniker) {
            item.m_moniker = newMoniker;
            m_dataUpdated = true;
        }
    }
}

std::unordered_set<std::string>
MdsdEventCfg::GetInvalidAnnotations()
{
    ExtractEventCfg();

    std::unordered_set<std::string> result;

    for (const auto & item : m_eventAnnotationTypes) {
        auto & name =  item.first;
        auto & anntype = item.second;
        if (EventAnnotationType::EventPublisher == anntype) {
            if (!m_ehpubMonikers.count(name)) {
                result.insert(name);
            }
        }
        else {
            if (!m_eventNames.count(name)) {
                result.insert(name);
            }
        }
    }
    return result;
}

void
MdsdEventCfg::ExtractEventCfg()
{
    if (!m_dataUpdated) {
        return;
    }

    Trace trace(Trace::ConfigUse, "MdsdEventCfg::ExtractEventCfg");

    // Clean any previous data if any
    m_eventNames.clear();
    m_ehpubMonikers.clear();
    m_ehMonikers.clear();

    auto publishers = GetEventPublishers();

    for (const auto & item : m_eventSinkCfgInfoList) {
        auto & eventname = item.m_eventName;
        auto & moniker = item.m_moniker;
        auto & storetype = item.m_storeType;

        m_eventNames.insert(eventname);

        auto localSinkName = item.GetLocalSinkName();
        m_ehpubMonikers[localSinkName].insert(moniker);

        if (storetype == StoreType::Bond) {
            m_ehMonikers.insert(moniker);
        }
        else if (storetype == StoreType::Local) {
            if (publishers.count(localSinkName)) {
               m_ehMonikers.insert(moniker);
            }
        }
    }
    m_dataUpdated = false;
}

std::unordered_map<std::string, std::unordered_set<std::string>>
MdsdEventCfg::GetCentralBondEvents() const
{
    std::unordered_map<std::string, std::unordered_set<std::string>> cbEvents;

    for (const auto & item : m_eventSinkCfgInfoList) {
        if (StoreType::Bond == item.m_storeType) {
            cbEvents[item.m_eventName].insert(item.m_moniker);
        }
    }
    return cbEvents;
}

std::unordered_set<std::string>
MdsdEventCfg::GetEventPubMonikers(
    const std::string & publisherName
    )
{
    if (publisherName.empty()) {
        throw std::invalid_argument("GetEventPubMonikers(): publisherName param cannot be empty.");
    }

    ExtractEventCfg();

    auto item = m_ehpubMonikers.find(publisherName);
    if (item != m_ehpubMonikers.end()) {
        return item->second;
    }

    return std::unordered_set<std::string>();
}
