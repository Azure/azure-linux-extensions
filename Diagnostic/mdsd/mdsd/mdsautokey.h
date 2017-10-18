// --------------------------------------------------------------------------------------------------------------------
// <copyright file="mdsautokey.h" company="Microsoft">
//  Copyright (c) Microsoft Corporation.  All rights reserved.
// </copyright>
// --------------------------------------------------------------------------------------------------------------------

// The autokey feature is never used by the Linux Diagnostic Extension; this stub disables the feature.

#ifndef _AUTOKEY_H_
#define _AUTOKEY_H_
#include <string>
#include <map>

namespace mdsautokey {
    enum autokeyResultStatus {
        autokeySuccess,
        autokeyPartialSuccess,
        autokeyFailure
    };

    class autokeyResult
    {
    public:
        autokeyResultStatus status;
        autokeyResult(autokeyResultStatus stat) : status(stat) {}
        autokeyResult() : status(autokeyResultStatus::autokeySuccess) {}
    };

    autokeyResult GetLatestMdsKeys(const std::string& autokeyCfg, const std::string& nmspace,
        int eventVersion, std::map<std::pair<std::string, std::string>, std::string>& keys)
        {
            return autokeyResult(autokeyResultStatus::autokeyFailure);
        }
}
#endif
