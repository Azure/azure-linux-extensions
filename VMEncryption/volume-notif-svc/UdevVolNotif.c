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
#include <sys/wait.h>
#include <sys/types.h>
#include <sys/stat.h>

#define LOG_PRIORITY 3
#define LOG_LEVEL 3
#define LOG_TO_CONSOLE 1

#define LOG_DIRETORY "/tmp"
#define LOG_FILE_TEMPLATE "%s/ade_vol_notif-%s.log"
#define ADE_EVENT_THRESHOLD 4
#define ADE_COUNT_WAIT_TIME 30
#define ADE_WAIT_TIME 900
#define ADE_NOT_STARTED "not_started";
#define ADE_FINISHED "finished";
#define ADE_RUNNING "running";

char* ade_status = ADE_NOT_STARTED;
time_t ade_finished;


// TODO: Make this a parameter to the program
static char log_file_path[1024];
void custom_log(const char *format, ...);

struct Node{
    struct Node* next;
    char* syspath;
};

struct Node* createNode(const char* syspath){
    if(syspath == NULL) return NULL;
    struct Node* tmp = (struct Node*)malloc(sizeof(struct Node*));
    tmp->next = NULL;
    tmp->syspath = (char*) malloc(sizeof(char)*strlen(syspath));
    strcpy(tmp->syspath,syspath);
    return tmp;
}

struct Node** nextNode(struct Node* node){
    if(node==NULL)return NULL;
    return &node->next;
}

void removeNode(struct Node** node){
        if(*node==NULL) {
            custom_log("node is null\n");
            return;}
        custom_log("removing syspath: %s\n", (*node)->syspath);
        struct Node* tmp = *node;
        if(tmp->next==NULL){
            *node = NULL;
            free(tmp->syspath);
            free(tmp);
        }else{
            *node=tmp->next;
            free(tmp->syspath);
            free(tmp);
        }
}

void addNode(struct Node** first, const char* ch){
        struct Node* node = createNode(ch);
        if(node==NULL) return;
        if(*first==NULL){
            *first = node;
        }else{
          node->next = *first;
          *first=node;
        }
}

int lstLength(struct Node* first){
        struct Node* tmp = first;
        int count =0;
        while(tmp!=NULL){
                tmp=tmp->next;
                count++;
        }
        return count;
}
int is_devnode_added(struct Node* first, const char* syspath){
        struct Node* tmp = first;
        while(tmp!=NULL){
                if(strcmp(syspath,tmp->syspath)==0) return 1;
                tmp=tmp->next;
        }
        return 0;
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

void prepare_log_file() {
    // Create log file with date time in UTC.
    time_t now = time(NULL);
    struct tm *timeinfo;
    timeinfo = gmtime(&now);
    char current_time[80];
    strftime(current_time, sizeof(current_time), "%Y-%m-%dT%H-%M-%S", timeinfo);
    snprintf(log_file_path, sizeof(log_file_path), LOG_FILE_TEMPLATE, LOG_DIRETORY, current_time);
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

void invoke_ade(const char* path){
    ade_status = ADE_RUNNING;
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
            execl(          "daemon_delay.sh",
                            "daemon_delay.sh",
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
    ade_status = ADE_FINISHED;
    ade_finished = time(NULL);
}

int is_device_crypted_from_syspath(const char* syspath){
        struct udev *udev;
        int ret = 0;
        udev = udev_new();
        struct udev_device* dev = udev_device_new_from_syspath(udev,syspath);
        const char* fs_usage = udev_device_get_property_value(dev,"ID_FS_USAGE");
        custom_log("get_dev_fsUsage_from_syspath: syspath %s usage status is %s",syspath, fs_usage);
        if(fs_usage!=NULL && strcmp(fs_usage,"crypto")==0) ret = 1;
        udev_device_unref(dev);
        return ret;
}
void cleanCryptedDevFromList(struct Node** first){
        struct Node** tmp = first;
        while(*tmp!=NULL){
                struct Node** rNode = tmp ;
                tmp =&((*tmp)->next);
                if(is_device_crypted_from_syspath((*rNode)->syspath)){
                        removeNode(rNode);
                }
        }
}

int main(int argc, char *argv[]) {

    prepare_log_file();

    custom_log("\n\n### Azure Disk Encryption volume notification service ###");
    custom_log("Starting udev volume notification program (%s) with %d args", argv[0], argc);
    signal(SIGINT, sigint_handler);
    custom_log("Registered SIGINT handler");

    // Command line options: -d for daemon mode
    int c = 0;
    int daemon_mode = 0;
    while ((c = getopt(argc, argv, "d")) != -1) {
        switch (c) {
            case 'd':
                custom_log("Option for switching to daemon mode provided");
                daemon_mode = 1;
                break;
            default:
                custom_log("Unknown option %c", c);
                exit(1);
        }
    }

    char current_working_directory[1024];
    custom_log("current working directory %s\n",getcwd(current_working_directory,1024));

    if (daemon_mode) {
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
    custom_log("Entering main event loop");
    time_t first_dev_node;
    first_dev_node = time(NULL);
    ade_finished  = time(NULL);
    int dev_node_count;
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
            custom_log("A new udev monitoring event is received!");

            const char *action = udev_device_get_action(dev);
                        custom_log("Action: %s", action);
            const char *devtype = udev_device_get_devtype(dev);
            custom_log("Device type: %s", devtype);
            const char *subsystem = udev_device_get_subsystem(dev);
            custom_log("Subsystem: %s", subsystem);
            const char *devpath = udev_device_get_devpath(dev);
            custom_log("Device path: %s", devpath);
            const char *devnode = udev_device_get_devnode(dev);
            custom_log("Device node: %s", devnode);
            int is_initialized = udev_device_get_is_initialized(dev);
            custom_log("is_initialized: %d", is_initialized);
            const char *fsType = udev_device_get_property_value(dev, "ID_FS_TYPE");
            custom_log("Filesystem type: %s", fsType);
            const char *fsUsage = udev_device_get_property_value(dev, "ID_FS_USAGE");
            custom_log("Filesystem Usage: %s", fsUsage);
            const char* syspath = udev_device_get_syspath(dev);
            custom_log("Syspath : %s", syspath);

            if (            action != NULL &&
                            strcmp(action, "change") == 0 &&
                            fsUsage != NULL &&
                            strcmp(fsUsage, "filesystem") == 0){
                    if(is_devnode_added(first,syspath)==0){
                            custom_log("adding Device node %s in list\n",devnode);
                            addNode(&first,syspath);
                            if(dev_node_count ==0){
                                first_dev_node = time(NULL);
                            }
                    }
            }
            //ADE generated dev events must be removed from list.
            cleanCryptedDevFromList(&first);
            
            custom_log("Processing udev monitoring event is done!\n");
            udev_device_unref(dev);
        }
        usleep(250*1000);
        dev_node_count = lstLength(first);
        int diff_for_ade_loop = (int)difftime(time(NULL),ade_finished);
        int diff_for_dev_nodes = dev_node_count>0?(int)difftime(time(NULL),first_dev_node):0;
        //Logic to invoke ADE.
        if (dev_node_count >= ADE_EVENT_THRESHOLD){
                    custom_log("dev node count %d max to trigger %d for running ADE!"
                    ,dev_node_count,ADE_EVENT_THRESHOLD);
                    invoke_ade(current_working_directory);
        }else if(diff_for_ade_loop>=ADE_WAIT_TIME){
            custom_log("running ADE in every %d sec, last ade run was at %s, diff: %d, dev nodes in list %d"
            ,ADE_WAIT_TIME,ctime(&ade_finished),diff_for_ade_loop,dev_node_count);
            custom_log("diff_for_ade_loop: %d, diff_for_dev_nodes: %d",diff_for_ade_loop,diff_for_dev_nodes);
            invoke_ade(current_working_directory);
        }else if(dev_node_count>0 && diff_for_dev_nodes>ADE_COUNT_WAIT_TIME){
            custom_log("running ADE, dev nodes in list %d, last ade run was at %s, diff: %d"
            ,dev_node_count,ctime(&first_dev_node),diff_for_dev_nodes);
            custom_log("diff_for_ade_loop: %d, diff_for_dev_nodes: %d",diff_for_ade_loop,diff_for_dev_nodes);
            invoke_ade(current_working_directory);
        }else{
            printf("...");
        }
    }
    udev_monitor_unref(mon);
    udev_unref(udev);
    return 0;
}