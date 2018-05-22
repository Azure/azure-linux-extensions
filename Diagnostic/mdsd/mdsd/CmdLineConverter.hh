// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _CMDLINECONVERTER_HH_
#define _CMDLINECONVERTER_HH_

#include <string>
#include <vector>
#include <functional>
#include "CfgContext.hh"

class CmdLineConverter
{
public:
    CmdLineConverter(const std::string & cmdline);
    
    virtual ~CmdLineConverter();

    static std::vector<std::string> Tokenize(const std::string& cmdline,
                                             std::function<void(const std::string&)> ctxLogOnWarning = [](const std::string&){} // Don't do any warning logging by default
                                            );

    /// <summary>
    /// Returns the char* array that can be used for execvp() directly.
    /// The caller shouldn't free the memory from this function.
    /// NOTE: the last item of the array is always NULL.
    /// </summary>
    char** argv() const { return execvp_args; }

    /// <summary>
    /// Returns the number of items in execvp args. This doesn't include
    /// the last NULL element.
    /// </summary>
    size_t argc() const { return execvp_nargs; }

private:
    size_t execvp_nargs = 0;
    char** execvp_args = NULL;
};


#endif // _CMDLINECONVERTER_HH_
