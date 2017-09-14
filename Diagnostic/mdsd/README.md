# mdsd agent

The mdsd agent  is the workhorse binary for the Linux Diagnostic Extension. The LAD extension constructs an mdsd configuration file based on the LAD configuration.

## Dependencies

The Dockerfile defines an environment sufficient to build the mdsd binary. Most dependencies are satisfied by the Ubuntu "trusty" repositories. The exceptions are for open-source components released by Microsoft. These components are available in source form from github. For convenience, Microsoft has made installable .deb packages available in a public "azurecore" repository, which the Dockerfile references. These components are:

- [CPPrest, a.k.a. "Casablanca"](https://github.com/Microsoft/cpprestsdk)
- [Azure Storage SDK](https://github.com/Azure/azure-storage-cpp)
- [Microsoft bond](https://github.com/Microsoft/bond)
- [Open Management Infrastructure (OMI)](https://github.com/Microsoft/omi)

## Building the program

Run `buildcmake.sh` with the appropriate options. This will build all the necessary Makefiles, then build the program, then construct .deb and .rpm packages containing the built binary. For maximum portability across distros, the mdsd binary is built to use static libraries whenever possible. Build artifacts are dropped under `builddir` (which is symlinked to the actual directory hierarchy, which will differ based on the choice of debug vs optimized build). The release packages appear under the `lad-mdsd` directory.

## Future direction

Over time, the capabilities of this monolithic binary are likely be broken out into fluentd plug-ins. This will significantly reduce the amount of code involved and will enable  more flexible growth of the LAD extension.
