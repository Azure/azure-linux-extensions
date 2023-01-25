#include <libudev.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include <time.h>
#include <errno.h>
#include <signal.h>
#include <getopt.h>
#include <sys/types.h>
#include <sys/stat.h>

#define LOG_PRIORITY 3
#define LOG_LEVEL 3
#define LOG_TO_CONSOLE 1

#define LOG_DIRETORY "/tmp"
#define LOG_FILE_TEMPLATE "%s/ade_vol_notif-%s.log"

// TODO: Make this a parameter to the program
static char log_file_path[1024];

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

    //execve(argv[0], argv, NULL);
    // char *newargv[] = { NULL };
    // execv(argv[0], newargv);
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

    if (daemon_mode) {
        daemonize(argc, argv);
    }

    struct udev *udev;
    struct udev_monitor *mon;
    int fd;
    int ret;

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


            if (action != NULL && strcmp(action, "change") == 0) {
                // Handle disk volume change event
                const char *devnode = udev_device_get_devnode(dev);
                custom_log("Device node: %s has changed. Checking if it is encrypted!", devnode);

                // TODO: Call ADE's handle sh with enable action to scan the volumes and encrypt if necessary.
                // Detect ADE path.
                // system("");
            }
            custom_log("Processing udev monitoring event is done!\n");
            udev_device_unref(dev);
        }
    }

    udev_monitor_unref(mon);
    udev_unref(udev);
    return 0;
}

