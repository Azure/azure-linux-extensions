cmake_minimum_required(VERSION 2.6)
project(mdsd)

set(CMAKE_MODULE_PATH ${CMAKE_MODULE_PATH} "${CMAKE_SOURCE_DIR}/cmake/Modules/")

# Platform (not compiler) specific settings
if(UNIX) # This includes Linux
    message("Build for Unix/Linux OS")
else()
  	message("-- Unsupported Build Platform.")
endif()

# Compiler (not platform) specific settings
if("${CMAKE_CXX_COMPILER_ID}" MATCHES "Clang")
    message("-- Setting clang options")
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -stdlib=libc++")
    set(LINKSTDLIB "c++")
    set(LIBSUFFIX "-clang")
    set(WARNINGS "${WARNINGS} -Wno-deprecated-register")
elseif("${CMAKE_CXX_COMPILER_ID}" MATCHES "GNU")
    message("-- Setting gcc options")
    set(WARNINGS "${WARNINGS} -Wno-unused-local-typedefs")
else()
  	message("-- Unknown compiler, success is doubtful.")
endif()

# To turn off the option from cmdline, run: cmake -DBUILD_TESTS=OFF ...
option(BUILD_TESTS "Build tests." ON)
# To add code coverage build options
option(BUILD_COV "Build with code coverage." OFF)

set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++11")

# Common flags for both C and C++
set(COMM_FLAGS "${COMM_FLAGS} -fstack-protector-all")
set(COMM_FLAGS "${COMM_FLAGS} -fPIC")
set(COMM_FLAGS "${COMM_FLAGS} -D_FORTIFY_SOURCE=2")
set(COMM_FLAGS "${COMM_FLAGS} -ffunction-sections")

if(BUILD_COV)
set(COMM_FLAGS "${COMM_FLAGS} -fprofile-arcs")
set(COMM_FLAGS "${COMM_FLAGS} -ftest-coverage")
endif()

set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} ${COMM_FLAGS}")
set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} ${COMM_FLAGS}")

set(WARNINGS "${WARNINGS} -Wall")
set(WARNINGS "${WARNINGS} -Wextra")

set(WARNINGS "${WARNINGS} -Wno-unknown-pragmas")
set(WARNINGS "${WARNINGS} -Wno-unused-parameter")

set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} ${WARNINGS}")

set(CMAKE_CXX_FLAGS_DEBUG "${CMAKE_CXX_FLAGS_DEBUG} -ggdb")
set(CMAKE_C_FLAGS_DEBUG "${CMAKE_CXX_FLAGS_DEBUG} -ggdb")

set(LINKER_FLAGS "-Wl,-z,relro -Wl,-z,now")
set(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} ${LINKER_FLAGS}")
set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} ${LINKER_FLAGS}")

# Build static library only
option(BUILD_SHARED_LIBS "Build shared Libraries." OFF)

set(OMI_INCLUDE_DIRS
    /usr/include/omi
    /usr/include/omi/common
    /usr/include/omi/output/include
    /usr/include/omi/micxx
)
set(OMI_LIB_PATH "/opt/omi/lib")

set(CASABLANCA_INCLUDE_DIRS "/usr/include/cpprest")
set(CASABLANCA_LIBRARIES "/usr/lib/x86_64-linux-gnu/libcpprest${LIBSUFFIX}.a")

set(STORAGE_INCLUDE_DIRS "/usr/include/azurestorage")
set(STORAGE_LIBRARIES "/usr/lib/x86_64-linux-gnu/libazurestorage${LIBSUFFIX}.a")

set(MDSD_LIB_NAME mdsd-lib${LIBSUFFIX})
set(LOG_LIB_NAME mdsdlog${LIBSUFFIX})
set(UTIL_LIB_NAME mdsdutil${LIBSUFFIX})
set(CMD_LIB_NAME mdscommands${LIBSUFFIX})
set(INPUT_LIB_NAME mdsdinput${LIBSUFFIX})
set(MDSDCFG_LIB_NAME mdsdcfg${LIBSUFFIX})
set(MDSREST_LIB_NAME mdsrest${LIBSUFFIX})

# Set rpath for all executables including mdsd, tests, etc
SET(CMAKE_SKIP_BUILD_RPATH  FALSE)
SET(CMAKE_BUILD_WITH_INSTALL_RPATH FALSE)
SET(CMAKE_INSTALL_RPATH_USE_LINK_PATH TRUE)

add_subdirectory(mdsdlog)
add_subdirectory(mdsdutil)
add_subdirectory(mdscommands)
add_subdirectory(mdsdinput)
add_subdirectory(mdsdcfg)
add_subdirectory(mdsrest)
add_subdirectory(mdsd)
