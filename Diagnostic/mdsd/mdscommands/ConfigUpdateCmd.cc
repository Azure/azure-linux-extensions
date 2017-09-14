// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include <sstream>
#include <fstream>
#include <algorithm>

#include <cpprest/pplx/pplxtasks.h>

#include "ConfigUpdateCmd.hh"
#include "MdsBlobReader.hh"
#include "CmdListXmlParser.hh"
#include "CmdXmlCommon.hh"
#include "MdsException.hh"
#include "Trace.hh"
#include "Logger.hh"
#include "Crypto.hh"

using namespace mdsd;
using namespace mdsd::details;

uint64_t ConfigUpdateCmd::s_lastTimestamp = 0;
Crypto::MD5Hash ConfigUpdateCmd::s_lastMd5Sum;
std::string ConfigUpdateCmd::s_cmdFileName = "MACommandCu.xml";

ConfigUpdateCmd::ConfigUpdateCmd(
        const std::string& rootContainerSas,
        const std::string& eventNameSpace,
        const std::string& tenantName,
        const std::string& roleName,
        const std::string& instanceName)
    : m_rootContainerSas(rootContainerSas)
    , m_configXmlPersistentFlag(true) // Just to avoid IDE/compiler warning
{
    Trace trace(Trace::MdsCmd, "ConfigUpdateCmd::ConfigUpdateCmd");

    if (rootContainerSas.empty()) {
        throw MDSEXCEPTION("ConfigUpdate blob root container cannot be empty.");
    }
    if (eventNameSpace.empty()) {
        throw MDSEXCEPTION("ConfigUpdate MDS namespace cannot be empty.");
    }
    // Check the validity of tenantName, roleName & instanceName.
    // 1. if tenantName is empty, then both roleName & instanceName must be empty
    if (tenantName.empty() && !(roleName.empty() && instanceName.empty())) {
        throw MDSEXCEPTION("Non-empty role name or instance name when tenant name is empty.");
    }
    // 2. if roleName is empty, then instance name must be empty
    if (roleName.empty() && !instanceName.empty()) {
        throw MDSEXCEPTION("Non-empty instanceName given when roleName is empty.");
    }

    // Construct the list of all possible cmd xml paths in xstore.
    // E.g., "TuxTest/myTestTenant/role1/instance1/MACommandCu.xml",
    //       "TuxTest/myTestTenant/role1/MACommandCu.xml",
    //       "TuxTest/myTestTenant/MACommandCu.xml" and
    //       "TuxTest/MACommandCu.xml"
    std::string upToNameSpace  = eventNameSpace + "/";
    std::string upToTenantName = upToNameSpace + tenantName + "/";
    std::string upToRoleName   = upToTenantName + roleName + "/";
    m_cmdXmlPathsXstore.reserve(4); // Maximum 4 paths to try
    if (!instanceName.empty()) {
        m_cmdXmlPathsXstore.push_back(upToRoleName + instanceName + "/" + s_cmdFileName);
    }
    if (!roleName.empty()) {
        m_cmdXmlPathsXstore.push_back(upToRoleName + s_cmdFileName);
    }
    if (!tenantName.empty()) {
        m_cmdXmlPathsXstore.push_back(upToTenantName + s_cmdFileName);
    }
    // Namespace/MACommandCu.xml should be always added
    m_cmdXmlPathsXstore.push_back(upToNameSpace + s_cmdFileName);

    TRACEINFO(trace,
            "ConfigUpdateCmd::ConfigUpdateCmd(), namespace = \""
            << eventNameSpace << "\", tenantName = \"" << tenantName
            << "\", roleName = \"" << roleName << "\", instanceName = \""
            << instanceName << "\", resulting cmd xml path in xstore (longest one only) = \""
            << m_cmdXmlPathsXstore.front() << '"');
}

// Helper for parsing config update cmd xml
static bool
ParseConfigUpdateCmdXml(
        std::string&& xmlDoc,
        bool& configXmlPersistentFlag,
        Crypto::MD5Hash& configXmlMD5Sum,
        std::string& configXmlPathXstore)
{
    Trace trace(Trace::MdsCmd, "ParseConfigUpdateCmdXml");

    if (xmlDoc.empty()) {
        trace.NOTE("No ConfigUpdate cmd XML data to parse. Abort parser.");
        return false;
    }

    configXmlPersistentFlag = false;
    configXmlPathXstore.clear();

    CmdListXmlParser parser;
    parser.Parse(xmlDoc);

    auto paramTable = parser.GetCmdParams();
    if (0 == paramTable.size()) {
        throw MDSEXCEPTION("No Command Parameter is found in ConfigUpdate cmd XML.");
    }

    // UpdateConfig cmd xml example:
    //
    // <Command version='1.0'>
    //   <Verb>UpdateConfig</Verb>
    //   <Parameters>
    //     <Parameter>TRUE</Parameter>
    //     <Parameter>65db3091d1b6ba83c7dba7a9a1a984ce</Parameter>
    //     <Parameter>ConfigArchive/65db3091d1b6ba83c7dba7a9a1a984ce/TuxTestVer7v0.xml</Parameter>
    //   </Parameters>
    // </Command>
    const std::string CfgUpdateCmdVerb = "UpdateConfig";
    const auto NPARAMS = 3;
    const auto PersistentFlagIndex = 0;
    const auto ConfigXmlMD5SumIndex = 1;
    const auto ConfigXmlXstorePathIndex = 2;

    auto cfgUpdateParamsList = paramTable[CfgUpdateCmdVerb];
    ValidateCmdBlobParamsList(cfgUpdateParamsList, CfgUpdateCmdVerb, NPARAMS);

    // Now extract the parameters
    // But check if there are more than one UpdateConfig commands in the cmd xml.
    // In that case, log a warning and use the last one.
    if (cfgUpdateParamsList.size() > 1)
    {
        std::ostringstream msg;
        msg << "More than one UpdateConfig commands given in the cmd XML"
            << " (there were " << cfgUpdateParamsList.size()
            << "). Only the last one will be used.";
        Logger::LogWarn(msg);
    }
    const auto& params = cfgUpdateParamsList.back();
    configXmlPersistentFlag = params[PersistentFlagIndex] == "TRUE";
    configXmlMD5Sum = Crypto::MD5Hash::from_hash(params[ConfigXmlMD5SumIndex]);
    configXmlPathXstore = std::move(params[ConfigXmlXstorePathIndex]);

    TRACEINFO(trace,
            "MDS config update cmd xml blob parsed. persist flag = "
            << configXmlPersistentFlag << ", config xml md5sum = "
            << configXmlMD5Sum.to_string() << ", config xml xstore path = "
            << configXmlPathXstore);
    return true;
}

pplx::task<bool>
ConfigUpdateCmd::StartAsyncDownloadOfNewConfig()
{
    Trace trace(Trace::MdsCmd, "ConfigUpdateCmd::StartAsyncDownloadOfNewConfig");

    // Helper struct type to hold a cml blob path and its LMT
    struct LmtLookupDataT
    {
        const std::string*  m_cmdXmlPath;
        uint64_t            m_lmt;

        LmtLookupDataT(const std::string& cmdXmlPath, uint64_t lmt)
            : m_cmdXmlPath(&cmdXmlPath)
            , m_lmt(lmt)
        {}

        // Just for containers
        LmtLookupDataT() : m_cmdXmlPath(nullptr), m_lmt(0) {}

        bool operator<(const LmtLookupDataT& rhs) const
        {
            return m_lmt < rhs.m_lmt;
        }
    };

    std::vector<pplx::task<LmtLookupDataT>> lmtTasks; // Parallel LMT lookup tasks

    // Async/parallel LMT retrieval
    for (size_t i = 0; i < m_cmdXmlPathsXstore.size(); i++)
    {
        lmtTasks.push_back(pplx::task<LmtLookupDataT>([=]()
        {
            MdsBlobReader blobReader(m_rootContainerSas, m_cmdXmlPathsXstore[i]);

            // Get the blob's LMT along with the blob's path (asynchronously)
            auto asyncLmtLookupTask = blobReader.GetLastModifiedTimeStampAsync(
                                            MdsBlobReader::DoNothingBlobNotFoundExHandler);
                                            // We don't want to log non-existing blob here, as that could be frequent and persistent
            return asyncLmtLookupTask.then([=](uint64_t lmt)
            {
                return LmtLookupDataT(m_cmdXmlPathsXstore[i], lmt);
            });
        }));
    }

    // Specify what to do when all parallel tasks are completed
    return pplx::when_all(lmtTasks.begin(), lmtTasks.end()).then([=](std::vector<LmtLookupDataT> lmtResults) -> pplx::task<bool>
    {
        Trace trace(Trace::MdsCmd, "ConfigUpdateCmd::StartAsyncDownloadOfNewConfig when_all().then() lambda");

        // Find latest LMT path
        auto maxLmtResult = std::max_element(lmtResults.begin(), lmtResults.end());
        auto latestLmt = maxLmtResult->m_lmt;
        auto latestLmtCmdXmlPath = *maxLmtResult->m_cmdXmlPath;

        TRACEINFO(trace, "Latest LMT from all candidate cmd blob paths (# paths: " << m_cmdXmlPathsXstore.size()
                << ", longest path: " << m_cmdXmlPathsXstore.front()
                << ", latest LMT path: " << latestLmtCmdXmlPath
                << ") = " << latestLmt << " (0 means no cmd blob found), "
                << ", s_lastTimestamp = " << s_lastTimestamp);

        return GetCmdXmlAsync(latestLmt, latestLmtCmdXmlPath);
    }).then([](bool result)
    {
        return result;
    });
}

pplx::task<bool>
ConfigUpdateCmd::GetCmdXmlAsync(uint64_t blobLmt, std::string cmdXmlPathXstore)
{
    Trace trace(Trace::MdsCmd, "ConfigUpdateCmd::GetCmdXmlAsync");

    pplx::task<bool> returnFalseTask([]() { return false; });

    if (blobLmt == 0) // No cmd blob found. Nothing to do.
    {
        TRACEINFO(trace, "No cmd blob was passed (blobLmt = 0). Nothing to do.");
        return returnFalseTask;
    }

    if (blobLmt <= s_lastTimestamp) // No new cmd blob found. Nothing to do.
    {
        TRACEINFO(trace, "No new cmd blob was passed (passed blobLmt = "
                << blobLmt << ", s_lastTimestamp = " << s_lastTimestamp << '"');
        return returnFalseTask;
    }

    // Get/check the cmd blob's content
    MdsBlobReader cmdXmlBlobReader(m_rootContainerSas, cmdXmlPathXstore);
    auto asyncCmdXmlReadTask = cmdXmlBlobReader.ReadBlobToStringAsync();
    return asyncCmdXmlReadTask.then([blobLmt,this](std::string cmdXmlString) -> pplx::task<bool>
    {
        return ProcessCmdXmlAsync(blobLmt, std::move(cmdXmlString));
    });
}

pplx::task<bool>
ConfigUpdateCmd::ProcessCmdXmlAsync(uint64_t blobLmt, std::string cmdXmlString)
{
    Trace trace(Trace::MdsCmd, "ConfigUpdateCmd::ProcessCmdXmlAsync");

    TRACEINFO(trace, "Cmd XML Blob content=\"" << cmdXmlString << '"');

    pplx::task<bool> returnFalseTask([]() { return false; });

    if (cmdXmlString.empty()) // Cmd blob content is empty. Nothing to do.
    {
        return returnFalseTask;
    }

    bool configXmlPersistentFlag = false;
    Crypto::MD5Hash configXmlMD5Sum;
    std::string configXmlPathXstore;
    std::string genevaIssueMsg = "[Geneva has generated an invalid configuration update command--See the description outside the bracket. Please report this via the 'Contact Us' button on the Geneva Monitoring portal] ";
    try
    {
        if (!ParseConfigUpdateCmdXml(std::move(cmdXmlString), configXmlPersistentFlag,
                configXmlMD5Sum, configXmlPathXstore)) {
            return returnFalseTask;
        }
    }
    catch (const MdsException& e)
    {
        std::ostringstream msg;
        msg << genevaIssueMsg << "ConfigUpdate cmd XML parse failed (no UpdateConfig verb or invalid XML format): "
            << e.what();
        Logger::LogError(msg);
        return returnFalseTask;
    }

    // Validate the retrieved ConfigUpdate cmd params
    if (configXmlPathXstore.empty())
    {
        Logger::LogError(genevaIssueMsg + "ConfigUpdate cmd's config xml xstore path param cannot be empty.");
        return returnFalseTask;
    }

    TRACEINFO(trace, "Cmd XML parsed successfully. ConfigXml xstore path = "
                    << configXmlPathXstore << ", MD5 sum = " << configXmlMD5Sum.to_string()
                    << ", persistent flag = " << configXmlPersistentFlag);

    // Check if the md5 is the same as the last downloaded one, and return if so.
    if (configXmlMD5Sum == s_lastMd5Sum)
    {
        TRACEINFO(trace, "MD5 sum given in the cmd XML"
                << " is equal to the last downloaded one. Skipping this one.");
        return returnFalseTask;
    }

    // Now, download config XML from Xstore (asynchronously)

    MdsBlobReader blobReader(m_rootContainerSas, configXmlPathXstore);
    auto cfgXmlAsyncReadTask = blobReader.ReadBlobToStringAsync();
    return cfgXmlAsyncReadTask.then([=](std::string configXml) -> pplx::task<bool>
    {
        return GetCfgXmlAsync(std::move(configXml), configXmlMD5Sum,
                configXmlPathXstore, configXmlPersistentFlag, blobLmt);
    });
}

pplx::task<bool>
ConfigUpdateCmd::GetCfgXmlAsync(
        std::string && configXml,
        const Crypto::MD5Hash & configXmlMD5Sum,
        const std::string & configXmlPathXstore,
        bool configXmlPersistentFlag,
        uint64_t cmdBlobLmt)
{
    Trace trace(Trace::MdsCmd, "ConfigUpdateCmd::GetCfgXmlAsync");

    TRACEINFO(trace, "Downloaded mdsd cfg xml: \"" << configXml << '"');

    pplx::task<bool> returnFalseTask([]() { return false; });

    if (configXml.empty())
    {
        Logger::LogError("Downloaded mdsd cfg xml is empty!");
        return returnFalseTask;
    }

    // Check if md5 sum matches the passed md5sum param
    auto computedMD5Sum = Crypto::MD5HashString(configXml);
    if (configXmlMD5Sum != computedMD5Sum)
    {
        std::ostringstream msg;
        msg << "MD5 sum mismatch! Calculated = " << computedMD5Sum.to_string()
            << ", Given in cmd XML = " << configXmlMD5Sum.to_string();
        Logger::LogError(msg);
        return returnFalseTask;
    }

    // Now update the relevant member variables
    m_configXmlPathXstore = configXmlPathXstore;
    m_configXmlString = std::move(configXml);
    m_configXmlMD5Sum = std::move(computedMD5Sum);
    m_configXmlPersistentFlag = configXmlPersistentFlag;
    s_lastMd5Sum = computedMD5Sum;
    s_lastTimestamp = cmdBlobLmt;

    return pplx::task<bool>([](){ return true; });
}
