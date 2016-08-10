//
// Copyright 2016 Microsoft Corporation
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
//


#include <stdio.h>
#include <stdlib.h>
#include <fcntl.h>
#include <signal.h>
#include <linux/fs.h>
#include <sys/ioctl.h>


#define JUMPWITHSTATUS(x)        \
{                                \
    status = (x);                \
    if (status) goto CLEANUP;    \
}


int gThaw = 0;


void globalSignalHandler(int signum)
{
    if (signum == SIGUSR1)
    {
        gThaw = 1;
    }
}


void printUsage()
{
    printf("Usage: safefreeze TimeoutInSeconds MountPoint1 [MountPoint2 [MountPoint3 [..]]]\n");
}


int main(int argc, char *argv[])
{
    int status = EXIT_SUCCESS;

    int timeout = 0;
    int numFileSystems = 0;
    int *fileSystemDescriptors = NULL;

    int i = 0;

    if (argc < 3)
    {
        printUsage();
        JUMPWITHSTATUS(EXIT_FAILURE);
    }

    if ((timeout = atoi(argv[1])) <= 0)
    {
        printUsage();
        JUMPWITHSTATUS(EXIT_FAILURE);
    }

    numFileSystems = argc - 2;
    fileSystemDescriptors = (int *) malloc(sizeof(int) * numFileSystems);

    for (i = 0; i < numFileSystems; i++)
    {
        fileSystemDescriptors[i] = -1;
    }

    for (i = 0; i < numFileSystems; i++)
    {
        char *mountPoint = argv[i + 2];

        if ((fileSystemDescriptors[i] = open(mountPoint, O_RDONLY)) < 0)
        {
            printf("Failed to open: %s\n", mountPoint);
            JUMPWITHSTATUS(EXIT_FAILURE);
        }

        struct stat sb;

        if (fstat(fileSystemDescriptors[i], &sb) == -1)
        {
            printf("Failed to stat: %s\n", mountPoint);
            JUMPWITHSTATUS(EXIT_FAILURE);
        }

        if ((sb.st_mode & S_IFDIR) == 0)
        {
            printf("Path not a directory: %s\n", mountPoint);
            JUMPWITHSTATUS(EXIT_FAILURE);
        }
    }

    struct sigaction globalSignalAction = {0};
    globalSignalAction.sa_handler = globalSignalHandler;

    if (sigaction(SIGHUP, &globalSignalAction, NULL) ||
        sigaction(SIGINT, &globalSignalAction, NULL) ||
        sigaction(SIGQUIT, &globalSignalAction, NULL) ||
        sigaction(SIGABRT, &globalSignalAction, NULL) ||
        sigaction(SIGPIPE, &globalSignalAction, NULL) ||
        sigaction(SIGTERM, &globalSignalAction, NULL) ||
        sigaction(SIGUSR1, &globalSignalAction, NULL) ||
        sigaction(SIGUSR2, &globalSignalAction, NULL) ||
        sigaction(SIGTSTP, &globalSignalAction, NULL) ||
        sigaction(SIGTTIN, &globalSignalAction, NULL) ||
        sigaction(SIGTTOU, &globalSignalAction, NULL)
       )
    {
        printf("Failed to setup signal handlers\n");
        JUMPWITHSTATUS(EXIT_FAILURE);
    }

    for (i = 0; i < numFileSystems; i++)
    {
        char *mountPoint = argv[i + 2];
        printf("freezing the mount: %s\n", mountPoint);

        if (ioctl(fileSystemDescriptors[i], FIFREEZE, 0) != 0)
        {
            printf("Failed to FIFREEZE: %s\n", mountPoint);
            JUMPWITHSTATUS(EXIT_FAILURE);
        }
    }


    if (kill(getppid(), SIGUSR1) != 0)
    {
        printf("Failed to send FreezeCompletion to parent process\n");
        JUMPWITHSTATUS(EXIT_FAILURE);
    }

    for (i = 0; i < timeout; i++)
    {
        if (gThaw == 1 || sleep(1) != 0)
        {
            break;
        }
    }

    if (gThaw != 1)
    {
        printf("Failed to receive timely Thaw from parent process\n");
        JUMPWITHSTATUS(EXIT_FAILURE);
    }
    
CLEANUP:

    if (fileSystemDescriptors != NULL)
    {
        for (i = 0; i < numFileSystems; i++)
        {
            if (fileSystemDescriptors[i] >= 0)
            {
                char *mountPoint = argv[i + 2];
                printf("unfreezing the mount: %s\n", mountPoint);

                if (ioctl(fileSystemDescriptors[i], FITHAW, 0) != 0)
                {
                    printf("Failed to FITHAW: %s\n", mountPoint);
                    status = EXIT_FAILURE;
                }

                close(fileSystemDescriptors[i]);
                fileSystemDescriptors[i] = -1;
            }
        }
        free(fileSystemDescriptors);
        fileSystemDescriptors = NULL;
    }

    return status;
}
