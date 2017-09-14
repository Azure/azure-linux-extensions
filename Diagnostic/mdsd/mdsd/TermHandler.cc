// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "Logger.hh"
#include <cstdlib>

extern "C" { void EmitStackTrace(int signo); }

// Log uncaught exception before terminate the process.
void TerminateHandler()
{
    try { 
        throw;
    }
    catch(const std::exception& e) { 
        Logger::LogError("Error: mdsd is terminated with exception: " + std::string(e.what()));
    }
    catch(...) {
        Logger::LogError("Error: mdsd is terminated with unknown exception.");
    }
    EmitStackTrace(0);
    abort();
}
