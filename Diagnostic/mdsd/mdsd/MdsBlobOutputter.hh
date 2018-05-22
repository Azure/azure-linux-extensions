// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#ifndef _MDSBLOBOUTPUTTER_HH
#define _MDSBLOBOUTPUTTER_HH
#include <string>
#include "Crypto.hh"
#include "Trace.hh"
#include "Logger.hh"
#include "Utility.hh"
#include <type_traits>
#include <cstring>
#include <stdexcept>

class MdsBlobOutputter
{
public:
    MdsBlobOutputter(size_t maxbytes) : _buffer(0), _end(0), _current(0)
    {
        if (maxbytes) {
            _current = _buffer = new unsigned char [maxbytes];
            _end = _buffer + maxbytes;
        }
    }

    ~MdsBlobOutputter() { if (_buffer) delete [] _buffer; }

    size_t size() const { return (_buffer) ? (_current - _buffer) : 0; }

    void clear() { if (_buffer) { delete [] _buffer; _buffer = nullptr; } }

    unsigned char * data() { return _buffer; }

    template <typename T>
    typename std::enable_if<std::is_integral<T>::value, void>::type
    Write(const T& value)
    {
        Trace trace(Trace::BondDetails, "Write<scalar>");
        TRACEINFO(trace, sizeof(T) << " bytes");
        if (_current + sizeof(T) > _end) {
            throw std::overflow_error("Bond blob buffer overflow");
        }
        * reinterpret_cast<T*>(_current) = value;
        _current += sizeof(T);
    }

    void
    Write(const std::string& value)
    {
        Trace trace(Trace::BondDetails, "Write<string>");
        size_t bytecount = value.size();
        size_t totalbytes = bytecount + sizeof(uint32_t);
        TRACEINFO(trace, value.size() << " characters, " << bytecount << " bytes (" << totalbytes << " total)");
        if ((_current + totalbytes) > _end) {
            throw std::overflow_error("Bond blob buffer overflow"); 
        }       
        * reinterpret_cast<uint32_t*>(_current) = bytecount;
        ::memcpy(_current + sizeof(uint32_t), value.data(), bytecount);
        _current += totalbytes;
    }

    void
    Write(const std::u16string& value)
    {
        Trace trace(Trace::BondDetails, "Write<u16string>");
        size_t bytecount = sizeof(std::u16string::value_type) * value.size();
        size_t totalbytes = bytecount + sizeof(uint32_t);
        TRACEINFO(trace, value.size() << " characters, " << bytecount << " bytes (" << totalbytes << " total)");
        if ((_current + totalbytes) > _end) {
            throw std::overflow_error("Bond blob buffer overflow"); 
        }       
        * reinterpret_cast<uint32_t*>(_current) = bytecount;
        ::memcpy(_current + sizeof(uint32_t), value.data(), bytecount);
        _current += totalbytes;
    }

    void
    WriteShort(const std::u16string& value)
    {
        Trace trace(Trace::BondDetails, "WriteShort<u16string>");
        size_t bytecount = sizeof(std::u16string::value_type) * value.size();
        size_t totalbytes = bytecount + sizeof(uint16_t);
        TRACEINFO(trace, value.size() << " characters, " << bytecount << " bytes (" << totalbytes << " total)");
        if ((_current + totalbytes) > _end) {
            throw std::overflow_error("Bond blob buffer overflow");
        }
        * reinterpret_cast<uint16_t*>(_current) = static_cast<uint16_t>(bytecount);
        ::memcpy(_current + sizeof(uint16_t), value.data(), bytecount);
        _current += totalbytes;
    }

    void
    Write(const Crypto::MD5Hash& value)
    {
        Trace trace(Trace::BondDetails, "Write<Crypto::MD5Hash>");
        size_t len = Crypto::MD5Hash::DIGEST_LENGTH;
        TRACEINFO(trace, len << " bytes");
        if (_current + len > _end) {
            throw std::overflow_error("Bond blob buffer overflow");
        }
        ::memcpy(_current, value.GetBuffer(), len);
        _current += len;
    }


    void
    Write(const char * array, size_t len)
    {
        Trace trace(Trace::BondDetails, "Write<char array>");
        if (len && !array) {
            throw std::invalid_argument("Attempt to write non-zero length char* array from NULL pointer");
        }
        if (!len) {
            Logger::LogWarn("Blob writer asked to write zero-length char array");
            return;
        }
        TRACEINFO(trace, len << " bytes to be written");
        if ((_current + len) > _end) {
            throw std::overflow_error("Bond blob buffer overflow");
        }
        ::memcpy(_current, array, len);
        _current += len;
    }

    void
    Write(const unsigned char * array, size_t len)
    {
        Trace trace(Trace::BondDetails, "Write<unsigned char array>");
        if (len && !array) {
            throw std::invalid_argument("Attempt to write non-zero length unsigned char* array from NULL pointer");
        }
        if (!len) {
            Logger::LogWarn("Blob writer asked to write zero-length unsigned char array");
            return;
        }
        TRACEINFO(trace, len << " bytes to be written");
        if ((_current + len) > _end)
        {
            throw std::overflow_error("Bond blob buffer overflow");
        }
        ::memcpy(_current, array, len);
        _current += len;
    }

    void
    WriteSuffix()
    {
        Write(0xdeadc0dedeadc0de);
    }

private:
    unsigned char*  _buffer;
    unsigned char*  _end;
    unsigned char*  _current;

    void
    dumpstate(std::ostream& strm)
    {
        strm << "_buffer=" << static_cast<void*>(_buffer);
        strm << " _current=" << static_cast<void*>(_current);
        strm << " _end=" << static_cast<void*>(_end);
    }
};

#endif // _MDSBLOBOUTPUTTER_HH

// vim: se expandtab sw=4 :
