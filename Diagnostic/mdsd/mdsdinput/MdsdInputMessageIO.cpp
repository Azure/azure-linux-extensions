// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "MdsdInputMessageIO.h"
#include <boost/make_shared.hpp>

extern "C" {
#include <unistd.h>
}

#include <cassert>
#include <cerrno>
#include <system_error>

namespace mdsdinput
{
    void FDIO::Write(const bond::blob& blob)
    {
        Write(blob.data(), blob.size());
    }

    void FDIO::Read(bond::blob& blob, uint32_t size)
    {
        auto data = boost::allocate_shared_noinit<char[]>(std::allocator<char>(), size);
        Read(data.get(), size);
        blob.assign(data, size);
    }

    void FDIO::Read(void *buffer, uint32_t size)
    {
        assert(buffer != nullptr);
        size_t nleft = size;
        do
        {
            errno = 0;
            ssize_t nr = read(_fd, reinterpret_cast<char*>(buffer) + (size - nleft), nleft);
            if (nr < 0)
            {
                if (EINTR != errno)
                {
                    throw std::system_error(errno, std::system_category());
                }
            }
            else
            {
                nleft -= nr;

                if (nleft > 0 && nr == 0)
                {
                    throw eof_exception();
                }
            }
        } while (nleft > 0);
    }

    void FDIO::Write(const void *buffer, uint32_t size)
    {
        assert(buffer != nullptr);
        size_t nleft = size;
        do
        {
            errno = 0;
            ssize_t nw = write(_fd, reinterpret_cast<const char*>(buffer)+(size - nleft), nleft);
            if (nw < 0)
            {
                if (EINTR != errno)
                {
                    throw std::system_error(errno, std::system_category());
                }
            }
            else if (nw == 0)
            {
                throw std::runtime_error("write() returned 0");
            }
            else
            {
                nleft -= nw;
            }
        } while (nleft > 0);
    }

    template void FDIO::Read(bool&);
    template void FDIO::Read(int32_t&);
    template void FDIO::Read(int64_t&);
    template void FDIO::Read(double&);

    template void FDIO::Write(bool);
    template void FDIO::Write(int32_t);
    template void FDIO::Write(int64_t);
    template void FDIO::Write(double);

    template class MessageIO<FDIO>;
}
