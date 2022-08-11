cmake_minimum_required(VERSION 3.4.0 FATAL_ERROR)

SET(TARGETNAME "LinuxEncryptionCompliance")

find_package(Dsc CONFIG QUIET)

if (MSVC) # Windows only
    find_package(cpprestsdk REQUIRED)
    find_package(Boost COMPONENTS program_options)
    # The BUILD_WINDOWS macro breaks the ccpprestsdk headers. The macro is set globally in
    # desiredstateconfiguration\tools\DscConfig.cmake; we undefine it for this project.
    SET(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} /UBUILD_WINDOWS")

    # Help cmake find the correct configuration based on build type if multiple
    # configurations are available in an imported target.
    set_target_properties(cpprestsdk::cpprest PROPERTIES
        MAP_IMPORTED_CONFIG_DEBUG DEBUG
        MAP_IMPORTED_CONFIG_MINSIZEREL RELEASE
        MAP_IMPORTED_CONFIG_RELWITHDEBINFO RELEASE
        MAP_IMPORTED_CONFIG_RELEASE RELEASE
    )
    include_directories(${Boost_INCLUDE_DIRS})
    SET(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} /MP")
    SET(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} /MP")
    SET (NO_IMPORT_LIB 1 )
    add_definitions( /wd4311 /wd4302 /wd4101 /wd4267)
else () # Linux only
    include_directories(
        ${OMI_ROOT}
        ${OMI_ROOT}/common
    )
endif()

# Common included directories
include_directories(
    ${DSC_ROOT}/common/inc
    ${ADMIN_INC}/nits/base
    ${ADMIN_INC}
    ${PAL_INC}
    ${MOF_CODEC_INC}
    ${WINOMI_ROOT}
)

file(GLOB SOURCES   ${CMAKE_CURRENT_SOURCE_DIR}/LinuxEncryptionCompliance.cpp
                    ${CMAKE_CURRENT_SOURCE_DIR}/module.c
                    ${CMAKE_CURRENT_SOURCE_DIR}/schema.c
                    )

add_internal_library(${TARGETNAME} SHARED ${SOURCES})

if (MSVC) # Windows only
    target_link_libraries(${TARGETNAME}
        ${Boost_LIBRARIES}
        pal.lib
        mi.lib
        ntdll.lib
        miutils.lib
        )
else () # Linux only
    target_link_libraries(${TARGETNAME}
        boost_system
        boost_filesystem
        mi
    )
endif ()
