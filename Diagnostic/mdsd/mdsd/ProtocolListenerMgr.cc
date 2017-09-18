// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "ProtocolListenerMgr.hh"
#include "ProtocolListenerDynamicJSON.hh"
#include "ProtocolListenerJSON.hh"
#include "ProtocolListenerTcpJSON.hh"
#include "ProtocolListenerBond.hh"
#include "Logger.hh"
#include "Trace.hh"
#include "Utility.hh"

extern "C" {
#include <unistd.h>
}

static MdsdUtil::LockedFile pidPortFile;

ProtocolListenerMgr::~ProtocolListenerMgr() {
    Trace trace(Trace::EventIngest, "ProtocolListenerMgr::Destructor");
}

void
ProtocolListenerMgr::Init(const std::string& prefix, int port, bool retry_random)
{
    Trace trace(Trace::EventIngest, "ProtocolListenerMgr::Init");

    TRACEINFO(trace, "Prefix: " + prefix + ", Port: " + std::to_string(port));

    if (nullptr == _mgr)
    {
        _mgr = new ProtocolListenerMgr(prefix, port, retry_random);
    }
}

ProtocolListenerMgr* ProtocolListenerMgr::_mgr = nullptr;

ProtocolListenerMgr*
ProtocolListenerMgr::GetProtocolListenerMgr()
{
    return _mgr;
}

bool
ProtocolListenerMgr::Start()
{
    Trace trace(Trace::EventIngest, "ProtocolListenerMgr::Start");

    std::unique_lock<std::mutex> lock(_lock);
    if (_stop)
    {
        bool failed = false;
        _stop = false;
        pidPortFile.Open(_prefix + ".pidport");
        pidPortFile.WriteLine(std::to_string(getpid()));

        _bond_listener.reset(new ProtocolListenerBond(_prefix));
        _djson_listener.reset(new ProtocolListenerDynamicJSON(_prefix));
        _json_listener.reset(new ProtocolListenerJSON(_prefix));
        _tcp_json_listener.reset(new ProtocolListenerTcpJSON(_prefix, _port, _retry_random));

        try
        {
            _bond_listener->Start();
        }
        catch (std::system_error& ex)
        {
            _bond_listener.release();
            Logger::LogError(std::string("ProtocolListenerMgr: BOND Listener failed to start: ") + ex.what());
            failed = true;
        }

        if (!failed)
        {
            try
            {
                _djson_listener->Start();
            }
            catch (std::system_error &ex)
            {
                _djson_listener.release();
                Logger::LogError(std::string("ProtocolListenerMgr: Dynamic JSON Listener failed to start: ") + ex.what());
                failed = true;
            }
        }

        if (!failed)
        {
            try
            {
                _json_listener->Start();
            }
            catch (std::system_error &ex)
            {
                _json_listener.release();
                Logger::LogError(std::string("ProtocolListenerMgr: JSON Listener failed to start: ") + ex.what());
                failed = true;
            }
        }

        if (!failed)
        {
            try
            {
                _tcp_json_listener->Start();
                pidPortFile.WriteLine(std::to_string(static_cast<ProtocolListenerTcpJSON *>(_tcp_json_listener.get())->Port()));
            }
            catch (std::system_error &ex)
            {
                _tcp_json_listener.release();
                Logger::LogError(std::string("ProtocolListenerMgr: TCP JSON Listener failed to start: ") + ex.what());
                failed = true;
            }
        }

        // One of the listeners failed to start. Stop the manager so things get cleaned up before process exit.
        if (failed)
        {
            _lock.unlock();
            Stop();
            return false;
        }
    }
    return true;
}

void
ProtocolListenerMgr::Stop()
{
    Trace trace(Trace::EventIngest, "ProtocolListenerMgr::Stop");

    std::lock_guard<std::mutex> lock(_lock);
    if (!_stop) {
        try
        {
            if (_bond_listener)
            {
                _bond_listener->Stop();
                unlink(_bond_listener->FilePath().c_str());
                _bond_listener.release();
            }
            if (_djson_listener)
            {
                _djson_listener->Stop();
                unlink(_djson_listener->FilePath().c_str());
                _djson_listener.release();
            }
            if (_json_listener)
            {
                _json_listener->Stop();
                unlink(_json_listener->FilePath().c_str());
                _json_listener.release();
            }
            if (_tcp_json_listener)
            {
                _tcp_json_listener->Stop();
                _tcp_json_listener.release();
            }
        }
        catch(std::exception& ex) {
            Logger::LogError("Error: ProtocolListenerMgr::Stop() unexpected exception while stopping listeners: " + std::string(ex.what()));
        }
        catch(...) {
            Logger::LogError("Error: ProtocolListenerMgr::Stop() unknown exception while stopping listeners.");
        }

        try {
            pidPortFile.Remove();
        }
        catch(std::exception& ex) {
            Logger::LogError("Error: ProtocolListenerMgr::Stop() unexpected exception while trying to remove pid-port file: " + std::string(ex.what()));
        }
        catch(...) {
            Logger::LogError("Error: ProtocolListenerMgr::Stop() unknown exception while trying to remove pid-port file.");
        }
        _stop = true;
        _cond.notify_all();
    }
}

void
ProtocolListenerMgr::Wait()
{
    Trace trace(Trace::EventIngest, "ProtocolListenerMgr::Wait");

    std::unique_lock<std::mutex> lock(_lock);

    // Wait for stop
   _cond.wait(lock, [this]{return this->_stop;});
}

extern "C"
void
StopProtocolListenerMgr()
{
    auto plmgmt = ProtocolListenerMgr::GetProtocolListenerMgr();
    if (plmgmt != nullptr)
    {
        plmgmt->Stop();
    }
}

extern "C" void
TruncateAndClosePidPortFile()
{
    try {
        pidPortFile.TruncateAndClose();
    }
    catch(std::exception& ex) {
        Logger::LogError("Error: TruncateAndClosePidPortFile() unexpected exception: " + std::string(ex.what()));
    }
    catch(...) {
        Logger::LogError("Error: TruncateAndClosePidPortFile() unknown exception.");
    }
}
