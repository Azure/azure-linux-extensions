set(SOURCES
    mdsd_input_types.cpp
    mdsd_input_apply.cpp
    MdsdInputSchemaCache.cpp
    MdsdInputMessageBuilder.cpp
    MdsdInputMessageIO.cpp
)

add_library(${INPUT_LIB_NAME} STATIC ${SOURCES})

install(TARGETS ${INPUT_LIB_NAME}
    ARCHIVE DESTINATION ${CMAKE_BINARY_DIR}/release/lib
)
