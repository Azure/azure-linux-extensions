// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "GcsServiceInfo.hh"
#include "Logger.hh"
#include "MdsConst.hh"

using namespace mdsd;

GcsServiceInfo GcsConfig::s_gcsInfo;

// Read an environment variable and store the value to 'value'.
// If given environment variable is invalid, do nothing.
static void
GetEnvVar(const std::string & name, std::string& value)
{
    if (name.empty()) {
        return;
    }

    char* v = std::getenv(name.c_str());
    if (!v) {
        Logger::LogInfo("Environment variable '" + name + "' is not defined.");
    }
    else {
        value = v;
    }
}

void
GcsConfig::ReadFromEnvVars()
{
    GetEnvVar(gcs::c_GcsEnv_EndPoint, s_gcsInfo.EndPoint);
    GetEnvVar(gcs::c_GcsEnv_Environment, s_gcsInfo.Environment);
    GetEnvVar(gcs::c_GcsEnv_Account, s_gcsInfo.GenevaAccount);
    GetEnvVar(gcs::c_GcsEnv_Region, s_gcsInfo.Region);

    GetEnvVar(gcs::c_GcsEnv_ThumbPrint, s_gcsInfo.ThumbPrint);
    GetEnvVar(gcs::c_GcsEnv_CertFile, s_gcsInfo.CertFile);
    GetEnvVar(gcs::c_GcsEnv_KeyFile, s_gcsInfo.KeyFile);
    GetEnvVar(gcs::c_GcsEnv_SslDigest, s_gcsInfo.SslDigest);
}

bool
GcsConfig::IsSet()
{
    return (
        !s_gcsInfo.EndPoint.empty() &&
        !s_gcsInfo.Environment.empty() &&
        !s_gcsInfo.GenevaAccount.empty() &&
        !s_gcsInfo.Region.empty() &&
        !s_gcsInfo.ThumbPrint.empty() &&
        !s_gcsInfo.CertFile.empty() &&
        !s_gcsInfo.KeyFile.empty() &&
        !s_gcsInfo.SslDigest.empty()
    );
}