// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef __MDSCONST_HH__
#define __MDSCONST_HH__

#include <string>

namespace mdsd {
    namespace gcs {
        const std::string c_GcsServiceName = "/api/agent/v2/";
        const std::string c_GcsMonitoringStorageKeysApiName = "MonitoringStorageKeys";
        const int c_HttpTimeInSeconds = 60;
        const std::string c_RequestIdHeader = "-request-id:";

        const std::string c_GcsEnv_EndPoint = "MONITORING_GCS_ENDPOINT";
        const std::string c_GcsEnv_Environment = "MONITORING_GCS_ENVIRONMENT";
        const std::string c_GcsEnv_Account = "MONITORING_GCS_ACCOUNT";

        const std::string c_GcsEnv_Namespace = "MONITORING_GCS_NAMESPACE";
        const std::string c_GcsEnv_Region = "MONITORING_GCS_REGION";
        const std::string c_GcsEnv_ConfigVersion = "MONITORING_CONFIG_VERSION";

        const std::string c_GcsEnv_ThumbPrint = "MONITORING_GCS_THUMBPRINT";
        const std::string c_GcsEnv_CertFile = "MONITORING_GCS_CERT_CertFile";
        const std::string c_GcsEnv_KeyFile = "MONITORING_GCS_CERT_KeyFile";
        const std::string c_GcsEnv_SslDigest = "MONITORING_GCS_CERT_SSLDIGEST";

        const std::string c_EventHub_notice = "raw";
        const std::string c_EventHub_publish = "eventpublisher";

    }
}


#endif
