// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#ifdef DOING_MEMCHECK

#include "MdsSchemaMetadata.hh"
#include "Engine.hh"
#include "Logger.hh"
#include "Trace.hh"
#include <valgrind/memcheck.h>

// Only compiled when DOING_MEMCHECK is added as a -D on the compile line
// Otherwise, it won't even compile, much less link.

extern "C" void

RunFinalCleanup()
{
    Trace trace(Trace::SignalHandlers, "RunFinalCleanup");

    trace.NOTE("Clear Schema Metadata Cache");
    MdsSchemaMetadata::ClearCache();

    trace.NOTE("Clear Extension object cache");
    CleanupExtensions();

    Engine* engine = Engine::GetEngine();
    trace.NOTE("Clear SchemasTable cache");
    engine->ClearPushedCache();
    trace.NOTE("Cleanup MdsdConfig");
    engine->ClearConfiguration();
    engine = nullptr;


    // Must be last
    trace.NOTE("Closing all logs");
    Logger::CloseAllLogs();
    VALGRIND_DO_LEAK_CHECK;
}

#endif

// vim: se sw=8 :
