// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#ifndef _PROTOCOL_LISTENER_DYNAMIC_JSON_HH_
#define _PROTOCOL_LISTENER_DYNAMIC_JSON_HH_

#include "ProtocolListener.hh"

class ProtocolListenerDynamicJSON : public ProtocolListener
{
public:
    ProtocolListenerDynamicJSON(const std::string& prefix)
        : ProtocolListener(prefix, "djson")
    {}

protected:
    virtual void HandleConnection(int fd);
};

// vim: set ai sw=8:
#endif // _PROTOCOL_LISTENER_DYNAMIC_JSON_HH_
