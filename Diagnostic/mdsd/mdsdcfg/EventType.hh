// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef __EVENTTYPE__HH__
#define __EVENTTYPE__HH__

namespace mdsd
{

// This defines event type specified in mdsd configuration file.
enum class EventType {
    None,
    OMIQuery,       // event defined by <OMIQuery> 
    RouteEvent,     // event defined by <RouteEvent>
    DerivedEvent,   // event defined by <DerivedEvent>
    EtwEvent        // event defined by <EtwProvider>
};

} // namespace

#endif // __EVENTTYPE__HH__
