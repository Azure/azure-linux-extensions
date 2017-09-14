// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "EventPubCfg.hh"
#include "MdsdEventCfg.hh"
#include "Trace.hh"

using namespace mdsd;

EventPubCfg::EventPubCfg(
    const std::shared_ptr<MdsdEventCfg>& mdsdEventCfg
    ) :
    m_mdsdEventCfg(mdsdEventCfg),
    m_dataChecked(false)
{
    if (!mdsdEventCfg) {
        throw std::invalid_argument("EventPubCfg ctor: invalid NULL pointer for mdsdEventCfg param.");
    }
}

void
EventPubCfg::AddServiceBusAccount(
    const std::string & moniker,
    std::string connStr
    )
{
    if (moniker.empty()) {
        throw std::invalid_argument("AddServiceBusAccount(): moniker param cannot be empty.");
    }
    if (connStr.empty()) {
        throw std::invalid_argument("AddServiceBusAccount(): connStr param cannot be empty.");
    }
    // throw if key already exists
    if (m_sbAccountMap.find(moniker) != m_sbAccountMap.end()) {
        throw std::runtime_error("AddServiceBusAccount(): key " + moniker + " already exists.");
    }
    m_sbAccountMap[moniker] = std::move(connStr);
    m_dataChecked = false;
}

void
EventPubCfg::AddAnnotationKey(
    const std::string & publisherName,
    std::string saskey
    )
{
    if (publisherName.empty()) {
        throw std::invalid_argument("AddAnnotationKey(): publisherName param cannot be empty.");
    }
    if (saskey.empty()) {
        throw std::invalid_argument("AddAnnotationKey(): saskey param cannot be empty.");
    }

    // throw if key already exists
    if (m_annotationKeyMap.find(publisherName) != m_annotationKeyMap.end()) {
        throw std::runtime_error("AddAnnotationKey(): key " + publisherName + " already exists.");
    }
    m_annotationKeyMap[publisherName] = std::move(saskey);
    m_dataChecked = false;
}

std::unordered_set<std::string>
EventPubCfg::CheckForInconsistencies(
    bool hasAutoKey
    )
{
    Trace trace(Trace::ConfigLoad, "EventPubCfg::CheckForInconsistencies");
    if (m_dataChecked) {
        TRACEINFO(trace, "EventPubCfg was already checked for inconsistencies. Do nothing.");
        return std::unordered_set<std::string>();
    }

    // clear any previous data
    m_nameMonikers.clear();
    m_embeddedSasMap.clear();

    std::unordered_set<std::string> invalidItems;

    for (const auto & publisherName : m_mdsdEventCfg->GetEventPublishers()) {
        try {
            ValidateSasKey(publisherName, hasAutoKey);
        }
        catch(const std::exception & ex) {
            invalidItems.insert(publisherName);
        }
    }

    m_dataChecked = true;
    DumpEmbeddedSasInfo();
    return invalidItems;
}

void
EventPubCfg::ValidateSasKey(
    const std::string & publisherName,
    bool hasAutoKey
    )
{
    if (publisherName.empty()) {
        throw std::invalid_argument("ValidateSasKey(): publisherName param cannot be empty.");
    }

    auto monikers = m_mdsdEventCfg->GetEventPubMonikers(publisherName);
    if (monikers.empty()) {
        throw std::runtime_error("ValidateSasKey(): no moniker is found for publisher " + publisherName);
    }

    m_nameMonikers[publisherName] = monikers;

    if (!hasAutoKey) {
        ValidateEmbeddedKey(publisherName, monikers);
    }
}

void
EventPubCfg::ValidateEmbeddedKey(
    const std::string & publisherName,
    const std::unordered_set<std::string>& monikers
    )
{
    // The SAS Key should be defined in either
    // <EventStreamingAnnotations> or <ServiceBusAccountInfos>
    auto annotationItem = m_annotationKeyMap.find(publisherName);
    if (annotationItem != m_annotationKeyMap.end()) {
        // search annotation key first
        auto & saskey = annotationItem->second;
        for (const auto & moniker: monikers) {
            m_embeddedSasMap[publisherName][moniker] = saskey;
        }
    }
    else {
        // search service bus account info
        for (const auto & moniker: monikers) {
            auto sbitem = m_sbAccountMap.find(moniker);
            if (sbitem != m_sbAccountMap.end()) {
                m_embeddedSasMap[publisherName][moniker] = sbitem->second;
            }
            else {
                throw std::invalid_argument("ValidateEmbeddedKey(): failed to find EH SAS key for " + publisherName);
            }
        }
    }
}

void
EventPubCfg::DumpEmbeddedSasInfo()
{
    Trace trace(Trace::ConfigLoad, "EventPubCfg::DumpEmbeddedSasInfo");

    if (!trace.IsActive()) {
        return;
    }
    if (m_embeddedSasMap.empty()) {
        TRACEINFO(trace, "EventPublisher map is empty");
    }
    else {
        for (const auto & iter : m_embeddedSasMap) {
            auto & publisherName = iter.first;
            auto & itemsmap = iter.second;
            if (itemsmap.empty()) {
                TRACEINFO(trace, "EventPublisher='" << publisherName << "'; Moniker/SAS: N/A.");
            }
            else {
                for (const auto& item : itemsmap) {
                    auto & moniker = item.first;
                    auto & saskey = item.second;
                    TRACEINFO(trace, "EventPublisher='" << publisherName << "'; Moniker='"
                        << moniker << "'; SAS: " << saskey.substr(0, saskey.size()/2));
                }
            }
        }
    }
}

std::unordered_map<std::string, std::unordered_map<std::string, std::string>>
EventPubCfg::GetEmbeddedSasData() const
{
    if (!m_dataChecked) {
        throw std::runtime_error("Check EventPubCfg for inconsistencies before GetEmbeddedSasData().");
    }
    return m_embeddedSasMap;
}

std::unordered_map<std::string, std::unordered_set<std::string>>
EventPubCfg::GetNameMonikers() const
{
    if (!m_dataChecked) {
        throw std::runtime_error("Check EventPubCfg for inconsistencies before GetNameMonikers().");
    }
    return m_nameMonikers;
}