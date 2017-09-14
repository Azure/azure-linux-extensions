// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "CmdLineConverter.hh"
#include "Utility.hh"
#include "Trace.hh"
#include <vector>
#include <exception>
#include <cstring>

std::vector<std::string> CmdLineConverter::Tokenize(const std::string& cmdline, std::function<void(const std::string&)> ctxLogOnWarning)
{
    Trace trace(Trace::Extensions, "CmdLineConverter::Tokenize");

    auto current = cmdline.begin();
    size_t pos = 1;
    std::vector<std::string> argv;
    std::string element;

    enum TokenizerState { outside, within, escape, singlequote, doublequote, doubleescape };
    TokenizerState state = outside;
    while (current != cmdline.end()) {

        // Generally, state transitions consume the character that causes the transition. (See bottom of loop.)
        // Any exceptions to this rule are clearly noted (by using "continue").
        switch (state) {
        case outside:
            // Advance past whitespace, else transition to state=within
            switch (*current) {
            case ' ':
            case '\n':
                break;
            default:
                state = within;         // NOTE: This state transition does NOT consume the character
                continue;
            }
            break;

        case within:
            switch (*current) {
            case '\\':                  // escape character - change to matching state
                state = escape;
                break;
            case '\'':                  // start single quote - change to matching state
                state  = singlequote;
                break;
            case '"':                   // start double quote - change to matching state
                state = doublequote;
                break;
            case ' ':                   // whitespace terminates the element, which we can push
            case '\n':                  // into the vector; change to "outside" state
                argv.emplace_back(std::move(element));
                element.clear();
                state = outside;
                break;
            default:
                element.push_back(*current);
                break;
            }
            break;

        case escape:
            // Only blank, newline, backslash, singlequote, and doublequote can be escaped; if the
            // character isn't one of those, put the backslash into the element along with the
            // shouldn't-have-been-escaped character.
            if (std::string(" \n\\'\"").find_first_of(*current) == std::string::npos) {
                element.push_back('\\');
            }
            element.push_back(*current);
            state = within;
            break;

        case singlequote:
            if (*current != '\'') {
                element.push_back(*current);
            } else {
                state = within;
            }
            break;

        case doublequote:
            switch (*current) {
            case '"':
                state = within;
                break;
            case '\\':
                state = doubleescape;
                break;
            default:
                element.push_back(*current);
                break;
            }
            break;

        case doubleescape:
            // If it's not a backslash or a doublequote, it can't be escaped, so flow the escape char through
            if (std::string("\\\"").find_first_of(*current) == std::string::npos) {
                element.push_back('\\');
            }
            element.push_back(*current);
            state = doublequote;
            break;
        }

        current++;
        pos++;
    }

    std::string warnMsg;
    switch (state) {
    case outside:
        break;
    case within:
        if (element.size()) {
            argv.emplace_back(std::move(element));
        }
        break;
    case singlequote:
    case doublequote:
        // Issue config-file parsing warning about an unterminated quote at the end of a cmdline
        warnMsg = "Unterminated quote at the end of the command line";
        trace.NOTEWARN(warnMsg);
        ctxLogOnWarning(warnMsg);
        // Auto-close it and add it, even it if's an empty string
        argv.emplace_back(std::move(element));
        break;
    case escape:
    case doubleescape:
        // Issue config-file warning about incomplete escape at the end of the cmdline
        warnMsg = "Incomplete escape at the end of the command line";
        trace.NOTEWARN(warnMsg);
        ctxLogOnWarning(warnMsg);
        // Add what we have
        argv.emplace_back(std::move(element));
        break;
    }

    return argv;
}

CmdLineConverter::CmdLineConverter(const std::string & cmdline)
{
    Trace trace(Trace::Extensions, "CmdLineConverter::CmdLineConverter");

    try {
        std::vector<std::string> strarray = Tokenize(cmdline);

        execvp_nargs = strarray.size();

        execvp_args  = new char*[execvp_nargs+1];
        size_t i = 0;
        for (const auto& x : strarray)
        {
            size_t len = x.length();
            execvp_args[i] = static_cast<char*>(malloc(len+1));
            strncpy(execvp_args[i], x.c_str(), len);
            execvp_args[i][len] = '\0';
            i++;
        }
        execvp_args[execvp_nargs] = NULL;
    }
	catch (const std::exception& e) {
		trace.NOTEERR("Failed to parse cmdline: '" + cmdline + "'. Error=" + e.what());
	}
}

CmdLineConverter::~CmdLineConverter()
{
    if (execvp_args)
    {
        for (size_t i = 0; i < execvp_nargs; i++)
        {
            free(execvp_args[i]);
            execvp_args[i] = NULL;
        }
        delete [] execvp_args;
        execvp_args = NULL;
    }
}
