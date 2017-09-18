// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _DAEMONCONF_HH_
#define _DAEMONCONF_HH_
      
#include <sys/types.h>
#include <string>

class DaemonConf
{
public:
    /*
      Run mdsd in daemon mode by forking the child process.
    */
    static void RunAsDaemon(const std::string& pidfile);

    /*
      Change a file's user and group to the daemon runtime user/group.
     */
    static bool Chown(const std::string& filepath);

private:
    /*
      Get a given username's user id. If user is not found, return 0.
    */
    static uid_t GetUidFromName(const char* username);

    /*
      Get a given groupname's groupid. If group is not found, return 0.
    */
    static gid_t GetGidFromName(const char* groupname);

    /*
      Set daemon userid and groupid to given Ids. If uid or gid are 0, do nothing.
    */
    static void SetPriv(uid_t uid, gid_t gid);

    /*
      Write final daemon process's process Id to pid file.
     */
    static bool WritePid(const std::string & pidfile);


private:
    constexpr static const char * runAsUser = "syslog";
    constexpr static const char * runAsGroup = "syslog";
};

#endif
