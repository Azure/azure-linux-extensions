SET(CMAKE_SKIP_BUILD_RPATH  FALSE)
SET(CMAKE_BUILD_WITH_INSTALL_RPATH FALSE)
# Reset rpath vars for static executable
SET(CMAKE_INSTALL_RPATH "${OMI_LIB_PATH}")
SET(CMAKE_INSTALL_RPATH_USE_LINK_PATH TRUE)

set(LINKER_FLAGS "${LINKER_FLAGS} -static-libgcc -static-libstdc++")
set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} ${LINKER_FLAGS}")

set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -pthread")
set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -pthread")

set(LDFLAGS "-rdynamic")
set(LDFLAGS "${LDFLAGS} -Wl,--wrap=memcpy") # To force using memcpy@GLIBC_2.2.5 (for old distro versions)
set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} ${LDFLAGS}")

if(NOT BUILD_NUMBER)
    execute_process(
        COMMAND date +%s
        OUTPUT_VARIABLE BUILD_NUMBER)
endif(NOT BUILD_NUMBER)
message("Build number: ${BUILD_NUMBER}")

add_definitions(-DBUILD_NUMBER=${BUILD_NUMBER})

include_directories(
    /usr/include/libxml2
    /usr/local/include
    ${OMI_INCLUDE_DIRS}
    ${CASABLANCA_INCLUDE_DIRS}
    ${STORAGE_INCLUDE_DIRS}
    ${CMAKE_SOURCE_DIR}/mdsd
    ${CMAKE_SOURCE_DIR}/mdsdinput
    ${CMAKE_SOURCE_DIR}/mdsdlog
    ${CMAKE_SOURCE_DIR}/mdsdutil
    ${CMAKE_SOURCE_DIR}/mdscommands
    ${CMAKE_SOURCE_DIR}/mdsdcfg
)

# include(/usr/local/lib/bond/bond.cmake)

link_directories(
    ${OMI_LIB_PATH}
)

if("${CMAKE_CXX_COMPILER_ID}" MATCHES "Clang")
    # Some dependency library has no static clang lib, so use shared ones.
    set(XML_LIB xml++-2.6${LIBSUFFIX})
    set(GLIBMM_LIB glibmm-2.4${LIBSUFFIX})
    set(SIGC_LIB sigc-2.0${LIBSUFFIX})
    set(BOOST_LIBS
        boost_log${LIBSUFFIX}
        boost_iostreams${LIBSUFFIX}
        boost_regex${LIBSUFFIX}
        boost_thread${LIBSUFFIX}
        boost_system${LIBSUFFIX}
    )

else()
    # For gcc, use static libs
    set(XML_LIB /usr/lib/libxml++-2.6.a)
    set(GLIBMM_LIB /usr/lib/x86_64-linux-gnu/libglibmm-2.4.a)
    set(SIGC_LIB /usr/lib/x86_64-linux-gnu/libsigc-2.0.a)
    set(BOOST_LIBS
        /usr/lib/x86_64-linux-gnu/libboost_log.a
        /usr/lib/x86_64-linux-gnu/libboost_iostreams.a
        /usr/lib/x86_64-linux-gnu/libboost_regex.a
        /usr/lib/x86_64-linux-gnu/libboost_thread.a
        /usr/lib/x86_64-linux-gnu/libboost_system.a
    )
endif()

set(COMM_LIBS
    micxx${LIBSUFFIX}
    omiclient${LIBSUFFIX}
    rt  # Required not to use clock_gettime@GLIBC_2.17
    /usr/lib/x86_64-linux-gnu/bond/libbond${LIBSUFFIX}.a
    ${LINKSTDLIB}
    ${STORAGE_LIBRARIES}
    ${CASABLANCA_LIBRARIES}
    ${XML_LIB}
    ${GLIBMM_LIB}
    /usr/lib/x86_64-linux-gnu/libglib-2.0.a
    ${SIGC_LIB}
    /usr/lib/x86_64-linux-gnu/libpcre.a
    /usr/lib/x86_64-linux-gnu/libuuid.a
    /usr/lib/x86_64-linux-gnu/libxml2.a
    /usr/lib/x86_64-linux-gnu/libz.a
    /usr/lib/x86_64-linux-gnu/liblzma.a
    ${BOOST_LIBS}
    /usr/local/lib/libssl.a
    /usr/local/lib/libcrypto.a
    dl
)

set(SOURCES
    Batch.cc
    CanonicalEntity.cc
    CfgContext.cc
    CfgCtxAccounts.cc
    CfgCtxDerived.cc
    CfgCtxEnvelope.cc
    CfgCtxError.cc
    CfgCtxEtw.cc
    CfgCtxEventAnnotations.cc
    CfgCtxEvents.cc
    CfgCtxExtensions.cc
    CfgCtxHeartBeats.cc
    CfgCtxImports.cc
    CfgCtxManagement.cc
    CfgCtxMdsdEvents.cc
    CfgCtxMonMgmt.cc
    CfgCtxOMI.cc
    CfgCtxParser.cc
    CfgCtxRoot.cc
    CfgCtxSvcBusAccts.cc
    CfgCtxSchemas.cc
    CfgCtxSources.cc
    cJSON.c
    CmdLineConverter.cc
    ConfigParser.cc
    Constants.cc
    Credentials.cc
    cryptutil.cc
    DaemonConf.cc
    DerivedEvent.cc
    Engine.cc
    EtwEvent.cc
    EventJSON.cc
    ExtensionMgmt.cc
    FileSink.cc
    IMdsSink.cc
    ITask.cc
    LADQuery.cc
    Listener.cc
    LocalSink.cc
    MdsdConfig.cc
    MdsdMetrics.cc
    mdsd.cc
    MdsEntityName.cc
    MdsSchemaMetadata.cc
    MdsValue.cc
    Memcheck.cc
    OMIQuery.cc
    OmiTask.cc
    Pipeline.cc
    PipeStages.cc
    Priority.cc
    ProtocolHandlerBase.cc
    ProtocolHandlerBond.cc
    ProtocolHandlerJSON.cc
    ProtocolListener.cc
    ProtocolListenerBond.cc
    ProtocolListenerDynamicJSON.cc
    ProtocolListenerJSON.cc
    ProtocolListenerMgr.cc
    ProtocolListenerTcpJSON.cc
    RowIndex.cc
    SaxParserBase.cc
    SchemaCache.cc
    Signals.c
    StoreType.cc
    StreamListener.cc
    Subscription.cc
    TableSchema.cc
    TermHandler.cc
    Version.cc
    XJsonBlobBlockCountsMgr.cc
    XJsonBlobRequest.cc
    XJsonBlobSink.cc
    XTableConst.cc
    XTableHelper.cc
    XTableRequest.cc
    XTableSink.cc
)

# To set source file specific compile flags, do
# set_source_files_properties(<file> PROPERTIES COMPILE_FLAGS <flag>)
# example:
# set_source_files_properties(Pipeline.cc PROPERTIES COMPILE_FLAGS -Wno-sign-compare)

# Disable warnings from azure storage API.
set_source_files_properties(
    XJsonBlobBlockCountsMgr.cc
    XJsonBlobRequest.cc
    XJsonBlobSink.cc
    XTableHelper.cc
    XTableRequest.cc
    XTableSink.cc
    PROPERTIES
    COMPILE_FLAGS "-Wno-unused-value -Wno-reorder -Wno-sign-compare"
)

set(WRAPPERS_FOR_OLD_GLIBC_SOURCES
    wrap_memcpy.c
    fdelt_chk.c
)

add_executable(
    mdsd
    ${SOURCES}
    ${WRAPPERS_FOR_OLD_GLIBC_SOURCES}
)

target_link_libraries(
    mdsd
    ${CMD_LIB_NAME}
    ${INPUT_LIB_NAME}
    ${UTIL_LIB_NAME}
    ${LOG_LIB_NAME}
    ${MDSDCFG_LIB_NAME}
    ${COMM_LIBS}
)

install(TARGETS
    mdsd
    RUNTIME DESTINATION ${CMAKE_BINARY_DIR}/release/bin
)
