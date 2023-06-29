#include <libudev.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include <time.h>
#include <errno.h>
#include <signal.h>
#include <getopt.h>
#include <fcntl.h>
#include <mntent.h>
#include <sys/wait.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <libmount/libmount.h>
#include <deque>
#include <vector>
#include <sstream>
#include <algorithm>
#include <thread>
#include <chrono>

#define LOG_PRIORITY 3
#define LOG_LEVEL 3
#define LOG_TO_CONSOLE 1

#define LOG_DIRETORY "/tmp"
#define LOG_FILE_TEMPLATE "%s/ade_vol_notif-%s.log"
#define ADE_MAX_EVENT_THRESHOLD_COUNT 15
#define ADE_MAX_ATTEMPT_FOR_DEVICE 3
#define ADE_COUNT_WAIT_TIME_SEC 3
#define ADE_PERIODIC_SCAN_SECONDS 900

enum class AdeStatus{ADE_NOT_STARTED,ADE_RUNNING,ADE_FINISHED};
AdeStatus ade_status = AdeStatus::ADE_NOT_STARTED;
time_t ade_finished;
bool thread_running_mnt=true;
bool unencrypted_fs_mounted = false;

// TODO: Make this a parameter to the program
static char log_file_path[1024];
void custom_log(const char *format, ...);

void thread_proc_mnt()
{
    //this is coped from ADE code
    std::vector<std::string> format_supported_file_systems{"ext4", "ext3", "ext2", "xfs", "btrfs"};
    const char *filename;
    struct libmnt_monitor *mn = mnt_new_monitor();
    mnt_monitor_enable_kernel(mn, true);
    custom_log("waiting for changes...\n");
    while (mnt_monitor_wait(mn, -1) > 0)
    {
        while(mnt_monitor_next_change(mn, &filename, NULL) == 0) {
        custom_log("mount change event logged for %s",filename);
        unencrypted_fs_mounted = false;
        FILE *fp = setmntent("/proc/self/mounts", "r");
        if (fp == NULL)
        {
            perror("Failed to open /proc/self/mounts");
            return;
        }

        struct mntent *mnt;
        while ((mnt = getmntent(fp)) != NULL)
        {
            std::string mnt_type(mnt->mnt_type);
            if (find(format_supported_file_systems.begin(),format_supported_file_systems.end(),mnt_type) != format_supported_file_systems.end())
            {
                // if mounted ext4 filesystem is not encrypted, set unencrypted_ext4_mounted to true
                // device name that doesn't contain mapper in the name and mnt_dir is not empty and not /boot
                std::string device_name(mnt->mnt_fsname);
                std::string mnt_dir(mnt->mnt_dir);
                if (device_name.find("mapper") == std::string::npos &&
                    !mnt_dir.empty() &&
                    mnt_dir != "/boot")
                {
                    unencrypted_fs_mounted= true;
                    custom_log("Unencrypted %s filesystem %s mounted on %s\n",mnt->mnt_type,mnt->mnt_fsname,mnt->mnt_dir);
                }
            }
        }
        endmntent(fp);
     }
    }
    mnt_unref_monitor(mn);
}


struct device{
        std::string syspath;
        std::string action;
        int ade_attempt_count;
};

void addNode(std::deque<device>& dq, const char* syspath, const char* action){
        dq.push_back({syspath,action,0});
}

void custom_log(const char *format, ...) {
    FILE *log_file = fopen(log_file_path, "a");
        if (!log_file)
    {
        fprintf(stderr, "Can't open log file %s", log_file_path);
        exit(1);
    }

    va_list args;
    va_start(args, format);
    // Append current date time in UTC.
    time_t now = time(NULL);
    struct tm *timeinfo;
    timeinfo = gmtime(&now);
    char bufferTime[80];
    strftime(bufferTime, sizeof(bufferTime), "[%Y-%m-%d %H:%M:%S] :", timeinfo);
    fprintf(log_file, "%s ", bufferTime);
    vfprintf(log_file, format, args);
    fprintf(log_file, "\n");
    fclose(log_file);
    va_end(args);


    if (LOG_TO_CONSOLE)
    {
        va_start(args, format);
        fprintf(stdout, "%s ", bufferTime);
        vprintf(format, args);
        printf("\n");
        va_end(args);
    }
    // TODO: Log to syslog additionally.
}

void sigint_handler(int signum) {
    custom_log("Caught SIGINT! Exiting...\n");
    exit(0);
}

void prepare_log_file(std::string log_directory) {
    // Create log file with date time in UTC.
    if (log_directory==""){
        log_directory=LOG_DIRETORY;
    }
    time_t now = time(NULL);
    struct tm *timeinfo;
    timeinfo = gmtime(&now);
    char current_time[80];
    strftime(current_time, sizeof(current_time), "%Y-%m-%dT%H-%M-%S", timeinfo);
    snprintf(log_file_path, sizeof(log_file_path), LOG_FILE_TEMPLATE, log_directory.c_str(), current_time);
}

void daemonize(int argc, char *argv[])
{
    custom_log("Going to daemonize");
    pid_t pid = fork();
    if (pid < 0) {
        custom_log("ERROR: Can't fork (error no=%d)\n", errno);
        exit(1);
    }
    if (pid > 0) {
        custom_log("Parent process is exiting, pid=%d", pid);
        exit(0);
    }
    umask(0);
    pid_t sid = setsid();
    if (sid < 0) {
        custom_log("ERROR: Can't set sid (error no=%d)\n", errno);
        exit(1);
    }
    if ((chdir("/")) < 0) {
        custom_log("ERROR: Can't change directory (error no=%d)\n", errno);
        exit(1);
    }
    close(STDIN_FILENO);
    close(STDOUT_FILENO);
    close(STDERR_FILENO);

    open("/dev/null",O_RDWR);
    dup(0);
}

void invoke_ade(const char* path,std::deque<device>&dq){
    ade_status = AdeStatus::ADE_RUNNING;
    //update counter in dq
    for(auto item = dq.begin(); item!=dq.end(); item++){
       item->ade_attempt_count+=1;
    }
    pid_t pAde = fork();
    if(pAde==0){
            // in case of child process.
            custom_log("child process %d created, running ADE", getpid());
            custom_log("changing directory to %s", path);
            chdir(path);
            execl(          "extension_shim.sh",
                            "extension_shim.sh",
                            "-c",
                            "main/handle.py --enable --vnscall",
                            NULL);
            int err = errno;
            custom_log("Failed to run process! error: %d",err);
            exit(1);
    }
    if(pAde>0){
       pid_t childPid = wait(NULL);
       custom_log("child process %d is completed",childPid);
    }
    //checking if daemon is still running
    pid_t pDaemon = fork();
    if(pDaemon==0){
            custom_log("child process %d created, checking daemon", getpid());
            custom_log("changing directory to %s", path);
            chdir(path);
            execl(          "ade_daemon_delay.sh",
                            "ade_daemon_delay.sh",
                            "extension_shim.sh",
                            NULL);
            int err = errno;
            custom_log("Failed to run process! error: %d",err);
            exit(1);

    }
    if(pDaemon>0){
       pid_t childPid = wait(NULL);
       custom_log("child process %d is completed",childPid);
    }
    ade_status = AdeStatus::ADE_FINISHED;
    ade_finished = time(NULL);
}

int is_device_crypted_from_syspath(const char* syspath){
        struct udev *udev;
        int ret = 0;
        udev = udev_new();
        struct udev_device* dev = udev_device_new_from_syspath(udev,syspath);
        const char* fs_usage = udev_device_get_property_value(dev,"ID_FS_USAGE");
        if(fs_usage!=NULL && strcmp(fs_usage,"crypto")==0) ret = 1;
        udev_device_unref(dev);
        udev_unref(udev);
        return ret;
}

bool is_devnode_added(std::deque<device>&dq, const char* syspath, const char* action){
        for(auto it:dq)
                if(             strcmp(it.syspath.c_str(),syspath)==0 &&
                                strcmp(it.action.c_str(),action)==0) return true;
        return false;
}

void cleanCryptedDevFromList(std::deque<device>&dq){
        using itdeque=std::deque<device>::iterator;
        std::vector<itdeque> cryptedDevices;
        //removing crypted changed devices, or attempt count is more than
        //ADE_MAX_ATTEMPT_FOR_DEVICE
        for(itdeque it=dq.begin(); it!=dq.end(); it++){
                if(             it->action =="change" &&
                                is_device_crypted_from_syspath(it->syspath.c_str())){
                        custom_log("[removed] change to crypt, syspath %s",it->syspath.c_str());
                        cryptedDevices.push_back(it);
                }
                else if(it->ade_attempt_count>=ADE_MAX_ATTEMPT_FOR_DEVICE){
                    cryptedDevices.push_back(it);
                    custom_log("[removed] ade attempt count %d is >= %d, syspath %s",it->ade_attempt_count,ADE_MAX_ATTEMPT_FOR_DEVICE,it->syspath.c_str());
                }
                else{
                    //do nothing
                }
        }
        //remove previously add crypted devices, which are mounted now.
        for(itdeque it=dq.begin(); it!=dq.end(); it++){
                  for(auto itd:cryptedDevices){
                          if(it==itd) continue;
                          if(it->action!="change" && it->syspath==itd->syspath){
                                  cryptedDevices.push_back(it); break;
                          }
                  }
        }
        for(auto it:cryptedDevices){
                dq.erase(it);
        }
}

void printdq(std::deque<device>&dq){
        custom_log("deque item count: %d",dq.size());
        for(auto it:dq){
                custom_log("deque item: action %s, syspath %s",it.action.c_str(), it.syspath.c_str());
        }
}

int main(int argc, char *argv[]) {

    // Command line options: -d for daemon mode
    //-l is for log path.
    int c = 0;
    int daemon_mode = 0;
    std::string log_path="";
    bool invalid_option=false;
    while ((c = getopt(argc, argv, "dl:")) != -1) {
        switch (c) {
            case 'd':
                daemon_mode = 1;
                break;
            case 'l':
                 log_path=optarg;
                 break;
            default:
                invalid_option=true;
                break;
        }
    }

    prepare_log_file(log_path);
    if(invalid_option==true){
        custom_log("Unknown option %c", c);
        exit(1);
    }
    custom_log("\n\n### Azure Disk Encryption volume notification service ###");
    custom_log("Starting udev volume notification program (%s) with %d args", argv[0], argc);
    signal(SIGINT, sigint_handler);
    custom_log("Registered SIGINT handler");

    char current_working_directory[1024];
    getcwd(current_working_directory,1024);

    if (daemon_mode) {
        custom_log("Option for switching to daemon mode provided");
        daemonize(argc, argv);
    }

    struct udev *udev;
    struct udev_monitor *mon;
    int fd;
    int ret;
    struct Node* first = NULL;

    udev = udev_new();
    if (!udev) {
        custom_log("ERROR: Can't create udev (error no=%d)\n", errno);
        exit(1);
    }

    // Set custom log function

    mon = udev_monitor_new_from_netlink(udev, "udev");
    if (!mon) {
        custom_log("ERROR: Can't create udev monitor (error no=%d)\n", errno);
        exit(1);
    }

    ret = udev_monitor_filter_add_match_subsystem_devtype(mon, "block", "partition" /*"disk"*/);
    if (ret < 0) {
        custom_log("ERROR: Can't add udev monitor filter (error no=%d)\n", errno);
        exit(1);
    }

    ret = udev_monitor_enable_receiving(mon);
    if (ret < 0) {
        custom_log("ERROR: Can't enable udev monitor receiving (error no=%d)\n", errno);
        exit(1);
    }

    fd = udev_monitor_get_fd(mon);
    if (fd < 0) {
        custom_log("ERROR: Can't get udev monitor fd (error no=%d)\n", errno);
        exit(1);
        }
    custom_log("Entering thread to check mounts");
    std::atexit([]() { thread_running_mnt = false;});
    std::thread mnt_thread(thread_proc_mnt);
    custom_log("Entering main event loop");
    time_t first_dev_node;
    first_dev_node = time(NULL);
    ade_finished  = time(NULL);
    int dev_node_count;
    std::deque<device> dq;
    while (1) {
        fd_set fds;
        struct timeval tv;
        int ret;

        FD_ZERO(&fds);
        FD_SET(fd, &fds);
        tv.tv_sec = 0;
        tv.tv_usec = 0;

        ret = select(fd+1, &fds, NULL, NULL, &tv);

        if (ret > 0 && FD_ISSET(fd, &fds)) {
            struct udev_device *dev;

            dev = udev_monitor_receive_device(mon);
            custom_log("*******************A new udev monitoring event is received!*******************");
            const char *devnode = udev_device_get_devnode(dev);
            custom_log("Device node: %s", devnode);
            const char *devtype = udev_device_get_devtype(dev);
            const char *subsystem = udev_device_get_subsystem(dev);
            custom_log("Device type: %s, Subsystem: %s",devtype,subsystem);
            const char *action = udev_device_get_action(dev);
            const char *fsType = udev_device_get_property_value(dev, "ID_FS_TYPE");
            const char *fsUsage = udev_device_get_property_value(dev, "ID_FS_USAGE");
            custom_log("Action: %s, Filesystem type: %s, Filesystem Usage: %s", action,fsType,fsUsage);
            const char *devpath = udev_device_get_devpath(dev);
            custom_log("Device path: %s", devpath);
            int is_initialized = udev_device_get_is_initialized(dev);
            custom_log("is_initialized: %d", is_initialized);
            const char* syspath = udev_device_get_syspath(dev);
            //custom_log("Syspath : %s", syspath);

            if (            action != NULL &&
                            (strcmp(action, "change") == 0 ||
                            strcmp(action, "add") == 0) &&
                            fsUsage != NULL &&
                            (strcmp(fsUsage, "filesystem") == 0||
                             strcmp(fsUsage, "crypto") == 0)){
                   if(!is_devnode_added(dq,syspath,action)){
                            custom_log("adding Device node %s in list\n",devnode);
                            addNode(dq,syspath,action);
                            if(dev_node_count ==0){
                                first_dev_node = time(NULL);
                            }
                    }
            }
            //ADE generated dev events must be removed from list.
            cleanCryptedDevFromList(dq);
            printdq(dq);
            custom_log("Processing udev monitoring event is done!\n");
            udev_device_unref(dev);
        }
        usleep(250*1000);
        dev_node_count = dq.size();
        int diff_for_ade_loop = (int)difftime(time(NULL),ade_finished);
        int diff_for_dev_nodes = dev_node_count>0?(int)difftime(time(NULL),first_dev_node):0;
        bool ade_invoked = false;
        //Logic to invoke ADE.
        if (dev_node_count >= ADE_MAX_EVENT_THRESHOLD_COUNT){
                    custom_log("dev node count %d max to trigger %d for running ADE!"
                    ,dev_node_count,ADE_MAX_EVENT_THRESHOLD_COUNT);
                    invoke_ade(current_working_directory,dq);
                    ade_invoked=true;
        }else if(diff_for_ade_loop>=ADE_PERIODIC_SCAN_SECONDS){
            custom_log("running ADE in every %d sec, last ade run was at %s, diff: %d, dev nodes in list %d"
            ,ADE_PERIODIC_SCAN_SECONDS,ctime(&ade_finished),diff_for_ade_loop,dev_node_count);
            custom_log("diff_for_ade_loop: %d, diff_for_dev_nodes: %d",diff_for_ade_loop,diff_for_dev_nodes);
            invoke_ade(current_working_directory,dq);
            ade_invoked=true;
        }else if(dev_node_count>0 && diff_for_dev_nodes>ADE_COUNT_WAIT_TIME_SEC){
            custom_log("running ADE, dev nodes in list %d, last ade run was at %s, diff: %d"
            ,dev_node_count,ctime(&first_dev_node),diff_for_dev_nodes);
            custom_log("diff_for_ade_loop: %d, diff_for_dev_nodes: %d",diff_for_ade_loop,diff_for_dev_nodes);
            invoke_ade(current_working_directory,dq);
            ade_invoked=true;
        }
        else if(ade_status!=AdeStatus::ADE_RUNNING && unencrypted_fs_mounted == true){
            custom_log("running ADE, a volume is mounted!");
            invoke_ade(current_working_directory,dq);
            ade_invoked=true;
            unencrypted_fs_mounted=false;
        }
        else{
            printf("...");
        }
        if(ade_invoked){
           first_dev_node = time(NULL);
           cleanCryptedDevFromList(dq);
        }

    }
    udev_monitor_unref(mon);
    udev_unref(udev);
    mnt_thread.join();
    return 0;
}