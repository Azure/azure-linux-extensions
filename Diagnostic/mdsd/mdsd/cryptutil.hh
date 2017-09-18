// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#ifndef _CRYPTUTIL_H_
#define _CRYPTUTIL_H_
#include <vector>
#include <string>
#include <utility>


typedef unsigned char BYTE;
namespace cryptutil
{
    bool DecodeString(const std::string& encodedString, std::vector<BYTE>& results);
    std::string DecodeAndDecryptString(const std::string& privKeyPath, const std::string& encodedString,
                                       const std::string& keyPassword = "");

    // Custom exception class
    class cryptutilException : public std::exception
    {
        std::string exMessage;
    public:
        cryptutilException(const std::string& errDetail)
            : exMessage(errDetail)
        {}
        virtual const char* what() const throw()
        {
            return exMessage.c_str();
        }
    };
}
#endif
