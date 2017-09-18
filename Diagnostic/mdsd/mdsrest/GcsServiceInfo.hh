// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef __GCSSERVICEINFO_HH__
#define __GCSSERVICEINFO_HH__

#include <string>

namespace mdsd
{

struct GcsServiceInfo
{
    std::string EndPoint;
    std::string Environment;
    std::string GenevaAccount;
    std::string ConfigNamespace;
    std::string Region;
    std::string SpecifiedConfigVersion;
    std::string ActualConfigVersion;
    std::string ThumbPrint;
    std::string CertFile;
    std::string KeyFile;
    std::string SslDigest;
};

class GcsConfig
{
    static void ReadFromEnvVars();

    // Return true if all required environmental variable settings are set
    // (may not be valid values). Return false otherwise.
    static bool IsSet();

    static GcsServiceInfo& GetData() { return s_gcsInfo; }

private:
    static GcsServiceInfo s_gcsInfo;
};

} // namespace mdsd

#endif // __GCSSERVICEINFO_HH__
