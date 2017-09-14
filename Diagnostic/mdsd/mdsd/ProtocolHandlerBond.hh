// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#ifndef _PROTOCOL_HANDLER_BOND_HH_
#define _PROTOCOL_HANDLER_BOND_HH_

#include "ProtocolHandlerBase.hh"
#include "MdsdInputMessageIO.h"
#include "MdsdInputMessageDecoder.h"

/*
 * This class is not, nor is it intended to be, thread safe.
 *
 * ProtocolListenerBond allocates a separate instance of this class per connection
 * and each connection is handled by a separate thread.
 */
class ProtocolHandlerBond: public ProtocolHandlerBase
{
public:
    explicit ProtocolHandlerBond(int fd)
        : _fd(fd), _fdio(fd), _io(_fdio)
    {}

    ~ProtocolHandlerBond();

    void Run();

private:
    mdsdinput::ResponseCode handleEvent(const mdsdinput::Message& msg);

    int _fd;
    mdsdinput::FDIO _fdio;
    mdsdinput::MessageIO<mdsdinput::FDIO> _io;
    mdsdinput::MessageDecoder _decoder;
};

// vim: set ai sw=8:
#endif // _PROTOCOL_HANDLER_BOND_HH_
