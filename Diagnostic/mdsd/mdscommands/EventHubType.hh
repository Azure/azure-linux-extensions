// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef __EVENTHUBTYPE_HH_
#define __EVENTHUBTYPE_HH_

#include <string>

namespace mdsd
{

enum class EventHubType
{
    Notice,
    Publish
};

std::string EventHubTypeToStr(EventHubType type);
EventHubType EventHubTypeFromStr(const std::string & s);

} // namespace mdsd

#endif  // __EVENTHUBTYPE_HH_
