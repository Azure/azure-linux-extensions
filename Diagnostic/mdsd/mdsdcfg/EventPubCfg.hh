// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef __EVENTPUBCFG__HH__
#define __EVENTPUBCFG__HH__

#include <memory>
#include <string>
#include <unordered_map>
#include <unordered_set>

namespace mdsd
{

class MdsdEventCfg;

/// This class handles event publishing configurations and error detection.
///
/// The design is based on the fact that
/// - Some errors could only be detected after all configuration data had been gathered.
/// - One piece of information (whether mdsd xml uses AutoKey or not), not managed by
///   this class and MdsdEventCfg, was needed to that final error detection.
///
/// Usage pattern:
/// - Add raw configuration data (like service bus accounts, annotation keys).
///   Read general event data from MdsdEventCfg.
/// - Extract event publisher SAS keys, monikers using CheckForInconsistencies().
///   Handle any inconsistencies.
///   If new service bus account, annotation key data are added after
///   CheckForInconsistencies(), CheckForInconsistencies() needs to be called again.
/// - Use SAS keys, moniker info for event publishing (GetEmbeddedSasData(),
///   GetNameMonikers(), etc.
///
/// NOTE: this class is not designed for thread-safe.
///
class EventPubCfg
{
public:
    EventPubCfg(const std::shared_ptr<MdsdEventCfg>& mdsdEventCfg);

    ~EventPubCfg() = default;

    /// <summary>
    /// Save event publisher credential info defined in <ServiceBusAccountInfos>.
    /// If the moniker already exists, throw exception.
    /// </summary>
    void AddServiceBusAccount(const std::string & moniker, std::string connStr);

    /// <summary>
    /// Save each Event Publisher's SAS key defined in <EventStreamingAnnotations>
    /// If the publisherName already exists, throw exception.
    /// </summary>
    /// <param name="publisherName"> event publisher name. It is source name for non-OMI query,
    /// or eventName for OMIQuery</param>
    /// <param name="saskey">SAS Key for event publishing</param>
    void AddAnnotationKey(const std::string & publisherName, std::string saskey);

    /// <summary>
    /// Using SBAccounts, AnnotationKeys and data from mdsdEventCfg,
    /// extract all publisher names, their monikers and sas keys.
    /// Return all the invalid publisher names if any.
    /// NOTE: this API applies to either AutoKey or embedded keys.
    /// </summary>
    /// <param name="hasAutoKey">If true, validate autokey related info; If false, validate
    /// embedded keys info. </param>
    std::unordered_set<std::string> CheckForInconsistencies(bool hasAutoKey);

    /// <summary>
    /// Return a map containing moniker, saskey info for each publisher name.
    /// The saskeys are from embedded keys only.
    /// map key: publisher name
    /// map value: a map of <moniker, saskey>
    ///
    /// Throw exception if required CheckForInconsistencies() is not called.
    /// </summary>
    std::unordered_map<std::string, std::unordered_map<std::string, std::string>> GetEmbeddedSasData() const;

    /// <summary>
    /// Get all the publisher names and their monikers.
    /// Each publisher has one or more monikers.
    /// NOTE: this function works for both embedded keys and AutoKeys.
    /// Return a map with key=publishername; value: monikers
    ///
    /// Throw exception if required CheckForInconsistencies() is not called.
    /// </summary>
    std::unordered_map<std::string, std::unordered_set<std::string>> GetNameMonikers() const;

private:
    /// <summary>
    /// Get the SAS key for given event publisher, and store the result to _ehPubMap.
    /// Throw exception if no SAS key or no moniker is found for the event publisher.
    /// </summary>
    void ValidateSasKey(const std::string & publisherName, bool hasAutoKey);

    /// <summary>
    /// Validate embedded keys.
    /// Throw exception if no key is found for given publisher name.
    /// </summary>
    void ValidateEmbeddedKey(const std::string & publisherName, const std::unordered_set<std::string>& monikers);

    /// <summary>Dump all embedded sas configuration data for tracing purpose.</summary>
    void DumpEmbeddedSasInfo();


private:
    std::shared_ptr<MdsdEventCfg> m_mdsdEventCfg;

    /// Whether data are checked or not.
    /// CheckForInconsistencies() must be called before any lookup methods are called.
    bool m_dataChecked;

    /// To store Event Publisher connection string defined in <ServiceBusAccountInfos>
    /// in mdsd xml.
    /// map key: moniker; value: event publisher connection string.
    std::unordered_map<std::string, std::string> m_sbAccountMap;

    /// To store Event Publisher SAS key defined in <EventStreamingAnnotations> in mdsd xml.
    /// NOTE: for each event publisher defined in EventStreamingAnnotations, the SAS key
    /// must be defined:
    /// - For non-Geneva, either ServiceBusAccountInfos or EventStreamingAnnotations.
    /// - For Geneva, AutoKey only.
    ///
    /// map key: publisher name; value: event publisher SAS key.
    /// publisher name: source name for non-OMIQuery, or eventName for OMIQuery.
    std::unordered_map<std::string, std::string> m_annotationKeyMap;

    /// This stores moniker, saskey for each publisher name.
    /// These information are calculated based on raw xml embedded configurations.
    /// map key=publisher name; map value=a map of <moniker, saskey>
    std::unordered_map<std::string, std::unordered_map<std::string, std::string>> m_embeddedSasMap;

    /// This stores monikers for each publisher name.
    /// Each publisher has one or more monikers.
    /// These information are calculated based on raw xml configurations.
    /// map key = publisher name; map value=monikers
    std::unordered_map<std::string, std::unordered_set<std::string>> m_nameMonikers;
};

} // namespace

#endif // __EVENTPUBCFG__HH__
