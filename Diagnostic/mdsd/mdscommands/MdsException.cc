// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include <sstream>
#include "MdsException.hh"

using namespace mdsd;

static
std::string GetFileBasename(
    const std::string & filepath
    )
{
    auto p = filepath.find_last_of('/');
    if (p == std::string::npos) {
        return filepath;
    }
    return filepath.substr(p+1);
}

MdsException::MdsException(
    const char* filename,
    int lineno,
    const std::string & message)
    : std::exception()
{
    std::ostringstream strm;
    if (filename) {
        strm << GetFileBasename(filename) << ":" << lineno << " ";
    }
    strm << message;
    m_msg = strm.str();
}

MdsException::MdsException(
    const char* filename,
    int lineno,
    const char* message)
    : std::exception()
{
    if (message) {
        std::ostringstream strm;
        if (filename) {
            strm << GetFileBasename(filename) << ":" << lineno << " ";
        }
        strm << message;
        m_msg = strm.str();
    }
}
