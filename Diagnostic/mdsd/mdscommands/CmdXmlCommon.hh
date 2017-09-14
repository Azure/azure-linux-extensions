// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef __CMDXMLCOMMON_HH__
#define __CMDXMLCOMMON_HH__

#include <string>
#include <vector>

namespace mdsd
{

class CmdXmlCommon {
public:
	static std::string GetRootContainerName() { return s_rootContainerName; }
	static void SetRootContainerName(std::string name) { s_rootContainerName = std::move(name); }

private:
	static std::string s_rootContainerName;
};


namespace details {

void ValidateCmdBlobParamsList(
    const std::vector<std::vector<std::string>>& paramsList,
    const std::string & verbName,
    size_t totalParams
    );


} // namespace details

} // namespace mdsd

#endif // __CMDXMLCOMMON_HH__
