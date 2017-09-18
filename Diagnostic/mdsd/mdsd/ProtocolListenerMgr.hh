// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#ifndef _PROTOCOL_LISTENER_MGMT_HH_
#define _PROTOCOL_LISTENER_MGMT_HH_

#include "ProtocolListener.hh"

#include <string>
#include <mutex>
#include <condition_variable>
#include <unordered_set>

class ProtocolListenerMgr
{
public:
    ~ProtocolListenerMgr();

    static void Init(const std::string& prefix, int port, bool retry_random);
    static ProtocolListenerMgr* GetProtocolListenerMgr();

    bool Start();
    void Stop();
    void Wait();

private:
    ProtocolListenerMgr(const std::string& prefix, int port, bool retry_random)
        : _prefix(prefix), _port(port), _retry_random(retry_random), _stop(true)
    {}

    static ProtocolListenerMgr* _mgr;

    std::string _prefix;
    int _port;
    bool _retry_random;
    std::mutex _lock;
    std::condition_variable _cond;
    bool _stop;
    std::unique_ptr<ProtocolListener> _bond_listener;
    std::unique_ptr<ProtocolListener> _djson_listener;
    std::unique_ptr<ProtocolListener> _json_listener;
    std::unique_ptr<ProtocolListener> _tcp_json_listener;
};

// vim: set ai sw=8:
#endif // _PROTOCOL_LISTENER_MGMT_HH_
