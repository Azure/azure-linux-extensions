// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include <sstream>

#include "CmdXmlCommon.hh"
#include "MdsException.hh"

namespace mdsd
{

std::string CmdXmlCommon::s_rootContainerName = "mam";

namespace details
{

void
ValidateCmdBlobParamsList(
    const std::vector<std::vector<std::string>>& paramsList,
    const std::string & verbName,
    size_t totalParams
    )
{
    if (0 == paramsList.size()) {
        std::ostringstream strm;
        strm << "No Command Parameter is found for Verb '" << verbName << "'.";
        throw MDSEXCEPTION(strm.str());
    }

    for (const auto & v : paramsList) {
        if (totalParams != v.size()) {
            std::ostringstream strm;
            strm << "Invalid number of Command (verb=" << verbName << ") parameters: expected="
            << totalParams << "; actual=" << v.size() << ".";
            throw MDSEXCEPTION(strm.str());
        }
    }
}

} // namespace details
} // namespace mdsd
