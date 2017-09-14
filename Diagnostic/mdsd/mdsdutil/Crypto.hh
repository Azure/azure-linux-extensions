// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _CRYPTO_HH_
#define _CRYPTO_HH_

#include <string>

namespace Crypto
{

class MD5Hash
{
public:
        MD5Hash();
        MD5Hash(const MD5Hash& orig) = default;
        MD5Hash& operator=(const MD5Hash& that) = default;
	MD5Hash(MD5Hash&&) = default;
        MD5Hash& operator=(MD5Hash&&) = default;

        bool operator==(const MD5Hash& that) const;
        bool operator!=(const MD5Hash& that) const;
        unsigned char * GetBuffer() { return hash; }
        const unsigned char * GetBuffer() const { return hash; }
        std::string to_string() const;

	static MD5Hash from_hash(const std::string &);

	static constexpr size_t DIGEST_LENGTH = 16;
private:

        unsigned char hash[DIGEST_LENGTH];
};

MD5Hash
MD5HashString(const std::string&);

MD5Hash
MD5HashFile(const std::string&);

};

#endif // _CRYPTO_HH_

// vim: se sw=8 :
