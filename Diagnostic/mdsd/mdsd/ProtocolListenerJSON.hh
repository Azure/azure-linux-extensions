// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#ifndef _PROTOCOL_LISTENER_JSON_HH_
#define _PROTOCOL_LISTENER_JSON_HH_

#include "ProtocolListener.hh"

class ProtocolListenerJSON : public ProtocolListener
{
public:
    ProtocolListenerJSON(const std::string& prefix)
        : ProtocolListener(prefix, "json")
    {}

protected:
    virtual void HandleConnection(int fd);
};

// vim: set ai sw=8:
#endif // _PROTOCOL_LISTENER_JSON_HH_
