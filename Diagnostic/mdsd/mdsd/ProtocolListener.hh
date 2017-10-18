// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#ifndef _PROTOCOL_LISTENER_HH_
#define _PROTOCOL_LISTENER_HH_

#include <thread>
#include <mutex>
#include <string>

class ProtocolListener
{
public:
    virtual ~ProtocolListener();

    std::string Protocol() { return _protocol; }

    void Start();
    void Stop();

    std::string FilePath() { return _file_path; };

protected:
    ProtocolListener(const std::string& prefix, const std::string& protocol)
            : _prefix(prefix), _protocol(protocol), _listenfd(-1)
    {
        _file_path = _prefix + "_" + _protocol + ".socket";
    }

    virtual void openListener();
    virtual void HandleConnection(int fd) = 0;

    std::string _prefix;
    std::string _protocol;

    std::string _file_path;

    std::mutex _lock;
    int _listenfd;
    std::thread _thread;

    bool stopCheck();
    void run();
};

// vim: set ai sw=8:
#endif // _PROTOCOL_LISTENER_HH_
