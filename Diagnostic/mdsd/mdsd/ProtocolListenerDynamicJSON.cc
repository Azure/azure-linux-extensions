// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "ProtocolListenerDynamicJSON.hh"
#include "ProtocolHandlerJSON.hh"
#include "Logger.hh"
#include "Trace.hh"

static
void
handler(int fd)
{
    ProtocolHandlerJSON h(fd);

    h.Run();
}

void
ProtocolListenerDynamicJSON::HandleConnection(int fd)
{
    Trace trace(Trace::EventIngest, "ProtocolListenerDynamicJSON::HandleConnection");

    std::thread thread(handler, fd);
    std::ostringstream out;
    out << "ProtocolListenerDynamicJSON: Created Dynamic JSON thread " << thread.get_id() << " for fd " << fd;
    Logger::LogInfo(out.str());
    thread.detach();
}
