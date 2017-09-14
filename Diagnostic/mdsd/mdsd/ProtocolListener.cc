// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "ProtocolListener.hh"
#include "Logger.hh"
#include "Trace.hh"
#include "Utility.hh"

#include <cstring>
#include <map>
#include <boost/algorithm/string.hpp>
#include <chrono>

extern "C" {
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/stat.h>
#include <netinet/in.h>
#include <poll.h>

extern void StopProtocolListenerMgr();
}

ProtocolListener::~ProtocolListener()
{
    Trace trace(Trace::EventIngest, "ProtocolListener::handleEvent");
    Stop();
}

void
ProtocolListener::openListener()
{
    Trace trace(Trace::EventIngest, "ProtocolListener::openListener");

    int fd = MdsdUtil::CreateAndBindUnixSocket(_file_path);

    // Allow processes under non-root UID (e.g., rsyslogd on Ubuntu) to send msg to this
    mode_t mode = 0666;
    if (-1 == chmod(_file_path.c_str(), mode)) {
        close(fd);
        throw std::system_error(errno, std::system_category(),
            "chmod(" + _file_path + ", " + std::to_string(mode) + ")");
    }

    _listenfd = fd;
}

void
ProtocolListener::Start()
{
    Trace trace(Trace::EventIngest, "ProtocolListener::Start");

    std::unique_lock<std::mutex> lock(_lock);

    if (_thread.get_id() != std::thread::id())
    {
        return;
    }

    openListener();

    if (listen(_listenfd, 10))
    {
        throw std::system_error(errno, std::system_category(), "listen()");
    }

    std::thread thread([this](){this->run();});
    _thread.swap(thread);
}

void
ProtocolListener::Stop()
{
    Trace trace(Trace::EventIngest, "ProtocolListener::Stop");

    std::unique_lock<std::mutex> lock(_lock);

    if (_listenfd != -1)
    {
        close(_listenfd);
        _listenfd = -1;
        _thread.detach();
    }
}

bool
ProtocolListener::stopCheck()
{
    std::lock_guard<std::mutex> lock(_lock);
    return _listenfd == -1 || std::this_thread::get_id() != _thread.get_id();
}

void
ProtocolListener::run()
{
    Trace trace(Trace::EventIngest, "ProtocolListener::run");

    int lfd;
    {
        std::lock_guard<std::mutex> lock(_lock);
        lfd = _listenfd;
    }
    while(!stopCheck()) {
        struct pollfd fds[1];
        fds[0].fd = lfd;
        fds[0].events = POLLIN;
        fds[0].revents = 0;

        int r = poll(&fds[0], 1, 1000);
        if (r < 0)
        {
            if (errno == EINTR)
            {
                continue;
            }

            if (!stopCheck())
            {
                // Log all other errors and return.
                Logger::LogError(std::string("ProtocolListener(" + _protocol + "): poll() returned an unexpected error: ") + std::strerror(errno));

                // Initiate a clean process exit.
                StopProtocolListenerMgr();
                // After calling StopProtocolListenerMgr() the only safe thing to do is return.
            }

            return;
        }
        if (r == 1)
        {
            int newfd = accept(lfd, NULL, 0);
            if (newfd > 0)
            {
                if (!stopCheck())
                {
                    HandleConnection(newfd);
                }
                else
                {
                    close(newfd);
                }
            }
            else
            {
                // If accept was interrupted, or the connection was reset (RST)
                // before it could be accepted, then just continue.
                if (errno == EINTR || errno == ECONNABORTED)
                {
                    continue;
                }

                // If the per-process (EMFILE) or system (ENFILE) descriptor limit is reached
                // then sleep for a while in the hope that the situation will improve.
                if (errno == EMFILE || errno == ENFILE)
                {
                    Logger::LogError(std::string("ProtocolListener(") + _protocol + "): descriptor limit reached: " + std::strerror(errno));
                    Logger::LogWarn(std::string("ProtocolListener(" + _protocol + "): waiting 1 minute before trying to accept new connections"));
                    std::this_thread::sleep_for(std::chrono::seconds(60));
                    continue;
                }

                if (!stopCheck())
                {
                    // Log all other errors and return.
                    Logger::LogError(std::string("ProtocolListener(" + _protocol + "): accept() returned an unexpected error: ") + std::strerror(errno));

                    // Other errors indicate (probably) fatal conditions.
                    // Initiate a clean process exit.
                    StopProtocolListenerMgr();
                    // After calling StopProtocolListenerMgr() the only safe thing to do is return.
                }

                return;
            }
        }
    }
}
