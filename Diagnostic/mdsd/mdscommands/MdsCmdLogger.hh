// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef __MDSCMDLOGGER__HH__
#define __MDSCMDLOGGER__HH__

#include "Logger.hh"

namespace mdsd { namespace details
{
    inline void MdsCmdLogError(const std::string & msg)
    {
        Logger::LogError("MDSCMD " + msg);
    }

    inline void MdsCmdLogError(const std::ostringstream& strm)
    {
        MdsCmdLogError(strm.str());
    }

    inline void MdsCmdLogWarn(const std::string & msg)
    {
        Logger::LogWarn("MDSCMD " + msg);
    }

    inline void MdsCmdLogWarn(const std::ostringstream& strm)
    {
        MdsCmdLogWarn(strm.str());
    }

} // namespace details
} // namespace mdsd

#endif // __MDSCMDLOGGER__HH__
