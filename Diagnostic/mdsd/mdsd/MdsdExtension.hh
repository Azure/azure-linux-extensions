// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _MDSDEXTENSION_HH_
#define _MDSDEXTENSION_HH_

#include <string>

class MdsdExtension
{
public:
    /// <summary> Contruct new MdsdExtension object given extension name.
    /// <param name="name">Extension name</param>
    /// </summary>
    MdsdExtension(const std::string & name) :
    _name(name), 
    _cpuPercentUsage(0),
    _isCpuThrottling(false),
    _memoryLimitInMB(0),
    _isMemoryThrottling(false),
    _ioReadLimitInKBPerSecond(0),
    _ioReadThrottling(false),
    _ioWriteLimitInKBPerSecond(0),
    _ioWriteThrottling(false)
    { }

    ~MdsdExtension() { }

    const std::string & Name() const { return _name; }

    const std::string & GetCmdLine() const { return _cmdline; }
    void SetCmdLine(const std::string & cmdline) { _cmdline = cmdline; }

    const std::string & GetBody() const { return _body; }
    void SetBody(const std::string & body) { _body = body; }

    const std::string & GetAlterLocation() const { return _alterLocation; }
    void SetAlterLocation(const std::string & alterLocation) { _alterLocation = alterLocation; }

    float GetCpuPercentUsage() const { return _cpuPercentUsage; }
    void SetCpuPercentUsage(float cpuPercentUsage) { _cpuPercentUsage = cpuPercentUsage; }

    bool GetIsCpuThrottling() const { return _isCpuThrottling; }
    void SetIsCpuThrottling(bool isCpuThrottling) { _isCpuThrottling = isCpuThrottling; }

    unsigned long long GetMemoryLimitInMB() const { return _memoryLimitInMB; }
    void SetMemoryLimitInMB(unsigned long long memoryLimitInMB) { _memoryLimitInMB = memoryLimitInMB; }

    bool GetIsMemoryThrottling() const { return _isMemoryThrottling; }
    void SetIsMemoryThrottling(bool isMemoryThrottling) { _isMemoryThrottling = isMemoryThrottling; }

    unsigned long long GetIOReadLimitInKBPerSecond() const { return _ioReadLimitInKBPerSecond; }
    void SetIOReadLimitInKBPerSecond(unsigned long long n) { _ioReadLimitInKBPerSecond = n; }

    bool GetIsIOReadThrottling() const { return _ioReadThrottling; }
    void SetIsIOReadThrottling(bool isThrottling) { _ioReadThrottling = isThrottling; }

    unsigned long long GetIOWriteLimitInKBPerSecond() const { return _ioWriteLimitInKBPerSecond; }
    void SetIOWriteLimitInKBPerSecond(unsigned long long n) { _ioWriteLimitInKBPerSecond = n; }

    bool GetIsIOWriteThrottling() const { return _ioWriteThrottling; }
    void SetIsIOWriteThrottling(bool isThrottling) { _ioWriteThrottling = isThrottling; }

private:
    MdsdExtension() = delete;

    const std::string _name;
    // Define command line to be std::string because we need to execute it.
    std::string _cmdline;
    std::string _body;
    // Define alternative location path to be std::string because we need to use the path for execute.
    std::string _alterLocation;

    float _cpuPercentUsage;
    bool _isCpuThrottling;

    unsigned long long _memoryLimitInMB;
    bool _isMemoryThrottling;

    unsigned long long _ioReadLimitInKBPerSecond;
    bool _ioReadThrottling;

    unsigned long long _ioWriteLimitInKBPerSecond;
    bool _ioWriteThrottling;
};


#endif // _MDSDEXTENSION_HH_
