// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef __BINARYWRITER__HH__
#define __BINARYWRITER__HH__

#include <string>
#include <cstring>
#include <vector>
#include <type_traits>
#include "MdsException.hh"

namespace mdsd { namespace details
{

typedef uint8_t byte;

// A helper class which allows write data in binary format to the bytes buffer.
class BinaryWriter
{
    template <class T, bool isFundamental>
    class BinaryWriterFunctions
    {
    public:
        static void Write(BinaryWriter& writer, T value);
        static void Write(BinaryWriter& writer, size_t position, T value);
    };

    template <class T>
    class BinaryWriterFunctions<T, true>
    {
    public:
        static void Write(BinaryWriter& writer, T value)
        {
            writer.Write(reinterpret_cast<const byte *>(&value), sizeof(T));
        }

        static void Write(BinaryWriter& writer, size_t position, T value)
        {
            writer.Write(position, reinterpret_cast<const byte *>(&value), sizeof(T));
        }
    };

    template <class T>
    class BinaryWriterFunctions<T, false>
    {
        static void Write(BinaryWriter& writer, T value);
        static void Write(BinaryWriter& writer, size_t position, T value);
    };

public:

    // Initializes a BinaryWriter object specifying the buffer to be used.
    BinaryWriter(std::vector<byte>& buffer) : m_buffer(buffer) {}

    // Gets the current size of the buffer.
    std::size_t GetBufferSize() const { return m_buffer.size(); }

    // Writes binary data to the specified position of the buffer, extending it if required.
    void Write(size_t position, const byte* source, size_t sourceSize)
    {
        if (!source) {
            throw MDSEXCEPTION("Unexpected NULL for source pointer.");
        }
        if (position + sourceSize > m_buffer.size())
        {
            m_buffer.resize(position + sourceSize);
        }

        memcpy(m_buffer.data() + position, source, sourceSize);
    }

    // Writes binary data to the end of the buffer, extending it.
    void Write(const byte* source, size_t sourceSize)
    {
        if (!source) {
            throw MDSEXCEPTION("Unexpected NULL for source pointer.");
        }
        Write(m_buffer.size(), source, sourceSize);
    }

    // Writes value of the primitive type to the end of the buffer in binary format.
    template <class T>
    void Write(T value)
    {
        BinaryWriterFunctions<T, std::is_fundamental<T>::value>::Write(*this, value);
    }

    // Writes value of the primitive type to the specified position of the buffer in binary format.
    template <class T>
    void Write(size_t position, T value)
    {
        BinaryWriterFunctions<T, std::is_fundamental<T>::value>::Write(*this, position, value);
    }

    // Writes string value to the end of the buffer.
    void Write(const std::string & value)
    {
        Write(reinterpret_cast<const byte *>(value.c_str()), value.size());
    }

    // Writes an integer value to the end of the buffer in base-128 format.
    void WriteInt32AsBase128(int value)
    {
        WriteInt64AsBase128(value);
    }

    // Writes an int64 value to the end of the buffer in base-128 format.
    void WriteInt64AsBase128(int64_t value)
    {
        bool negative = value < 0;
        long t = static_cast<long>(negative ? -value : value);
        bool first = true;
        do
        {
            byte b;
            if (first)
            {
                b = (byte)(t & 0x3f);
                t >>= 6;
                if (negative)
                {
                    b = (byte)(b | 0x40);
                }

                first = false;
            }
            else
            {
                b = (byte)(t & 0x7f);
                t >>= 7;
            }

            if (t > 0)
            {
                b |= 0x80;
            }

            Write(&b, sizeof(b));
        } while (t > 0);
    }

    // Writes an unsigned integer value to the end of the buffer in base-128 format.
    void WriteUInt32AsBase128(unsigned int value)
    {
        WriteUInt64AsBase128(value);
    }

    // Writes an unsigned long value to the end of the buffer in base-128 format.
    void WriteUInt64AsBase128(uint64_t value)
    {
        uint64_t t = value;

        do
        {
            byte b = (byte)(t & 0x7f);
            t >>= 7;
            if (t > 0)
            {
                b |= 0x80;
            }

            Write(&b, sizeof(b));
        } while (t > 0);
    }

    // Clears the buffer.
    void Reset() { m_buffer.clear(); }

private:
    
    std::vector<byte>& m_buffer;
};

} // namespace details
} // namespace mdsd

#endif // __BINARYWRITER__HH__
