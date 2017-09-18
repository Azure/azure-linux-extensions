// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef __CONFIGUPDATECMD_HH__
#define __CONFIGUPDATECMD_HH__

#include <string>
#include <vector>
#include "Crypto.hh"

namespace mdsd
{

/// <summary>
/// This class implements functions to handle ConfigUpdate command xml files.
/// This includes download xml file, parse xml file, and get data from xml.
/// </summary>
class ConfigUpdateCmd
{
public:
    /// <summary>
    /// Create the object that'll handle a ConfigUpdate command xml file.
    /// <param name="rootContainerSas">The sas key for the root container
    /// where the command xml file locates. </param>
    /// <param name="eventNameSpace">Event namespace (e.g., TuxTest). Can't be empty.</param>
    /// <param name="tenantName">Tenant name. Optional</param>
    /// <param name="roleName">Role name. Optional</param>
    /// <param name="instanceName">Instance name. Optional</param>
    /// </summary>
    ConfigUpdateCmd(
            const std::string& rootContainerSas,
            const std::string& eventNameSpace,
            const std::string& tenantName,
            const std::string& roleName,
            const std::string& instanceName);

    ~ConfigUpdateCmd() {}

    ConfigUpdateCmd(const ConfigUpdateCmd & other) = default;
    ConfigUpdateCmd(ConfigUpdateCmd&& other) = default;
    ConfigUpdateCmd& operator=(const ConfigUpdateCmd& other) = default;
    ConfigUpdateCmd& operator=(ConfigUpdateCmd&& other) = default;

    /// <summary>
    /// Initiate an async download of a new config. Returns a task whose result
    /// is true iff a new config was successfully downloaded (and corresponding
    /// member variables are correctly updated).
    /// </summary>
    pplx::task<bool> StartAsyncDownloadOfNewConfig();

    /// <summary>
    /// Get the config XML string downloaded from XStore
    /// </summary>
    std::string GetConfigXmlString() const { return m_configXmlString; }

    /// <summary>
    /// Get the config XML string's MD5 sum
    /// </summary>
    Crypto::MD5Hash GetConfigXmlMD5Sum() const { return m_configXmlMD5Sum; }

    /// <summary>
    /// Initialize with existing MD5Hash (e.g. from the mdsd command line config).
    /// </summary>
    static void Initialize(const Crypto::MD5Hash& md5) { s_lastMd5Sum = md5; }

private:
    std::string m_rootContainerSas;
    std::string m_configXmlString;          // Member variable where downloaded mdsd config xml will be stored

    std::vector<std::string> m_cmdXmlPathsXstore;   // List of all XStore paths to search for a cmd xml blob.
                                            // e.g., "TuxTest/myTestTenant/role1/instance1/MACommandCu.xml",
                                            //       "TuxTest/myTestTenant/role1/MACommandCu.xml",
                                            //       "TuxTest/myTestTenant/MACommandCu.xml"

    // Function to asynchronously start downloading a cmd xml blob given as the param.
    // The task then continues to the ProcessCmdXmlAsync task if a cmd xml is downloaded correctly.
    // Returns the continuation task whose completion will give us the result of cmd blob downloading/processing.
    pplx::task<bool> GetCmdXmlAsync(uint64_t blobLmt, std::string cmdXmlPathXstore);

    // Async cmd XML processing task
    // The task then continues to the GetCfgXmlAsync task if a cmd xml is parsed correctly.
    pplx::task<bool> ProcessCmdXmlAsync(uint64_t blobLmt, std::string cmdXmlString);

    // Async cfg XML downloading task
    pplx::task<bool> GetCfgXmlAsync(
            std::string && configXml,
            const Crypto::MD5Hash & configXmlMD5Sum,
            const std::string & configXmlPathXstore,
            bool configXmlPersistentFlag,
            uint64_t blobLmt);

    // Extracted UpdateConfig cmd params
    std::string m_configXmlPathXstore;      // e.g., "ConfigArchive/65db3091d1b6ba83c7dba7a9a1a984ce/TuxTestVer7v0.xml"
    Crypto::MD5Hash m_configXmlMD5Sum;      // e.g., "65db3091d1b6ba83c7dba7a9a1a984ce"
    bool m_configXmlPersistentFlag;         // May not be needed at all for us, but just saving it anyway

    // Things to remember for update logic
    // Updated with timestamp of the last successful XML cfg blob to compare with the new XML cfg blob
    static uint64_t s_lastTimestamp;
    // Updated with MD5 hash of the last successful mdsd config blob's MD5 sum to compare with the new XML cfg blob    
    static Crypto::MD5Hash s_lastMd5Sum;
    // Fixed constants
    static std::string s_cmdFileName;       // Currently "MACommandCu.xml"
};

} // namespace mdsd

#endif // __CONFIGUPDATECMD_HH__
