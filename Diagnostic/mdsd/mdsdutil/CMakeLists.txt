set(SOURCES
    AzureUtility.cc
    Crypto.cc
    HttpProxySetup.cc
    MdsTime.cc
    OpensslCert.cc
    OpensslCertStore.cc
    Utility.cc
)

# Disable warnings from azure storage API.
set_source_files_properties(
    AzureUtility.cc
    HttpProxySetup.cc
    PROPERTIES
    COMPILE_FLAGS "-Wno-unused-value -Wno-reorder"
)

include_directories(
    ${STORAGE_INCLUDE_DIRS}
    ${CASABLANCA_INCLUDE_DIRS}
    ${OMI_INCLUDE_DIRS}
    ${CMAKE_SOURCE_DIR}/mdsd
    ${CMAKE_SOURCE_DIR}/mdsdlog
)

add_library(${UTIL_LIB_NAME} STATIC ${SOURCES})

install(TARGETS ${UTIL_LIB_NAME}
    ARCHIVE DESTINATION ${CMAKE_BINARY_DIR}/release/lib
)
