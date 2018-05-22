// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once

#ifndef __MDSEXCEPTION__HH__
#define __MDSEXCEPTION__HH__

#include <string>
#include <exception>

#define MDSEXCEPTION(message) \
    mdsd::MdsException(__FILE__, __LINE__, message)
/**/

namespace mdsd
{

class MdsException : public std::exception
{
private:
    std::string m_msg;

public:
    MdsException(const char* filename,
                 int lineno,
                 const std::string & message);

    MdsException(const char* filename,
                 int lineno,
                 const char* message);

    virtual const char * what() const noexcept
    {
        return m_msg.c_str();
    }
};

class BlobNotFoundException : public std::exception
{
private:
    std::string m_msg;

public:
    BlobNotFoundException(std::string message) noexcept :
        std::exception(),
        m_msg(std::move(message))
    {}

    virtual const char * what() const noexcept
    {
        return m_msg.c_str();
    }
};

class TooBigEventHubDataException : public MdsException
{
public:
    TooBigEventHubDataException(const std::string & msg) :
        MdsException(nullptr, 0, msg)
        {}
    TooBigEventHubDataException(const char* msg) :
        MdsException(nullptr, 0, msg)
        {}
};

}

#endif // __MDSEXCEPTION__HH__
