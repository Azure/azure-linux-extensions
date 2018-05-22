set(SOURCES
    Logger.cc
    Trace.cc
)

add_library(${LOG_LIB_NAME} STATIC ${SOURCES})

install(TARGETS ${LOG_LIB_NAME}
    ARCHIVE DESTINATION ${CMAKE_BINARY_DIR}/release/lib
)
