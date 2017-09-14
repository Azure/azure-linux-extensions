// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "DaemonConf.hh"
#include "Logger.hh"
#include "Trace.hh"
#include "Utility.hh"
#include "Version.hh"

#include <string>
#include <sstream>

extern "C" {
#include <stdlib.h>
#include <unistd.h>
#include <sys/types.h>
#include <errno.h>
#include <pwd.h>
#include <grp.h>
#include <sys/stat.h>
#include <fcntl.h>
}


uid_t DaemonConf::GetUidFromName(const char* username)
{
    Trace trace(Trace::Daemon, "GetUidFromName");

    uid_t uid = 0;    
    if (!username) {
        Logger::LogError("Error: GetUidFromName(): unexpected NULL pointer for username.");
        return uid;
    }
    
    struct passwd *resultObj;
    struct passwd wrkObj;
    char buf[2048];
    
    getpwnam_r(username, &wrkObj, buf, sizeof(buf), &resultObj);
    if (resultObj == NULL) {
        Logger::LogWarn("WARN: GetUidFromName(): No user called '" + std::string(username) + "' is found.");
    }
    else {
        uid = resultObj->pw_uid;
    }
    trace.NOTE("Name='" + std::string(username) + "'. UID=" + std::to_string(uid));
    return uid;
}


gid_t DaemonConf::GetGidFromName(const char* groupname)
{
    Trace trace(Trace::Daemon, "GetGidFromName");
    gid_t gid = 0;    
    if (!groupname) {
        Logger::LogError("Error: GetGidFromName(): unexpected NULL for groupname");
        return gid;
    }

    struct group *resultObj;
    struct group wrkObj;
    char buf[2048];
    
    getgrnam_r(groupname, &wrkObj, buf, sizeof(buf), &resultObj);
    if (resultObj == NULL) {
        Logger::LogWarn("WARN: GetGidFromName(): No group called '" + std::string(groupname) + "' is found.");
    }
    else {
        gid = resultObj->gr_gid;
    }
    
    trace.NOTE("GetGidFromName() returned: Group='" + std::string(groupname) + "'. GID=" + std::to_string(gid));
    return gid;
}


void DaemonConf::SetPriv(uid_t uid, gid_t gid)
{
    Trace trace(Trace::Daemon, "SetPriv");
    std::string uidstr = std::to_string(uid);
    std::string gidstr = std::to_string(gid);

    if (0 == uid) {
        Logger::LogError("Error: unexpected user id " + uidstr + ". Do nothing.");
        return;
    }
    if (0 == gid) {
        Logger::LogError("Error: unexpected group id " + gidstr + ". Do nothing.");
        return;
    }    

    int r2 = setgid(gid);
    if (r2) {
        int errnum = errno;
        std::string errstr = MdsdUtil::GetErrnoStr(errnum);
        Logger::LogError("Error: fatal error. setgid() failed to set id " + gidstr + ". error: " + errstr);
        exit(1);
    }
    trace.NOTE("mdsd's groupid changed to " + gidstr);

    int r1 = setuid(uid);
    if (r1) {
        int errnum = errno;
        std::string errstr = MdsdUtil::GetErrnoStr(errnum);
        Logger::LogError("Error: fatal error. setuid() failed to set id " + uidstr + ". error: " + errstr);
        exit(1); 
    }
    else {        
        trace.NOTE("mdsd's userid changed to id " + uidstr);
    }
}

/*
  Run mdsd in daemon mode by forking the child process.
 */
void DaemonConf::RunAsDaemon(const std::string & pidfile)
{
    Trace trace(Trace::Daemon, "RunAsDaemon");
    pid_t ppid = getpid();
    pid_t pid = fork();
    if (-1 == pid) {
        int errnum = errno;
        std::string errstr = MdsdUtil::GetErrnoStr(errnum);
        Logger::LogError("Fork child process failed with -1. error: " + errstr);
        exit(1);
    }
    if (pid > 0) {
        Logger::LogError("Parent process " + std::to_string(ppid) + " exit. child process id=" + std::to_string(pid));
        exit(0);
    }
    
    if (WritePid(pidfile) == false) {
        exit(1);
    }
    
    umask(0);
    // Create a new session for the child process
    pid_t sid = setsid();
    if (sid < 0) {
        int errnum = errno;
        std::string errstr = MdsdUtil::GetErrnoStr(errnum);
        Logger::LogError("child process setsid() returned " + std::to_string(sid) + ". error: " + errstr);
        exit(1);
    }
    if ((chdir("/")) < 0) {
        int errnum = errno;
        std::string errstr = MdsdUtil::GetErrnoStr(errnum);
        Logger::LogError("Chdir() to root directory failed: " + errstr);
        exit(1);
    }
    
    close(STDIN_FILENO);
    close(STDOUT_FILENO);
    close(STDERR_FILENO);

    int uid = GetUidFromName(runAsUser);
    int gid = GetGidFromName(runAsGroup);
    if (uid >= 0 && gid >= 0) {
        SetPriv(uid, gid);
    }

    std::ostringstream msg;
    msg << "START mdsd daemon ver(" << Version::Version << ") pid(" << getpid() << ") uid(" << uid << ") gid (" << gid << ")" << std::endl;
    Logger::LogError(msg.str());
    Logger::LogWarn(msg.str());
    Logger::LogInfo(msg.str());
}

bool DaemonConf::WritePid(const std::string & pidfile)
{
    Trace trace(Trace::Daemon, "WritePid");
    int fd = open(pidfile.c_str(), O_WRONLY|O_CREAT|O_CLOEXEC, 0644);
    MdsdUtil::FdCloser fdCloser(fd);

    if (fd < 0) {
        int errnum = errno;
        std::ostringstream buf;
        buf << "Error: failed to open or create Pid file: " << pidfile << ". " << MdsdUtil::GetErrnoStr(errnum);
        Logger::LogError(buf.str());
        return false;
    }
    
    bool status = true;
    try{
        MdsdUtil::WriteBufferAndNewline(fd, std::to_string(getpid()));
    }
    catch (const std::runtime_error & e) {
        Logger::LogError(std::string("Error writing pid file: ") + e.what());
        status = false;
    }

    return status;
}

bool DaemonConf::Chown(const std::string& filepath)
{   
    bool isOK = true;

    uid_t uid = GetUidFromName(runAsUser);
    gid_t gid = GetGidFromName(runAsGroup);
    if (uid > 0 && gid > 0) {
        int r = chown(filepath.c_str(), uid, gid);
        if (r) {
            int errnum = errno;
            std::string errstr = MdsdUtil::GetErrnoStr(errnum);
            Logger::LogError("Error: Chown() failed. logfile='" + filepath + "' user='" + runAsUser
                             + "' group='" + runAsGroup + "' . error: " + errstr);
            isOK = false;
        }
    }
    return isOK;
}

// vim: se ai sw=4 expandtab tabstop=4 :
