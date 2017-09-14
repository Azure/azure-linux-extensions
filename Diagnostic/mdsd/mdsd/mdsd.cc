// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "Logger.hh"
#include "ProtocolListenerMgr.hh"
#include "MdsdConfig.hh"
#include "LocalSink.hh"
#include "Engine.hh"
#include "Version.hh"
#include "Trace.hh"
#include "DaemonConf.hh"
#include "ExtensionMgmt.hh"
#include "Utility.hh"
#include "HttpProxySetup.hh"
#include "EventHubUploaderMgr.hh"
#include "XJsonBlobBlockCountsMgr.hh"

#include <cstdlib>
#include <cerrno>
#include <system_error>
#include <cstdio>
#include <cstring>
#include <string>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <memory>

extern "C" {
#include <unistd.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <pthread.h>
#include <sys/time.h>
#include <sys/resource.h>
}

using std::string;
using std::to_string;
using std::cerr;
using std::endl;

void usage();
extern "C" { void SetSignalCatchers(int); }
void TerminateHandler();

// This is a file-scope string
static std::string config_file_path;
static std::string autokey_config_path;

int
main(int argc, char **argv)
{
    int mdsd_port = 29130;    // Default port number, grabbed out of the air

    Engine* engine = Engine::GetEngine();
    bool mdsdConfigValidationOnly = false;
    bool runAsDaemon = false; // If true, run at Daemon mode instead of application mode.
    bool coreDumpAtFatal = false; // If true, create core dump when received fatal signals.
    std::string proxy_setting_string; // E.g., "[http:]//[username:password@]www.xyz.com:8080/"
    bool disableLogging = false; // Useful for development testing
    bool retryRandomPort = false;

    Logger::Init();

    std::string mdsd_config_dir;
    std::string mdsd_run_dir;
    std::string mdsd_log_dir;

    try
    {
        mdsd_config_dir = MdsdUtil::GetEnvDirVar("MDSD_CONFIG_DIR", "/etc/mdsd.d");
        mdsd_run_dir = MdsdUtil::GetEnvDirVar("MDSD_RUN_DIR", "/var/run/mdsd");
        mdsd_log_dir = MdsdUtil::GetEnvDirVar("MDSD_LOG_DIR", "/var/log");
    } catch (std::runtime_error& ex) {
        Logger::LogError(ex.what());
        exit(1);
    }

    config_file_path = mdsd_config_dir + "/mdsd.xml";
    autokey_config_path = mdsd_config_dir + "/mdsautokey.cfg";
    const std::string config_cache_dir = mdsd_config_dir + "/config-cache";

    std::string mdsd_prefix = mdsd_run_dir + "/";
    std::string mdsd_role = "default"; // altered by '-r'
    std::string mdsd_role_prefix = mdsd_prefix + mdsd_role; // replaced with '-r' value if it starts with '/'
    std::string ehSaveDir = mdsd_run_dir + "/eh"; // Full path to save failed Event Hub events.

    // default mdsd log file paths, they can be overwritten by input args.
    std::string mdsdInfoFile = mdsd_log_dir + "/mdsd.info";
    std::string mdsdWarnFile = mdsd_log_dir + "/mdsd.warn";
    std::string mdsdErrFile = mdsd_log_dir + "/mdsd.err";

    LocalSink::Initialize();

    {
        int opt;
        while ((opt = getopt(argc, argv, "bc:CDde:jo:P:p:Rr:S:T:vVw:")) != -1) {
            switch (opt) {
            case 'b':
                engine->BlackholeEvents();
                break;
            case 'c':
                config_file_path = optarg;
                break;
            case 'C':
                coreDumpAtFatal = true;
                break;
            case 'D':
                disableLogging = true;
                break;
            case 'd':
                runAsDaemon = true;
                break;
            case 'e':
                mdsdErrFile = optarg;
                break;
            case 'j':
                Trace::AddInterests(Trace::EventIngest);
                break;
            case 'o':
                mdsdInfoFile = optarg;
                break;
            case 'P':
                proxy_setting_string = optarg;
                try {
                    MdsdUtil::CheckProxySettingString(proxy_setting_string);
                } catch (const MdsdUtil::HttpProxySetupException& e) {
                    cerr << "Invalid proxy specification for -P option: "
                         << e.what() << endl;
                    usage();
                }
                break;
            case 'p':
                mdsd_port = atoi(optarg);
                if (mdsd_port < 0) { // We now allow '-p 0' (binding to a random port)
                    usage();
                }
                break;
            case 'R':
                retryRandomPort = true;
                break;
            case 'r':
                if (*optarg == '/') {
                    // Special case to allow overriding of the default mdsd_prefix (e.g. /var/run/mdsd).
                    // This may be needed in cases where mdsd will not be able to create or write to /var/run/mdsd.
                    // This is useful during dev testing and might also be needed for LAD.
                    mdsd_role_prefix = optarg;
                } else {
                    mdsd_role_prefix = mdsd_prefix + std::string(optarg);
                }
                break;
            case 'S':
                ehSaveDir = optarg;
                if (ehSaveDir.empty()) {
                    cerr << "'-S' requires a valid pathname." << endl;
                    usage();
                }
                break;
            case 'T':
                try {
                    unsigned long val = std::stol(string(optarg), 0, 0);
                    Trace::AddInterests(static_cast<Trace::Flags>(val));
                } catch (std::exception & ex) {
                    usage();
                }
                break;
            case 'v':
                mdsdConfigValidationOnly = true;
                break;
            case 'V':
                cerr << Version::Version << endl;
                exit(0);
            case 'w':
                mdsdWarnFile = optarg;
                break;
            default: /* '?' */
                usage();
            }
        }
    }

    // For config xml validation only, log to console.
    if (!mdsdConfigValidationOnly) {
        // Only try to create the mdsd_run_dir dir if it wasn't overridden via '-r' option.
        if (mdsd_role_prefix.substr(0, mdsd_run_dir.length()) == mdsd_run_dir) {
            try {
                MdsdUtil::CreateDirIfNotExists(mdsd_run_dir, 01755);
            }
            catch (std::exception &e) {
                Logger::LogError("Fatal error: unexpected exception at creating dir '" + mdsd_run_dir + "'. " +
                                 "Reason: " + e.what());
                exit(1);
            }
        }

        try {
            MdsdUtil::CreateDirIfNotExists(ehSaveDir, 01755);
        }
        catch(std::exception & e) {
            Logger::LogError("Fatal error: unexpected exception at creating dir '" + ehSaveDir + "'. " +
                             "Reason: " + e.what());
            exit(1);
        }

        if (!disableLogging) {
            Logger::SetInfoLog(mdsdInfoFile.c_str());
            Logger::SetWarnLog(mdsdWarnFile.c_str());
            Logger::SetErrorLog(mdsdErrFile.c_str());
        }

        if (0 == geteuid() && runAsDaemon) {
            // Change ownership of logs if we're running as root
            DaemonConf::Chown(mdsdInfoFile);
            DaemonConf::Chown(mdsdWarnFile);
            DaemonConf::Chown(mdsdErrFile);

            if (mdsd_role_prefix.substr(0, mdsd_run_dir.length()) == mdsd_run_dir)
            {
                DaemonConf::Chown(mdsd_run_dir);
            }
            DaemonConf::Chown(ehSaveDir);
        }
    }

    try {
        XJsonBlobBlockCountsMgr::GetInstance().SetPersistDir(mdsd_role_prefix + "_jsonblob_blkcts", mdsdConfigValidationOnly);
    } catch (std::exception& e) {
        Logger::LogError(std::string("Unexpected exception from setting JsonBlobBlockCountsMgr persist dir. Reason: ").append(e.what()));
        exit(1);
    }

    if (runAsDaemon) {
        DaemonConf::RunAsDaemon(mdsd_role_prefix + ".pid");
    }

    SetSignalCatchers(coreDumpAtFatal);
    std::set_terminate(TerminateHandler);

    if (mdsdConfigValidationOnly) {
        std::unique_ptr<MdsdConfig> newconfig(new MdsdConfig(config_file_path, autokey_config_path));
        int status = 0;
        if (newconfig->GotMessages(MdsdConfig::anySeverity)) {
            cerr << "Parse reported these messages:" << endl;
            newconfig->MessagesToStream(cerr, MdsdConfig::anySeverity);
            status = 1;
        } else {
            cerr << "Parse succeeded with no messages." << endl;
        }
        newconfig.reset();
        exit(status);
    }

    if (!mdsd::EventHubUploaderMgr::GetInstance().SetTopLevelPersistDir(ehSaveDir)) {
        exit(1);
    }

    ProtocolListenerMgr::Init(mdsd_role_prefix, mdsd_port, retryRandomPort);

    MdsdConfig* newconfig = new MdsdConfig(config_file_path, autokey_config_path);
    auto valid = newconfig->ValidateConfig(true);
    if (!valid || !newconfig->IsUseful()) {
        Logger::LogError("Error: Config invalid or not useful (if there's no config parse error). Abort mdsd.");
        delete newconfig;
        exit(1);
    }
    Engine::SetConfiguration(newconfig);

    try {
        MdsdUtil::SetStorageHttpProxy(proxy_setting_string, { "MDSD_http_proxy", "https_proxy", "http_proxy" });
    }
    catch(const std::exception & ex) {
        Logger::LogError(ex.what());
        exit(1);
    }

    ExtensionMgmt::StartExtensionsAsync(Engine::GetEngine()->GetConfig());

    // Start the listeners
    auto plmgmt = ProtocolListenerMgr::GetProtocolListenerMgr();
    try
    {
        if (!plmgmt->Start()) {
            Logger::LogError("One or more listeners failed to start.");
            exit(1);
        }
    }
    catch(std::exception& ex) {
        Logger::LogError("Error: unexpected exception while starting listeners: " + std::string(ex.what()));
        exit(1);
    }
    catch(...) {
        Logger::LogError("Error: unknown exception while starting listeners.");
        exit(1);
    }

    // Wait to be stopped
    plmgmt->Wait();

    return 0;
}

void
usage()
{
    cerr << "Usage:" << endl
    << "mdsd [-Abdjv] [-c path] [-e path] [-o path] [-p port] [-P proxy_setting] [-r path] [-S path] [-T flags] [-w path]" << endl << endl
    << "-A  Don't enable config auto management." << endl
    << "-b  Don't forward events to MDS (blackhole them instead)" << endl
    << "-c  Specifies the path to the configuration XML file" << endl
    << "-C  Don't suppress core dump when dying due to fatal signals" << endl
    << "-D  Disable logging to files. All log output will instead go to STDERR (fd 2)." << endl
    << "-d  Run mdsd as a daemon" << endl
    << "-e  Specifies the path to which mdsd error logs are dumped" << endl
    << "-j  Dump all JSON events to stdout as they're received" << endl
    << "-o  Specifies the path to which mdsd informative logs are dumped" << endl
    << "-p  Specifies the port on which the daemon listens for stream connections (0 can be passed" << endl
    << "    as port, in which case a randomly available port will be picked). The port will only be" << endl
    << "    bound to 127.0.0.1 (loopback). If the specified non-zero port is in use," << endl
    << "    and '-R' is specified, then mdsd will try to bind to a randomly available port instead." << endl
    << "    Either way, the bound port number will be written to a file whose path is derived" << endl
    << "    from -r info or default (/var/run/mdsd/default.pidport)." << endl
    << "-P  Specifies an HTTP proxy. If not set, use environment variable in order of MDSD_http_proxy," << endl
    << "    https_proxy, http_proxy, with first one tried first. If -P is set, override environment variables." << endl
    << "-R  Try binding to a random port if binding to the default/specified port fails." << endl
    << "-r  Specifies the role name or file prefix that mdsd will use to construct the paths to the" << endl
    << "    pidport and unix domain socket files. If the argument starts with '/' then the value is" << endl
    << "    used as the file prefix, otherwise it is used as the role name and the file prefix is " << endl
    << "    '/var/run/mdsd/' + role name (e.g. if role name is 'test' then the prefix is '/var/run/mdsd/test')." << endl
    << "-S  Specifies directory to save Event Hub events. syslog user needs to have rwx" << endl
    << "    access to it. If the directory does not exist, mdsd will try to create it." << endl
    << "-T  Enable tracing for modules selected by flags" << endl
    << "-v  Validate configuration file and exit" << endl
    << "-V  Print version and exit" << endl
    << "-w  Specifies the path to which mdsd warning logs are dumped" << endl;
    exit(1);
}

extern "C" void
LoadNewConfiguration()
{
    Trace trace(Trace::ConfigLoad, "LoadNewConfiguration");

    Logger::LogInfo("Reloading configuration (SIGHUP caught)");

    MdsdConfig *newconfig = new MdsdConfig(config_file_path, autokey_config_path);
    bool valid = newconfig->ValidateConfig(true);
    if (!valid || !newconfig->IsUseful()) {
        delete newconfig;
    }
    else {
        Engine::SetConfiguration(newconfig);
        ExtensionMgmt::StartExtensionsAsync(newconfig);
    }
}

extern "C" void
SetCoreDumpLimit()
{
    Logger::LogInfo("Set resource limits for core dump.");

    struct rlimit core_limit;
    if (getrlimit(RLIMIT_CORE, &core_limit) < 0) {
        std::string errstr = MdsdUtil::GetErrnoStr(errno);
        Logger::LogError("Error: getrlimit failed. Reason: " + errstr);
        return;
    }

    if (RLIM_INFINITY != core_limit.rlim_cur) {
        core_limit.rlim_cur = RLIM_INFINITY;
        core_limit.rlim_max = core_limit.rlim_cur;

        if (setrlimit(RLIMIT_CORE, &core_limit) < 0) {
            std::string errstr = MdsdUtil::GetErrnoStr(errno);
            Logger::LogError("Error: setrlimit failed. Reason: " + errstr);
        }
    }
}

// vim: set tabstop=4 softtabstop=4 shiftwidth=4 expandtab :
