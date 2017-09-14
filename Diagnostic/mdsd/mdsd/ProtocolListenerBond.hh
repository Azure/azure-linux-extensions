// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#ifndef _PROTOCOL_LISTENER_BOND_HH_
#define _PROTOCOL_LISTENER_BOND_HH_

#include "ProtocolListener.hh"

class ProtocolListenerBond : public ProtocolListener
{
public:
    ProtocolListenerBond(const std::string& prefix)
        : ProtocolListener(prefix, "bond")
    {}

protected:
    virtual void HandleConnection(int fd);
};

// vim: set ai sw=8:
#endif // _PROTOCOL_LISTENER_BOND_HH_
