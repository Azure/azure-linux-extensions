include_directories(
    ${CMAKE_SOURCE_DIR}/mdsd
    ${CMAKE_SOURCE_DIR}/mdsdlog
)

set(SOURCES
    EventPubCfg.cc
    MdsdEventCfg.cc
)

# static lib only
add_library(${MDSDCFG_LIB_NAME} STATIC ${SOURCES})

install(TARGETS
        ${MDSDCFG_LIB_NAME}
        ARCHIVE DESTINATION ${CMAKE_BINARY_DIR}/release/lib
)
