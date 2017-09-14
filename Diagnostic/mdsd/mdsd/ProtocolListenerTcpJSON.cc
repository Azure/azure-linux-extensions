// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "ProtocolListenerTcpJSON.hh"
#include "StreamListener.hh"
#include "Logger.hh"
#include "Trace.hh"
#include "Utility.hh"

static
void
handler(int fd)
{
    StreamListener::handler(new StreamListener(fd));
}

void
ProtocolListenerTcpJSON::openListener()
{
    Trace trace(Trace::EventIngest, "ProtocolListenerTcpJSON::openListener");

    int fd = socket(AF_INET, SOCK_STREAM, 0);
    if (-1 == fd)
    {
        throw std::system_error(errno, std::system_category(), "socket(AF_INET, SOCK_STREAM)");
    }
    MdsdUtil::FdCloser fdCloser(fd);

    int reuseaddr = 1;
    if (setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &reuseaddr, sizeof(reuseaddr)))
    {
        throw std::system_error(errno, std::system_category(), "setsockopt(SO_REUSEADDR)");
    }

    struct {
        int l_onoff;
        int l_linger;
    } linger { 0, 0 };
    if (setsockopt(fd, SOL_SOCKET, SO_LINGER, &linger, sizeof(linger)))
    {
        throw std::system_error(errno, std::system_category(), "setsockopt(SO_LINGER)");
    }

    if (_port == 0)
    {
        Logger::LogInfo(std::string("ProtocolListenerTcpJSON: Binding to a random port"));
    }

    struct sockaddr_in loopback;
    loopback.sin_family = AF_INET;
    loopback.sin_port = htons(_port);
    loopback.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    if (bind(fd, (struct sockaddr *)&loopback, sizeof(loopback)))
    {
        // If the first bind attempt was to a random port, then it doesn't matter what the errno is.
        // Just throw the exception. Trying, again, on a random port is also likely to fail.
        if (errno != EADDRINUSE || !_retry_random || _port == 0)
        {
            throw std::system_error(errno, std::system_category(),
                                    std::string("bind(AF_INET, ") + std::to_string(_port) + ")");
        }

        Logger::LogWarn("ProtocolListenerTcpJSON: Port " + std::to_string(_port) +
                        " is already in use. Will try a random port.");

        loopback.sin_port = 0;
        if (bind(fd, (struct sockaddr *) &loopback, sizeof(loopback)))
        {
            throw std::system_error(errno, std::system_category(),
                                    std::string("bind(AF_INET, 0)"));
        }
    }

    socklen_t len = sizeof(loopback);
    if (getsockname(fd, (struct sockaddr*)&loopback, &len))
    {
        throw std::system_error(errno, std::system_category(), "getsockname()");
    }
    auto _requested_port = _port;
    _port = (int)ntohs(loopback.sin_port);

    if (_requested_port != _port)
    {
        Logger::LogWarn(std::string("ProtocolListenerTcpJSON: Listener port is ") + std::to_string(_port));
    }

    fdCloser.Release();

    _listenfd = fd;
}

void
ProtocolListenerTcpJSON::HandleConnection(int fd)
{
    Trace trace(Trace::EventIngest, "ProtocolListenerTcpJSON::HandleConnection");

    std::thread thread(handler, fd);
    std::ostringstream out;
    out << "ProtocolListenerTcpJSON: Created TCP JSON thread " << thread.get_id() << " for fd " << fd;
    thread.detach();
    Logger::LogInfo(out.str());
}
