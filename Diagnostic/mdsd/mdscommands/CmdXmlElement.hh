// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef __CMDXMLELEMENT__HH__
#define __CMDXMLELEMENT__HH__

#include <string>

namespace mdsd { namespace details
{

enum class ElementType
{
    Unknown,
    Verb,
    Parameter,
    Command
};

ElementType Name2ElementType(const std::string& name);

} // namespace details
} // namespace mdsd

#endif // __CMDXMLELEMENT__HH__
