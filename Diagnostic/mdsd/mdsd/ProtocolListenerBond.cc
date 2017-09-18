// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "ProtocolListenerBond.hh"
#include "ProtocolHandlerBond.hh"
#include "Logger.hh"
#include "Trace.hh"

#include <sstream>

static
void
handler(int fd)
{
    ProtocolHandlerBond h(fd);

    h.Run();
}

void
ProtocolListenerBond::HandleConnection(int fd)
{
    Trace trace(Trace::EventIngest, "ProtocolListenerBond::HandleConnection");

    std::thread thread(handler, fd);
    std::ostringstream out;
    out << "ProtocolListenerBond: Created BOND thread " << thread.get_id() << " for fd " << fd;
    thread.detach();
    Logger::LogInfo(out.str());
}
