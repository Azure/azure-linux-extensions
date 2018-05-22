// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once

#ifndef _CFGOBODIRECTCONFIG_HH_
#define _CFGOBODIRECTCONFIG_HH_

#include <string>

// struct to hold OBO direct upload config data

namespace mdsd {

struct OboDirectConfig
{
    // Currently all fields are as is from the XML CDATA config (e.g., "ProviderName,AnsiString").
    // Parse out as desired.
    std::string onBehalfFields;
    std::string containerSuffix;
    std::string primaryPartitionField;
    std::string partitionFields;
    std::string onBehalfReplaceFields;
    std::string excludeFields;
    std::string timePeriods = "PT1H";   // timePeriods is optional and "PT1H" by default if not given.
    std::string priority;
};

}

#endif // _CFGOBODIRECTCONFIG_HH_
