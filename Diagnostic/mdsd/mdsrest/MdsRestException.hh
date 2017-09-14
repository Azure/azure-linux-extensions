// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once

#ifndef __MDSRESTEXCEPTION__HH__
#define __MDSRESTEXCEPTION__HH__

#include <string>
#include <exception>

namespace mdsd
{

class JsonParseException : public std::exception
{
private:
    std::string m_msg;

public:
    JsonParseException(std::string message) noexcept :
        std::exception(),
        m_msg(std::move(message))
    {}

    virtual const char * what() const noexcept
    {
        return m_msg.c_str();
    }
};

}

#endif // __MDSRESTEXCEPTION__HH__
