// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _CFGEVENTANNOTATIONTYPE_HH_
#define _CFGEVENTANNOTATIONTYPE_HH_

namespace EventAnnotationType
{
    // Because one event can be multiple types,
    // each type should be a power of 2.
    enum Type
    {
        None = 0,
        EventPublisher = 1 << 0,
        OnBehalf = 1 << 1
    };
};

#endif // _CFGEVENTANNOTATIONTYPE_HH_
