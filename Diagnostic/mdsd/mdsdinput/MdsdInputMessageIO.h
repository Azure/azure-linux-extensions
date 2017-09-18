// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once

#include "mdsd_input_reflection.h"
#include "bond/core/bond.h"
#include "bond/stream/input_buffer.h"
#include "bond/stream/output_buffer.h"
#include "bond/protocol/simple_binary.h"

namespace mdsdinput
{
    constexpr uint32_t MAX_MESSAGE_SIZE = 64 * 1024;

    class eof_exception : public std::runtime_error {
    public:
        eof_exception()
            : std::runtime_error("Connection Closed")
        {}
    };

    class msg_too_large_error : public std::runtime_error {
    public:
        explicit msg_too_large_error(const std::string& msg)
            : std::runtime_error(msg)
        {}
    };

    class FDIO
    {
    public:
        explicit FDIO(int fd)
            : _fd(fd)
        {}

        // Read overload(s) for arithmetic types
        template <typename T>
        typename boost::enable_if<boost::is_arithmetic<T> >::type
        Read(T& value)
        {
            Read(reinterpret_cast<void*>(&value), sizeof(value));
        }

        // Write overload(s) for arithmetic types
        template <typename T>
        typename boost::enable_if<boost::is_arithmetic<T> >::type
        Write(T value)
        {
            Write(reinterpret_cast<const void*>(&value), sizeof(value));
        }

        // Read into a memory blob
        void Read(bond::blob& blob, uint32_t size);

        // Write a memory blob
        void Write(const bond::blob& blob);

        // Read into a memory buffer
        void Read(void *buffer, uint32_t size);

        // Write a memory buffer
        void Write(const void *buffer, uint32_t size);
    protected:
        int _fd;
    };

    extern template void FDIO::Read(bool&);
    extern template void FDIO::Read(int32_t&);
    extern template void FDIO::Read(int64_t&);
    extern template void FDIO::Read(double&);

    extern template void FDIO::Write(bool);
    extern template void FDIO::Write(int32_t);
    extern template void FDIO::Write(int64_t);
    extern template void FDIO::Write(double);

    template<typename IO>
    class MessageIO
    {
    public:
        MessageIO(IO& io)
            : _io(io)
        {}

        void ReadMessage(Message& msg)
        {
            uint32_t size = 0;
            _io.Read(size);
            if (size > MAX_MESSAGE_SIZE)
            {
                throw msg_too_large_error("");
            }
            bond::blob data;
            _io.Read(data, size);
            bond::SimpleBinaryReader<bond::InputBuffer> input(data);
            bond::Deserialize(input, msg);
        }

        void WriteMessage(const Message& msg)
        {
            bond::OutputBuffer obuf;
            bond::SimpleBinaryWriter<bond::OutputBuffer> output(obuf);
            bond::Serialize(msg, output);
            bond::blob data = obuf.GetBuffer();
            uint32_t size = data.size();
            _io.Write(size);
            _io.Write(data);
        }

        void ReadAck(Ack& ack)
        {
            _io.Read(ack.msgId);
            uint32_t code = 0;
            _io.Read(code);
            ack.code = static_cast<mdsdinput::ResponseCode>(code);
        }

        void WriteAck(const Ack& ack)
        {
            _io.Write(ack.msgId);
            _io.Write(static_cast<uint32_t>(ack.code));
        }

    protected:
        IO _io;
    };

    extern template class MessageIO<FDIO>;
}
