// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _EXTENSIONINFO_HH_
#define _EXTENSIONINFO_HH_

#include <string>
#include <ctime>
#include <map>
#include <mutex>
#include <functional>
#include <set>
#include <unordered_set>
#include <vector>
#include <future>
#include <stddef.h>
#include <boost/asio.hpp>
#include <atomic>

extern "C" {
#include <unistd.h>
#include <semaphore.h>
}

/// <summary>
/// Keep track of an extension's meta data. Any of these data change
/// will mean the extension definition changed.
/// </summary>
struct ExtensionMetaData
{
    std::string Name;
    std::string CommandLine;
    std::string Body;
    std::string AlterLocation;

    ExtensionMetaData()
    {
    }

    ExtensionMetaData(
        const std::string & name,
        const std::string & cmdline,
        const std::string & body,
        const std::string & loc
        ) : Name(name), CommandLine(cmdline), Body(body), AlterLocation(loc)
    {}


    /// <summary>
    /// Compare this extension's meta data with some other meta data.
    /// Return true if they are the same, return false otherwise.
    /// </summary>
    bool operator==(const ExtensionMetaData & other) const;
};

/// <summary>
/// Keep track an extension process's information.
/// </summary>
class ExtensionInfo
{
public:
    enum ExtStatus {
        NORMAL,     // A new extension.
        BAD,        // An extension starts to run but failed in the middle.
        KILLING,    // An extension killed by SIGINT, or killed externally.
        EXIT,       // An extension stopped and killed already.
        UNKNOWN     // Unknown. Should be never in this status.
    };
    
    // An extension's metadata.
    ExtensionMetaData MetaData;
    
    // Process id of the extension process.
    pid_t Pid = 0;

    // Process start time in number of seconds in UTC.
    time_t StartTime = 0;

    // Number of times the extension is retried since last reset.
    unsigned int RetryCount = 0;

    // Extension status.
    ExtStatus Status = UNKNOWN;
    
    // asio timer to kill the extension by force.
    boost::asio::deadline_timer * StopTimer;

    // whether the extension timer is already cancelled or not.
    std::atomic<bool> StopTimerCancelled;

    ExtensionInfo();

    ~ExtensionInfo();

    /// <summary>
    /// Get the string format of the status.
    /// </summary>
    std::string GetStatus() const;

    /// <summary>
    /// Get the string format of the status.
    /// </summary>
    static std::string StatusToString(ExtStatus s);

private:
    static std::map<ExtStatus, std::string> _statusMap;
};

/// <summary>
/// Keep track of all extension processes. 
/// </summary>
class ExtensionList
{
public:

    /// <summary>
    /// Get number of items.
    /// </summary>
    static size_t GetSize();

    /// <summary>
    /// Add an item to the list. If the item already exists, free the memory of
    /// existing one and add the new one.
    /// Return true if no error. Return false if the input is invalid.
    /// </summary>
    static bool AddItem(ExtensionInfo * extObj);

    /// <summary>
    /// Get an item given its name.
    /// Return the object pointer.
    /// Return nullptr if not found or given name is invalid.
    /// The caller shouldn't free the object pointer.
    /// </summary>
    static ExtensionInfo * GetItem(const std::string & extname);

    /// <summary>
    /// Get an item given its process id.
    /// Return the object pointer.
    /// Return nullptr if not found or given pid is invalid.
    /// The caller shouldn't free the object pointer.
    /// </summary>
    static ExtensionInfo * GetItem(pid_t extPid);

    /// <summary>
    /// Update an existing item's pid.
    /// Return true if success, false if any error.
    /// </summary>
    static bool UpdateItem(pid_t oldpid, pid_t newpid);

    /// <summary>
    /// Delete an item from the list.
    /// Return true if the item is actually deleted. 
    /// Return false if the given name is invalid or not found.
    /// </summary>
    static bool DeleteItem(const std::string & extname);

    /// <summary>
    /// Delete a set of items with given names.
    /// Return true if all items are actually deleted, or set is empty.
    /// Return false if any item is not found.
    /// </summary>
    static bool DeleteItems(const std::set<std::string>& extnames);
    static void DeleteAllItems();

    /// <summary>
    /// Use a given function to iterate over each extension object.
    /// </summary>
    static void ForeachExtension(const std::function<void(ExtensionInfo*)>& fn);

    /// <summary>
    /// Add a pid to the pid set.
    /// </summary>
    static void AddPid(pid_t pid);

    /// <summary>
    /// Get all pids of the pid set. Clear the original one.
    /// </summary>
    static std::unordered_set<pid_t> GetAndClearPids();


private:
    static std::map<const std::string, ExtensionInfo*> _extlistByName;
    static std::map<pid_t, ExtensionInfo*> _extlistByPid;

    static std::mutex _listmutex;

    /// Store a list of PIDs that needs to be killed because their
    /// meta data are changed.
    static std::unordered_set<pid_t> _killList;
    static std::mutex _klmutex;
};

class MdsdExtension;
class MdsdConfig;

/// <summary>
/// Use configuration to create new extension processes, then manage
/// the extension processes.
/// </summary>
class ExtensionMgmt
{
public:
    /// <summary>
    /// Free all resources.
    /// </summary>
    ~ExtensionMgmt();

    /// <summary>
    /// Get a singleton instance.
    /// </summary>
    static ExtensionMgmt* GetInstance();

    /// <summary>
    /// Start all extensions given a config synchronously. It will also
    /// stop any obsolete extension.
    /// Return true if success; Return false for any error.
    /// </summary>
    static bool StartExtensions(MdsdConfig * config);

    /// <summary>
    /// Calls StartExtensions() in async.
    /// </summary>
    static void StartExtensionsAsync(MdsdConfig * config);

    /// <summary>
    /// Stop all extensions.
    /// Return true for success, false for any error.
    /// </summary>
    bool StopAllExtensions();

    /// <summary>
    /// Defines SIGCHLD signal handler, which is from child extension process. It will
    /// - release child process resources.
    /// - change extension object status.
    /// - update the extension object in ExtensionList.
    /// </summary>
    void CatchSigChld(int signo);

private:
    ExtensionMgmt();

    /// <summary>
    /// Define semaphore to synchronize between stopped extensions
    /// (handled in SIGCHLD signal handler) and creating new ones (in main thread)
    /// </summary>
    sem_t _extsem;

    /// <summary>
    /// True if semaphore is initialized properly, false if any error.
    /// </summary>
    bool _extsemInitOK;

    /// <summary>
    /// Singleton instance.
    /// </summary>
    static ExtensionMgmt * _extInstance;

    /// <summary>
    /// Environment name for extension. Extension uses it to read the value defined in <Body>
    /// </summary>
    static constexpr const char* BODYENV = "MON_EXTENSION_BODY";

    /// <summary>
    /// The grace period in number of seconds for the extension process to 
    /// terminate itself before it is killed by force. Because mdsd service's 
    /// grace period is 30-second, make it shorter than that.
    /// </summary>
    static const unsigned int EXT_TERMINATE_GRACE_SECONDS = 20;

    /// <summary>
    /// The maximum number of retries to start extension within
    /// given window seconds.
    /// </summary>
    static const unsigned int EXT_MAX_RETRIES = 3;

    /// <summary>
    /// Numbe of seconds to wait before retrying the extension
    /// </summary>
    static const unsigned int EXT_RETRY_WAIT_SECONDS = 5;

    /// <summary>
    /// Extension restart retry timeout in number of seconds.
    /// If the time difference is bigger than this window, reset
    /// extension's RetryCount to be 0.
    /// </summary>
    static const unsigned int EXT_RETRY_TIMEOUT_SECONDS = 60;

    /// <summary>
    /// Initialize semaphore. Return true if no error; return false for any error.
    /// </summary>
    bool InitSem();

    /// <summary>
    /// Start all extensions defined in a config. It won't stop any extension.
    /// It will return the extension names defined in the config in extlistInConfig.
    /// Return true for success, false for any error.
    /// </summary>
    bool StartExtensionsFromConfig(
        MdsdConfig * config, 
        std::set<std::string> & extlistInConfig);

    /// <summary>
    /// Restart all extensions whose meta data were changed.
    /// Return true if success, false for any error.
    /// <param name="changedList">List of changed extensions.</param>
    /// <param name="newDataList">The meta data for the changed extensions. Key is old extension pid. </param>
    /// </summary>
    bool RestartChangedExtensions(const std::vector<ExtensionInfo*> & changedList,
        const std::map<pid_t, ExtensionMetaData> & newDataList);

    /// <summary>
    /// Wait until any extension's change status SIGCHLD caught, or until timed out
    /// after SEM_WAIT_SECONDS seconds.
    /// Return true if success, false if error or timed out.
    /// </summary>
    bool WaitForAnyExtStop();

    /// <summary>
    /// Start all extensions whose meta data were changed.
    /// Return true for success, false for any error.
    /// </summary>
    bool StartAllChangedExts(const std::unordered_set<pid_t> changedPids,
        const std::map<pid_t, ExtensionMetaData> & newDataList) const;

    /// <summary>
    /// Start one extension instance whose meta data were changed.
    /// Return true for success, false for any error.
    /// </summary>
    bool StartOneChangedExt(pid_t changedPid, const ExtensionMetaData & metadata) const;

    /// <summary>
    /// Any extension that's not in given set is obsolete.
    /// For each obsolete extension, delete it from ExtensionList and Stop it.
    /// Return true if no error is found. Otherwise, return false.
    /// </summary>
    bool StopObsoleteExtensions(const std::set<std::string> & extlistInConfig) const;

    /// <summary>
    /// Block or unblock a given signal to the process.
    /// </summary>
    bool MaskSignal(bool isBlock, int signum) const;

    /// <summary>
    /// Attempt to start a given extension process.
    /// Return true if it starts OK, return false for any error.
    /// If starting OK, the extensionInfo object will be added to ExtensionList. Its memory
    /// will be managed there.
    /// </summary>
    bool StartExtension(
        const std::string & extName,
        const std::string & cmdline,
        const std::string & body,
        const std::string & alterLocation) const;

    /// <summary>
    /// Start an extension process given its meta data.
    /// Return true if it starts OK, return false for any error.
    /// </summary>
    bool StartExtension(const ExtensionMetaData & metaData) const;

    /// <summary>
    /// Either create a new ExtensionInfo object or update existing one in
    /// the extension list. If an extension failed to be created, it should not be
    /// retried.
    /// </summary>
    bool UpdateExtensionList(
        ExtensionInfo * oldExtInfo,
        const std::string & extName,
        const std::string & cmdline,
        const std::string & body,
        const std::string & alterLocation,
        pid_t pid,
        bool extFailed) const;

    /// <summary>
    /// Stop an extension process. It won't remove the ExtensionInfo item from ExtensionList.
    /// </summary>
    bool StopExtension(ExtensionInfo * extObj) const;

    /// <summary>
    /// Update the information of extension given its pid.
    /// Return true for success, false for error.
    /// </summary>
    bool UpdateStoppedExtension(pid_t extpid);


    /// <summary>
    /// Handle extension that fails itself. Either retry it or delete it forever based on its status.
    /// Return true if success, false if any error.
    /// </summary>
    bool HandleExtensionFailure(ExtensionInfo * extObj);

    /// <summary>
    /// This is to unblock all signal mask. For example, in child process, child process
    /// may use this function to unblock signal mask inherited from parent process.
    /// Return errno.
    /// <summary>
    int UnblockSignals() const;

    /// <summary>
    /// Kill a process by sending it SIGKILL. It doesn't validate whether 
    /// the process is actually killed or not. 
    /// Return true if signal is sent out properly.
    /// Return false if signal is not sent out, or the operation is aborted.
    /// <summary>
    bool KillProcessByForce(pid_t pid, const boost::system::error_code& error) const;

    /// <summary>
    /// Send signal signum to process id pid. 
    /// Return whether the process exists or not through pIsPsExist.
    /// Return true if signal is sent out properly, false if error. If process doesn't exist,
    /// also return true.
    /// <param name="pid"> process id </param>
    /// <param name="signum"> signal number </param>
    /// <param name="pIsPsExist"> Return whether the process exists or not </param>
    /// <summary>
    bool SendSignalToProcess(pid_t pid, int signum, bool *pIsPsExist) const;

};


#endif // _EXTENSIONINFO_HH_
