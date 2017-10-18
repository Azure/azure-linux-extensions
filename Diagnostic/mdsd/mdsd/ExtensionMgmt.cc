// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "ExtensionMgmt.hh"
#include "Logger.hh"
#include "Utility.hh"
#include "Trace.hh"
#include "MdsdExtension.hh"
#include "MdsdConfig.hh"
#include "CmdLineConverter.hh"
#include <cassert>
#include <cpprest/pplx/threadpool.h>
#include <boost/bind.hpp>

extern "C" {
#include <signal.h>
#include <sys/types.h>
#include <sys/wait.h>
}

std::map<const std::string, ExtensionInfo*> ExtensionList::_extlistByName;
std::map<pid_t, ExtensionInfo*> ExtensionList::_extlistByPid;
std::unordered_set<pid_t> ExtensionList::_killList;

std::mutex ExtensionList::_listmutex;
std::mutex ExtensionList::_klmutex;

bool ExtensionMetaData::operator==(const ExtensionMetaData & other) const
{
    if (Name == other.Name &&
        CommandLine == other.CommandLine &&
        Body == other.Body &&
        AlterLocation == other.AlterLocation)
    {
        return true;
    }
    return false;
}

ExtensionInfo::ExtensionInfo() : StopTimer(nullptr),
    StopTimerCancelled(false)
{

}

ExtensionInfo::~ExtensionInfo()
{
    if (StopTimer) {
        StopTimerCancelled = true;
        delete StopTimer;
        StopTimer = nullptr;
    }
}

std::string
ExtensionInfo::GetStatus() const
{
    return ExtensionInfo::StatusToString(Status);
}

std::map<ExtensionInfo::ExtStatus, std::string> ExtensionInfo::_statusMap = {
    { ExtStatus::NORMAL, "NORMAL" },
    { ExtStatus::BAD, "BAD" },
    { ExtStatus::KILLING, "KILLING" },
    { ExtStatus::EXIT, "EXIT" }
};

std::string
ExtensionInfo::StatusToString(ExtStatus s)
{
    const auto &iter = _statusMap.find(s);
    if (_statusMap.end() == iter) {
        return "UNKNOWN";
    }
    return iter->second;
}

size_t ExtensionList::GetSize()
{
    std::unique_lock<std::mutex> lock(_listmutex);
    return _extlistByName.size();
}

bool 
ExtensionList::AddItem(ExtensionInfo * extObj)
{
    Trace trace(Trace::Extensions, "ExtensionList::AddItem");
    if (!extObj)
    {
        Logger::LogError("Error: unexpected NULL value for ExtensionInfo object.");
        return false;
    }

    const std::string & extname = extObj->MetaData.Name;
    if (MdsdUtil::IsEmptyOrWhiteSpace(extname))
    {
        Logger::LogError("Error: unexpected empty or whitespace value for ExtensionName");
        return false;
    }

    std::unique_lock<std::mutex> lock(_listmutex);
    
    // search for the item. If found, delete the old one.
    const auto & iter = _extlistByName.find(extname);
    if (iter != _extlistByName.end())
    {
        ExtensionInfo *oldExtObj = iter->second;
        delete oldExtObj;
        oldExtObj = nullptr;
    }
    _extlistByName[extname] = extObj;
    assert(0 != extObj->Pid);
    _extlistByPid[extObj->Pid] = extObj;
    trace.NOTE("Successfully added ExtensionInfo object with Name='" + extname + "'");
    return true;    
}


void
ExtensionList::AddPid(pid_t pid)
{
    Trace trace(Trace::Extensions, "ExtensionList::AddPid");
    std::unique_lock<std::mutex> lock(_klmutex);
    if (0 < _killList.count(pid)) {
        Logger::LogError("Error: duplicate pid found: " + std::to_string(pid));
    }
    else {
        _killList.insert(pid);
    }
}

std::unordered_set<pid_t>
ExtensionList::GetAndClearPids()
{
    Trace trace(Trace::Extensions, "ExtensionList::GetAndClearPids");
    std::unique_lock<std::mutex> lock(_klmutex);
    std::unordered_set<pid_t> r = _killList;
    _killList.clear();
    return r;
}

ExtensionInfo * 
ExtensionList::GetItem(const std::string & extname)
{
    Trace trace(Trace::Extensions, "ExtensionList::GetItem(extname)");
    if (MdsdUtil::IsEmptyOrWhiteSpace(extname))
    {
        Logger::LogError("Error: unexpected empty or whitespace value for ExtensionName");
        return nullptr;
    }

    ExtensionInfo * obj = nullptr;
    std::unique_lock<std::mutex> lock(_listmutex);
    const auto & iter = _extlistByName.find(extname);

    if (iter != _extlistByName.end()) {
        obj = iter->second;
        trace.NOTE("Got ExtensionInfo object: '" + extname + "'");
    }
    else {
        trace.NOTE("ExtensionInfo is not found: '" + extname + "'.");
    }

    return obj;
}
 

ExtensionInfo * 
ExtensionList::GetItem(pid_t extPid)
{
    Trace trace(Trace::Extensions, "ExtensionList::GetItem(pid_t)");
    if (0 >= extPid)
    {
        Logger::LogError("Error: unexpected value for pid: " + std::to_string(extPid));
        return nullptr;
    }
    ExtensionInfo * obj = nullptr;
    std::unique_lock<std::mutex> lock(_listmutex);
    const auto & iter = _extlistByPid.find(extPid);

    if (iter != _extlistByPid.end()) {
        obj = iter->second;
        trace.NOTE("Got ExtensionInfo with pid=" + std::to_string(extPid));
    }
    else {
        trace.NOTE("ExtensionInfo is not found with pid=" + std::to_string(extPid));
    }
    return obj;
}

bool
ExtensionList::UpdateItem(pid_t oldpid, pid_t newpid)
{
    Trace trace(Trace::Extensions, "ExtensionList::UpdateItem");
    assert(0 < oldpid);
    assert(0 < newpid);

    bool resultOK = true;
    std::unique_lock<std::mutex> lock(_listmutex);
    const auto & iter = _extlistByPid.find(oldpid);
    if (iter != _extlistByPid.end()) {
        ExtensionInfo *obj = iter->second;
        _extlistByPid.erase(iter);
        _extlistByPid[newpid] = obj;
        trace.NOTE("Extension is updated: from pid " + std::to_string(oldpid) + " to pid " + std::to_string(newpid));
    }
    else {
        resultOK = false;
        Logger::LogError("Extension is not found with pid=" + std::to_string(oldpid));
    }
    return resultOK;
}

bool 
ExtensionList::DeleteItem(const std::string & extname)
{
    Trace trace(Trace::Extensions, "ExtensionList::DeleteItem");
    if (MdsdUtil::IsEmptyOrWhiteSpace(extname))
    {
        Logger::LogError("Error: unexpected empty or whitespace for ExtensionName");
        return false;
    }

    bool resultOK = true;

    std::unique_lock<std::mutex> lock(_listmutex);
    const auto & iter = _extlistByName.find(extname);
    if (iter != _extlistByName.end())
    {
        ExtensionInfo * obj = iter->second;

        _extlistByName.erase(iter);
        _extlistByPid.erase(obj->Pid);

        lock.unlock();
        trace.NOTE("Deleted item: '" + extname + "'");

        delete obj;
        obj = nullptr;
        resultOK = true;
    }
    else
    {
        trace.NOTE("Extension is not found: '" + extname + "'");
        resultOK = false;
    }

    return resultOK;
}

bool
ExtensionList::DeleteItems(const std::set<std::string>& extnames)
{
    Trace trace(Trace::Extensions, "ExtensionList::DeleteItems");
    if (0 == extnames.size())
    {
        return true;
    }

    bool resultOK = true;
    std::unique_lock<std::mutex> lock(_listmutex);

    for(const auto & extname : extnames) 
    {
        const auto & iter = _extlistByName.find(extname);
        if (iter != _extlistByName.end())
        {
            ExtensionInfo * obj = iter->second;
            _extlistByName.erase(iter);
            _extlistByPid.erase(obj->Pid);
            trace.NOTE("Deleted item: '" + extname + std::string("'"));
            delete obj;
            obj = nullptr;
        }
        else
        {
            trace.NOTE("Extension is not found: '" + extname + std::string("'"));
            resultOK = false;
        }
    }

    return resultOK;
}

void
ExtensionList::DeleteAllItems()
{
    Trace trace(Trace::Extensions, "ExtensionList::DeleteAllItems");
    std::unique_lock<std::mutex> lock(_listmutex);
    for (auto x : _extlistByPid) {
        delete x.second;
    }
    _extlistByPid.clear();
    _extlistByName.clear();
}

void
ExtensionList::ForeachExtension(const std::function<void(ExtensionInfo*)>& fn)
{
    Trace trace(Trace::Extensions, "ExtensionList::ForeachExtension");
    std::unique_lock<std::mutex> lock(_listmutex);
    for (const auto & kv : _extlistByName) {
        trace.NOTE(std::string("Walking ExtensionInfo with name='") + kv.first + "'");
        fn(kv.second);
    }
}

ExtensionMgmt * ExtensionMgmt::_extInstance = nullptr;

ExtensionMgmt*
ExtensionMgmt::GetInstance()
{
    if (!_extInstance) {
        _extInstance = new ExtensionMgmt();
        if(!_extInstance->InitSem())
        {
            delete _extInstance;
            _extInstance = nullptr;
        }
    }
    return _extInstance;
}

ExtensionMgmt::ExtensionMgmt() : _extsemInitOK(false)
{
}

ExtensionMgmt::~ExtensionMgmt()
{
    Trace trace(Trace::Extensions, "ExtensionMgmt::~ExtensionMgmt");
    if (_extsemInitOK)
    {
        if (-1 == sem_destroy(&_extsem))
        {
            std::string errstr = MdsdUtil::GetErrnoStr(errno);
            Logger::LogError("Error: sem_destroy() failed: " + errstr);
        }
    }
}

bool
ExtensionMgmt::InitSem()
{
    Trace trace(Trace::Extensions, "ExtensionMgmt::InitSem");
    if (-1 == sem_init(&_extsem, 0, 0)) {
        std::string errstr = MdsdUtil::GetErrnoStr(errno);
        Logger::LogError("Error: sem_init() failed: " + errstr);
        _extsemInitOK = false;
        return false;
    }
    _extsemInitOK = true;
    return true;
}

bool
ExtensionMgmt::StartExtensions(MdsdConfig * config)
{
    Trace trace(Trace::Extensions, "ExtensionMgmt::StartExtensions");
    if (!config) {
        trace.NOTE("MdsdConfig* is NULL. Do nothing.");
        return true;
    }
    bool resultOK = false;
    try {
        ExtensionMgmt* extmgmt = GetInstance();
        if (extmgmt) {
            std::set<std::string> extlistInConfig;
            resultOK = extmgmt->StartExtensionsFromConfig(config, extlistInConfig);
            resultOK = resultOK && extmgmt->StopObsoleteExtensions(extlistInConfig);
        }
    }
    catch(const std::exception & ex) {
        Logger::LogError(std::string("Error: StartExtensions failed: ") + ex.what());
        resultOK = false;
    }
    return resultOK;
}

void
ExtensionMgmt::StartExtensionsAsync(MdsdConfig * config)
{
    if (!config) {
        return;
    }

    // If there is no old and new extension, do nothing
    if (0 == config->GetNumExtensions() &&
        0 == ExtensionList::GetSize()) {
        return;
    }

    static std::future<bool> lastTask;
    static std::mutex mtx;

    try {
        // multiple threads may call this function when automatic configuration mgr
        // and main thread starts up
        std::lock_guard<std::mutex> lock(mtx);
        if (lastTask.valid()) {
            if (!lastTask.get()) {
                Logger::LogError("Previous StartExtensions() failed.");
            }
        }
        lastTask = std::async(std::launch::async, StartExtensions, config);
    }
    catch(const std::system_error& ex) {
        Logger::LogError(std::string("Error: std::async failed calling 'StartExtensions': ") + ex.what());
    }
}

bool
ExtensionMgmt::StartExtensionsFromConfig(
    MdsdConfig * config, 
    std::set<std::string>& extlistInConfig)
{
    Trace trace(Trace::Extensions, "ExtensionMgmt::StartExtensionsFromConfig");
    bool resultOK = true;

    std::vector<ExtensionInfo*> changedList;
    // key is old extension's pid.
    std::map<pid_t, ExtensionMetaData> newDataList;

    std::function<void(MdsdExtension*)> Visitor = 
        [this,&trace,&extlistInConfig,&resultOK,&changedList,&newDataList](MdsdExtension * extObj)
    {
        const std::string & extname = extObj->Name();
        const std::string & cmdline = extObj->GetCmdLine();
        const std::string & body = extObj->GetBody();
        const std::string & alterLocation = extObj->GetAlterLocation();

        assert(false == MdsdUtil::IsEmptyOrWhiteSpace(extname));
        assert(false == MdsdUtil::IsEmptyOrWhiteSpace(cmdline));

        extlistInConfig.insert(extname);

        // check with ExtensionList
        ExtensionInfo* oldExtInfo = ExtensionList::GetItem(extname);
        if (!oldExtInfo) {
            resultOK = resultOK && StartExtension(extname, cmdline, body, alterLocation);
        }
        else
        {
            ExtensionMetaData newMetaData(extname, cmdline, body, alterLocation);
            bool sameMetaData = (oldExtInfo->MetaData == newMetaData);
            if (!sameMetaData) {
                trace.NOTE("Found new metadata for " + extname);
                changedList.push_back(oldExtInfo);
                newDataList[oldExtInfo->Pid] = newMetaData;
            }
            else {
                trace.NOTE("No metadata were changed for " + extname);
            }
        }
    };

    config->ForeachExtension(Visitor);

    if (0 < changedList.size()) {
        resultOK = resultOK && RestartChangedExtensions(changedList, newDataList);
    }
    trace.NOTE("Finished with success = " + MdsdUtil::ToString(resultOK));
    return resultOK;
}

// terminate current Extension processes. each process will send SIGCHLD, which
// will be handled in signal handler. The extension will be deleted in the signal handler.
bool
ExtensionMgmt::RestartChangedExtensions(
    const std::vector<ExtensionInfo*> & changedList,
    const std::map<pid_t, ExtensionMetaData> & newDataList)
{
    Trace trace(Trace::Extensions, "ExtensionMgmt::RestartChangedExtensions");
    bool resultOK = true;
    if (0 == changedList.size()) {
        return resultOK;
    }
    assert(changedList.size() == newDataList.size());
    
    for (const auto & ext : changedList) {
        StopExtension(ext);
    }

    trace.NOTE("Wait for all changed extensions to be stopped ...");
    for (size_t i = 0; i < newDataList.size(); i++) {
        bool extStopOK = WaitForAnyExtStop();
        if (extStopOK) {
            std::unordered_set<pid_t> changedPids = ExtensionList::GetAndClearPids();
            for (const auto & pid : changedPids) {
                trace.NOTE("GetAndClearPids(): pid=" + std::to_string(pid));
            }
            resultOK = StartAllChangedExts(changedPids, newDataList);
        }
    }

    trace.NOTE("Finished with success = " + MdsdUtil::ToString(resultOK));
    return resultOK;
}

bool
ExtensionMgmt::WaitForAnyExtStop()
{
    Trace trace(Trace::Extensions, "ExtensionMgmt::WaitForAnyExtStop");
    bool resultOK = true;
    struct timespec ts;
    if (-1 == clock_gettime(CLOCK_REALTIME, &ts)) {
        resultOK = false;
    }
    else {
        ts.tv_sec += EXT_TERMINATE_GRACE_SECONDS + 1;

        int waitstatus = 0;
        time_t semStartTime = time(0);
        while((waitstatus = sem_timedwait(&_extsem, &ts)) == -1 && EINTR == errno) {
            semStartTime = time(0);
            continue;
        }
        int waiterrno = errno;
        if (-1 == waitstatus) {
            if (ETIMEDOUT == waiterrno)
            {
                long waitTime = (long)(time(0) - semStartTime);
                Logger::LogError("Error: sem_timedwait() timed out after " + std::to_string(waitTime) + " seconds.");
            }
            else {
                std::string errstr = MdsdUtil::GetErrnoStr(waiterrno);
                Logger::LogError("Error: sem_timedwait() failed. Error string: " + errstr);
            }
            resultOK = false;
        }
        else {
            trace.NOTE("sem_timedwait() succeeded.");
        }
    }
    trace.NOTE("Finished with success = " + MdsdUtil::ToString(resultOK));
    return resultOK;
}


bool
ExtensionMgmt::StartAllChangedExts(
    const std::unordered_set<pid_t> changedPids,
    const std::map<pid_t, ExtensionMetaData> & newDataList) const
{
    Trace trace(Trace::Extensions, "ExtensionMgmt::StartAllChangedExts");
    bool resultOK = true;

    for (const auto & pid : changedPids) {
        const auto & iter = newDataList.find(pid);

        if (newDataList.end() == iter) {
            Logger::LogError("Error: old extension pid is not found: " + std::to_string(pid));
            resultOK = false;
        }
        else {
            ExtensionMetaData metadata = iter->second;
            assert(metadata.Name.empty() == false);
            resultOK = resultOK && StartOneChangedExt(pid, metadata);
        }
    }
    trace.NOTE("Finished with success = " + MdsdUtil::ToString(resultOK));
    return resultOK;
}



bool
ExtensionMgmt::StartOneChangedExt(pid_t changedPid, const ExtensionMetaData & metadata) const
{
    Trace trace(Trace::Extensions, "ExtensionMgmt::StartOneChangedExt");
    bool resultOK = true;

    // only start new one when old one was terminated.
    if (-1 == waitpid(changedPid, NULL,  WNOHANG) && ECHILD == errno) {
        trace.NOTE(metadata.Name + " with pid " + std::to_string(changedPid) + " was terminated. Start new one.");
        resultOK = resultOK && StartExtension(metadata);
    }
    else {
        Logger::LogError("Error: " + metadata.Name + " with pid " + std::to_string(changedPid) + " was not terminated properly.");
        resultOK = false;
    }

    trace.NOTE("Finished with success = " + MdsdUtil::ToString(resultOK));
    return resultOK;
}


bool
ExtensionMgmt::StopObsoleteExtensions(const std::set<std::string> & extlistInConfig) const
{
    Trace trace(Trace::Extensions, "ExtensionMgmt::StopObsoleteExtensions");
    if (0 == ExtensionList::GetSize()) {
        return true;
    }

    std::set<std::string> obsoleteExtNames;
    std::unordered_set<ExtensionInfo*> obsoleteExtObjs;

    std::function<void(ExtensionInfo*)> Visitor = 
    [&extlistInConfig,&obsoleteExtNames,&obsoleteExtObjs](ExtensionInfo * extObj)
    {
        assert(nullptr != extObj);
        if (extlistInConfig.find(extObj->MetaData.Name) == extlistInConfig.end()) {
            obsoleteExtNames.insert(extObj->MetaData.Name);
            obsoleteExtObjs.insert(extObj);
        }
    };

    ExtensionList::ForeachExtension(Visitor);

    // The extensions must be stopped first before being deleted
    bool resultOK = true;
    for (const auto & extObj : obsoleteExtObjs)
    {
        resultOK = resultOK && StopExtension(extObj);
    }

    resultOK = resultOK && ExtensionList::DeleteItems(obsoleteExtNames);

    trace.NOTE("Finished with success = " + MdsdUtil::ToString(resultOK));
    return resultOK;
}

bool
ExtensionMgmt::StopAllExtensions()
{
    Trace trace(Trace::Extensions, "ExtensionMgmt::StopAllExtensions");
    size_t nitems = ExtensionList::GetSize();
    if (0 == nitems) {
        return true;
    }

    bool resultOK = true;
    unsigned int nexists = 0;
    std::function<void(ExtensionInfo*)> StopExtFunc = [this,&nexists,&resultOK](ExtensionInfo * extObj)
    {
        assert(nullptr != extObj);
        if (-1 != waitpid(extObj->Pid, NULL,  WNOHANG)) {
            nexists++;
        }
        resultOK = resultOK && StopExtension(extObj);
    };

    ExtensionList::ForeachExtension(StopExtFunc);

    trace.NOTE("Found " + std::to_string(nexists) + " running extensions. Wait for them to finish.");
    for (size_t i = 0; i < nexists; i++) {
        resultOK = resultOK & WaitForAnyExtStop();
    }
    ExtensionList::DeleteAllItems();

    trace.NOTE("Finished with success = " + MdsdUtil::ToString(resultOK));
    return resultOK;    
}



bool
ExtensionMgmt::MaskSignal(bool isBlock, int signum) const
{
    Trace trace(Trace::Extensions, "ExtensionMgmt::MaskSignal");
    sigset_t ss;
    std::string errmsg = "";
    int errnum = 0;

    if (-1 == sigemptyset(&ss)) {
        errnum = errno;
        errmsg = "Error: sigemptyset() failed.";
    }
    else
    {
        if (-1 == sigaddset(&ss, signum)) {
            errnum = errno;
            errmsg = "Error: sigaddset() failed on signal: " + std::to_string(signum);
        }
        else {
            int how = isBlock? SIG_BLOCK : SIG_UNBLOCK;
            if (-1 == sigprocmask(how, &ss, NULL))
            {
                errnum = errno;
                errmsg = "Error: sigprocmask() failed.";
            }
        }
    }

    bool resultOK = true;
    if (errmsg != "")
    {
        errmsg += " Error string: " + MdsdUtil::GetErrnoStr(errnum);
        Logger::LogError(errmsg);
        resultOK = false;
    }
    return resultOK;
}

bool
ExtensionMgmt::StartExtension(const ExtensionMetaData & metaData) const
{
    return StartExtension(metaData.Name, metaData.CommandLine, metaData.Body, metaData.AlterLocation);
}

bool
ExtensionMgmt::StartExtension(
    const std::string & extName,
    const std::string & cmdline,
    const std::string & body,
    const std::string & alterLocation
) const
{
    Trace trace(Trace::Extensions, "ExtensionMgmt::StartExtension");
    bool resultOK = true;

    ExtensionInfo * oldExtInfo = ExtensionList::GetItem(extName);
    if (oldExtInfo)
    {
        sleep(EXT_RETRY_WAIT_SECONDS);
    }

    if (!MaskSignal(true, SIGCHLD))
    {
        return false;
    }

    CmdLineConverter cconverter(cmdline);
    char** cargv = cconverter.argv();

    // use pipe to send child error to parent
    int pipefds[2];
    if (-1 == pipe(pipefds)) {
        Logger::LogError("Error: pipe() failed: Error string: " + MdsdUtil::GetErrnoStr(errno));
        return false;
    }

    // Use FD_CLOEXEC so that if exec() succeeds, fd will be closed automatically.
    if (fcntl(pipefds[1], F_SETFD, fcntl(pipefds[1], F_GETFD) | FD_CLOEXEC)) {
        Logger::LogError("Error: fcntl() failed: Error string: " + MdsdUtil::GetErrnoStr(errno));
        return false;
    }

    pid_t pid = fork();
    int forkerr = errno;
    if (-1 == pid) {
        Logger::LogError("Error: fork() failed: Error string: '" + MdsdUtil::GetErrnoStr(forkerr) + "'.");
        return false;
    }

    if (0 == pid) {
        // child process
        close(pipefds[0]);
        int childerr = 0;
        if (!MdsdUtil::IsEmptyOrWhiteSpace(body)) {
            if (-1 == setenv(BODYENV, body.c_str(), 1)) {
                childerr = errno;
            }
        }
        if (0 == childerr) {
            childerr = UnblockSignals();
            if (0 == childerr) {
                std::string fullpath = alterLocation + "/" + cargv[0];
                execvp(fullpath.c_str(), cargv);
                // child has error if it reaches here
                childerr = errno;
            }
        }
        // send error code to parent
        if (write(pipefds[1], &childerr, sizeof(int)) < 0) {
            Logger::LogError("Error: write() failed: Error string: '" + MdsdUtil::GetErrnoStr(errno) + "'.");
        }
        _exit(0);
    }
    // parent process
    close(pipefds[1]);

    // read child error if any.
    int readcount = 0;
    int childerr = 0;
    while (-1 == (readcount = read(pipefds[0], &childerr, sizeof(int)))) {
        if (EAGAIN != errno && EINTR != errno) {
            break;
        }
    }
    bool childFailed = false;
    if (readcount && childerr > 0) {
        Logger::LogError("Error: create " + extName + " process failed. pid=" + std::to_string(pid) + ". Error: " + MdsdUtil::GetErrnoStr(childerr));
        childFailed = true;
    }
    else {
        trace.NOTE("Created process " + extName + ": cmdline=" + cmdline + "; pid=" + std::to_string(pid));
    }
    
    resultOK = resultOK && UpdateExtensionList(oldExtInfo, extName, cmdline, body, alterLocation, pid, childFailed);
    resultOK = resultOK && MaskSignal(false, SIGCHLD);
    return resultOK;
}

bool
ExtensionMgmt::UpdateExtensionList(
    ExtensionInfo * oldExtInfo,
    const std::string & extName,
    const std::string & cmdline,
    const std::string & body,
    const std::string & alterLocation,
    pid_t pid,
    bool extFailed) const
{
    Trace trace(Trace::Extensions, "ExtensionMgmt::UpdateExtensionList");
    bool resultOK = true;

    if (!oldExtInfo) {
        trace.NOTE("Get a new extension definition. Add it to cache.");

        ExtensionInfo * extInfo = new ExtensionInfo();
        extInfo->MetaData.Name = extName;
        extInfo->MetaData.CommandLine = cmdline;
        extInfo->MetaData.Body = body;
        extInfo->MetaData.AlterLocation = alterLocation;
        extInfo->Pid = pid;
        extInfo->StartTime = time(NULL);
        extInfo->Status = ExtensionInfo::NORMAL;
        extInfo->RetryCount = extFailed? (EXT_MAX_RETRIES+1) : 0;

        resultOK = ExtensionList::AddItem(extInfo);
        if (!resultOK) {
            delete extInfo;
            extInfo = nullptr;
        }
    }
    else {
        pid_t oldpid = oldExtInfo->Pid;
        trace.NOTE("Get existing extension. Update its pid from " + std::to_string(oldpid) + " to " + std::to_string(pid));
        oldExtInfo->Pid = pid;
        oldExtInfo->StartTime = time(NULL);
        oldExtInfo->Status = ExtensionInfo::NORMAL;
        resultOK = ExtensionList::UpdateItem(oldpid, pid);
    }
    return resultOK;
}


int
ExtensionMgmt::UnblockSignals() const
{
    Trace trace(Trace::Extensions, "ExtensionMgmt::UnblockSignals");
    int sigerr = 0;
    sigset_t ss;
    if (-1 == sigfillset(&ss)) {
        sigerr = errno;
        Logger::LogError("Error: sigfillset() failed. Error string: " + MdsdUtil::GetErrnoStr(sigerr));
    }
    else {
        if (-1 == sigprocmask(SIG_UNBLOCK, &ss, NULL)) {
            sigerr = errno;
            Logger::LogError("Error: sigprocmask() failed. Error string: " + MdsdUtil::GetErrnoStr(sigerr));
        }
    }
    return sigerr;
}


bool
ExtensionMgmt::StopExtension(ExtensionInfo * extObj) const
{
    Trace trace(Trace::Extensions, "ExtensionMgmt::StopExtension");

    if (!extObj)
    {
        trace.NOTE("ExtensionInfo object is NULL. Do nothing.");
        return true;
    }

    pid_t extpid = extObj->Pid;
    std::string extname = extObj->MetaData.Name;
    trace.NOTE("Stopping " + extname + " pid=" + std::to_string(extpid) + " status=" + extObj->GetStatus());

    bool stopOK = false;
    bool isPsExist = false;

    ExtensionInfo::ExtStatus oldStatus = extObj->Status;
    assert(ExtensionInfo::ExtStatus::EXIT != oldStatus);

    extObj->Status = ExtensionInfo::ExtStatus::KILLING;
    trace.NOTE("Set " + extname + "'s status to be KILLING. Pid=" + std::to_string(extpid));

    if (ExtensionInfo::ExtStatus::NORMAL == oldStatus ||
        ExtensionInfo::ExtStatus::BAD == oldStatus)
    {
        stopOK = SendSignalToProcess(extpid, SIGINT, &isPsExist);
    }

    if (isPsExist)
    {
        trace.NOTE("Set timer to KillProcessByForce ...");
        extObj->StopTimer = new boost::asio::deadline_timer(crossplat::threadpool::shared_instance().service());
        extObj->StopTimer->expires_from_now(boost::posix_time::seconds(EXT_TERMINATE_GRACE_SECONDS));
        extObj->StopTimer->async_wait(boost::bind(&ExtensionMgmt::KillProcessByForce, 
            this, extpid, boost::asio::placeholders::error));
    }

    trace.NOTE("Finished with success = " + MdsdUtil::ToString(stopOK));

    return stopOK;
}

void
ExtensionMgmt::CatchSigChld(int signo)
{
    Trace trace(Trace::Extensions, "ExtensionMgmt::CatchSigChld");
    trace.NOTE(std::string("Caught signal=")  + std::to_string(signo) + " : " + std::string(strsignal(signo)));

    assert(SIGCHLD == signo);

    pid_t chldpid = 0;
    int waitpiderr = 0;
    bool haschild = false;

    while(true) {
        chldpid = waitpid((pid_t)-1, NULL, WNOHANG);
        waitpiderr = errno;
        trace.NOTE("waitpid() returned id=" + std::to_string(chldpid) + "\n");
        if (0 < chldpid) {
            UpdateStoppedExtension(chldpid);
            haschild = true;
        }
        else {
            break;
        }
    }

    if (-1 == chldpid && ECHILD == waitpiderr && !haschild) {
         if (-1 == sem_post(&_extsem)) {
             std::string errstr = MdsdUtil::GetErrnoStr(errno);
             trace.NOTE("Error: CatchSigchld: sem_post() failed: " + errstr);
         }
    }
}

bool
ExtensionMgmt::UpdateStoppedExtension(pid_t extpid)
{
    Trace trace(Trace::Extensions, "ExtensionMgmt::UpdateStoppedExtension");

    ExtensionInfo * extObj = ExtensionList::GetItem(extpid);
    if (!extObj) {
        Logger::LogError("no ExtensionInfo object found in cache for pid=" + std::to_string(extpid));
        return false;
    }

    ExtensionInfo::ExtStatus status = extObj->Status;
    std::string extname = extObj->MetaData.Name;
    trace.NOTE("Extension pid=" + std::to_string(extpid) + "; Status=" + ExtensionInfo::StatusToString(status));

    bool resultOK = true;
    assert(ExtensionInfo::ExtStatus::NORMAL == status || ExtensionInfo::ExtStatus::KILLING == status);

    if (ExtensionInfo::ExtStatus::NORMAL == status) {
        resultOK = HandleExtensionFailure(extObj);
    }
    else if (ExtensionInfo::ExtStatus::KILLING == status) {
        trace.NOTE("Change extension status to EXIT. Delete it from cache. Call sem_post().");
        extObj->Status = ExtensionInfo::ExtStatus::EXIT;
        resultOK = resultOK && ExtensionList::DeleteItem(extname);
        ExtensionList::AddPid(extpid);
        if (-1 == sem_post(&_extsem)) {
            std::string errstr = MdsdUtil::GetErrnoStr(errno);
            trace.NOTE("Error: UpdateStoppedExtension: sem_post() failed: " + errstr);
            resultOK = false;
        }
    }
    else {
        resultOK = false;
        Logger::LogError("Unexpected extension status. expected=NORMAL/KILLING; actual=" + extObj->GetStatus());
    }

    trace.NOTE("Finished with success = " + MdsdUtil::ToString(resultOK));
    return resultOK;
}


bool
ExtensionMgmt::HandleExtensionFailure(ExtensionInfo * extObj)
{
    Trace trace(Trace::Extensions, "ExtensionMgmt::HandleExtensionFailure");
    bool resultOK = true;
    if (!extObj) {
        Logger::LogError("Unexpected nullptr for extension object.");
        return false;
    }

    extObj->Status = ExtensionInfo::ExtStatus::BAD;

    unsigned int extlife = static_cast<unsigned int>((time(NULL) - extObj->StartTime));
    if (EXT_RETRY_TIMEOUT_SECONDS >= extlife) {
        extObj->RetryCount++;
    }
    else {
        extObj->RetryCount = 0;
    }

    trace.NOTE("Extension last life: " + std::to_string(extlife) + " seconds, retry count: " + std::to_string(extObj->RetryCount));
    if (EXT_MAX_RETRIES >= extObj->RetryCount) {
        trace.NOTE("Meet retry criteria. Restart extension.");
        resultOK = resultOK && StartExtension(extObj->MetaData);
    }
    else {
        trace.NOTE("Exceed max retries. Stop retrying. Delete it from cache.");
        extObj->Status = ExtensionInfo::ExtStatus::EXIT;
        resultOK = resultOK && ExtensionList::DeleteItem(extObj->MetaData.Name);
    }

    trace.NOTE("Finished with success = " + MdsdUtil::ToString(resultOK));
    return resultOK;
}


bool
ExtensionMgmt::KillProcessByForce(pid_t pid, const boost::system::error_code& error) const
{
    Trace trace(Trace::Extensions, "ExtensionMgmt::KillProcessByForce");
    bool resultOK = true;

    TRACEINFO(trace, "pid=" << pid);

    if (boost::asio::error::operation_aborted == error) {
        trace.NOTE("Operation is aborted. Do nothing.");
        resultOK = false;
    }
    else {
        ExtensionInfo * obj = ExtensionList::GetItem(pid);
        if (obj->StopTimerCancelled) {
            trace.NOTE("Extension with pid " + std::to_string(pid) + " is already cancelled. Stop further action.");
        }
        else {
            bool isPsExist = true;
            resultOK = SendSignalToProcess(pid, SIGKILL, &isPsExist);
        }
    }
    return resultOK;
}

bool
ExtensionMgmt::SendSignalToProcess(pid_t pid, int signum, bool *pIsPsExist) const
{
    Trace trace(Trace::Extensions, "ExtensionMgmt::SendSignalToProcess");
    assert(0 < pid);
    assert(0 < signum);

    bool resultOK = true;
    trace.NOTE("Start to send signal " + std::to_string(signum) + " to pid " + std::to_string(pid));
    (*pIsPsExist) = true;

    if (-1 == kill(pid, signum))
    {
        int killerr = errno;
        std::string errstr = MdsdUtil::GetErrnoStr(errno);
        if (ESRCH == killerr)
        {
            trace.NOTE("process was not found with pid=" + std::to_string(pid));
            (*pIsPsExist) = false;
        }
        else
        {
            Logger::LogError("Error: failed to send signal. Error string: " + errstr);
            resultOK = false;
        }
    }
    else
    {
        trace.NOTE("Sucessfully sent signal.");
    }
    return resultOK;
}

extern "C" 
{
    
void CatchSigChld(int signo)
{
    ExtensionMgmt *e = ExtensionMgmt::GetInstance();
    if (e) {
        e->CatchSigChld(signo);
    }
}

void CleanupExtensions()
{
    ExtensionMgmt *e = ExtensionMgmt::GetInstance();
    if (e)
    {
        e->StopAllExtensions();
    }
}

}

