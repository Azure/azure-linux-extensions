// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "Crypto.hh"
#include <cstring>
#include <map>
#include <string>
#include <stdexcept>
#include <system_error>
extern "C" {
#include <openssl/md5.h>
#include <errno.h>
#include <unistd.h>
#include <fcntl.h>
//#include <sys/types.h>
//#include <sys/stat.h>
}

namespace Crypto {

MD5Hash::MD5Hash()
{
    memset((void*)hash, 0, DIGEST_LENGTH);
}

bool
MD5Hash::operator==(const MD5Hash& that) const
{
    return (0 == memcmp((void*)(this->hash), (void*)(that.hash), DIGEST_LENGTH));
}

bool
MD5Hash::operator!=(const MD5Hash& that) const
{
    return (0 != memcmp((void*)(this->hash), (void*)(that.hash), DIGEST_LENGTH));
}

std::string
MD5Hash::to_string() const
{
    std::string result;
    result.reserve(2 * DIGEST_LENGTH);

    constexpr char digits[] = "0123456789abcdef";

    for (size_t i = 0; i < DIGEST_LENGTH; i++) {
        result.push_back(digits[(hash[i]>>4) & 0xf]);
        result.push_back(digits[ hash[i]     & 0xf]);
    }

    return result;
}

MD5Hash
MD5HashString(const std::string& input)
{
    MD5Hash hash;

    MD5((const unsigned char *)input.c_str(), input.length(), hash.GetBuffer());
    return hash;
}

MD5Hash
MD5HashFile(const std::string & filename)
{
    int fd = open(filename.c_str(), O_RDONLY);
    if (-1 == fd) {
        throw std::system_error(errno, std::system_category(), std::string("Failed to open ").append(filename).append(" for read"));
    }

    MD5_CTX context;

    MD5_Init(&context);

    while (1) {
        unsigned char buffer[65536];

        ssize_t length = read(fd, buffer, sizeof(buffer));
        if (-1 == length) {
	    close(fd);
            throw std::system_error(errno, std::system_category(), "Failed to read " + filename);
	} else if (0 == length) {
            break;
	}
        MD5_Update(&context, buffer, length);
    }

    MD5Hash result;
    MD5_Final(result.GetBuffer(), &context);
    close(fd);
    return result;
}

unsigned char
char_to_nybble(char c)
{
    static std::map<char, unsigned char> high_digits {
        { 'a', 10 }, { 'A', 10 }, { 'b', 11 }, { 'B', 11 }, { 'c', 12 }, { 'C', 12 },
        { 'd', 13 }, { 'D', 13 }, { 'e', 14 }, { 'E', 14 }, { 'f', 15 }, { 'F', 15 }
    };

    if (c >= '0' && c <= '9') {
        return (unsigned char)(c - '0');
    }

    auto iter = high_digits.find(c);
    if (iter != high_digits.end()) {
        return iter->second;
    }

    std::string msg { "Illegal character (" };
    msg.append(1, c).append("} in MD5 hashstring");
    throw std::domain_error(msg);
}

MD5Hash
MD5Hash::from_hash(const std::string & hash_string)
{
    MD5Hash result;
    unsigned char nybbles[DIGEST_LENGTH*2];
    size_t current = 0;

    for (char c : hash_string) {
        if (c != ' ') {
            nybbles[current++] = char_to_nybble(c);
            if (current == sizeof(nybbles)) {
                break;
            }
        }
    }
    if (current != sizeof(nybbles)) {
        throw std::length_error("MD5 hash string too short");
    }

    for (current = 0; current < DIGEST_LENGTH; current++) {
        int offset = current << 1;
        result.hash[current] = (nybbles[offset]<<4) + nybbles[offset+1];
    }

    return result;
}

};

// vim: se sw=4 expandtab :
