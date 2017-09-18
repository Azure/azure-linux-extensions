// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#ifndef _PROTOCOL_LISTENER_TCP_JSON_HH_
#define _PROTOCOL_LISTENER_TCP_JSON_HH_

#include "ProtocolListener.hh"

class ProtocolListenerTcpJSON : public ProtocolListener
{
public:
    ProtocolListenerTcpJSON(const std::string& prefix, int port, bool retry_random)
            : ProtocolListener(prefix, "json"), _port(port), _retry_random(retry_random)
    {
        _file_path = _prefix + ".pidport";
    }

    int Port() { return _port; };

protected:
    virtual void openListener();
    virtual void HandleConnection(int fd);

    int _port;
    bool _retry_random;
};

// vim: set ai sw=8:
#endif // _PROTOCOL_LISTENER_TCP_JSON_HH_
