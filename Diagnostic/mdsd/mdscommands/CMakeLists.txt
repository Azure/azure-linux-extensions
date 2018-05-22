set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -pthread")

include_directories(
    ${CASABLANCA_INCLUDE_DIRS}
    ${STORAGE_INCLUDE_DIRS}
    /usr/include/libxml2
    ${CMAKE_SOURCE_DIR}/mdsd
    ${CMAKE_SOURCE_DIR}/mdsdlog
    ${CMAKE_SOURCE_DIR}/mdsdutil
)

set(SOURCES
    BodyOnlyXmlParser.cc
    CmdListXmlParser.cc
    CmdXmlCommon.cc
    CmdXmlElement.cc
    CmdXmlParser.cc
    ConfigUpdateCmd.cc
    DirectoryIter.cc
    EventData.cc
    EventEntry.cc
    EventHubCmd.cc
    EventHubPublisher.cc
    EventHubType.cc
    EventHubUploader.cc
    EventHubUploaderId.cc
    EventHubUploaderMgr.cc
    EventPersistMgr.cc
    MdsBlobReader.cc
    MdsException.cc
    PersistFiles.cc
    PublisherStatus.cc
    ${CMAKE_SOURCE_DIR}/mdsd/SaxParserBase.cc
)

# Disable warning from CPPREST
set_source_files_properties(PersistFiles.cc PROPERTIES COMPILE_FLAGS -Wno-sign-compare)

# Disable warnings from azure storage API.
set_source_files_properties(
    MdsBlobReader.cc
    EventHubCmd.cc
    PROPERTIES
    COMPILE_FLAGS "-Wno-unused-value -Wno-reorder"
)

add_library(${CMD_LIB_NAME} STATIC ${SOURCES})

install(TARGETS ${CMD_LIB_NAME}
    ARCHIVE DESTINATION ${CMAKE_BINARY_DIR}/release/lib
)
