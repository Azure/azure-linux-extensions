// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "ProtocolListenerJSON.hh"
#include "StreamListener.hh"
#include "Logger.hh"
#include "Trace.hh"

static
void
handler(int fd)
{
    StreamListener::handler(new StreamListener(fd));
}

void
ProtocolListenerJSON::HandleConnection(int fd)
{
    Trace trace(Trace::EventIngest, "ProtocolListenerJSON::HandleConnection");

    std::thread thread(handler, fd);
    std::ostringstream out;
    out << "ProtocolListenerJSON: Created JSON thread " << thread.get_id() << " for fd " << fd;
    Logger::LogInfo(out.str());
    thread.detach();
}
