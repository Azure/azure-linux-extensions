include_directories(
    ${CMAKE_SOURCE_DIR}/mdsdlog
    ${CMAKE_SOURCE_DIR}/mdsdutil
    ${CASABLANCA_INCLUDE_DIRS}
    ${STORAGE_INCLUDE_DIRS}
)

set(SOURCES
    GcsJsonData.cc
    GcsJsonParser.cc
    GcsServiceInfo.cc
    GcsUtil.cc
    MdsRest.cc
)

# static lib only
add_library(${MDSREST_LIB_NAME} STATIC ${SOURCES})

install(TARGETS
        ${MDSREST_LIB_NAME}
        ARCHIVE DESTINATION ${CMAKE_BINARY_DIR}/release/lib
)
