// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "Version.hh"
#include <string>

#define QUOTE(x) #x
#define VAL(x) QUOTE(x)

#define STATIC_VER VAL(MAJOR) "." VAL(MINOR) "." VAL(PATCH) "+" VAL(BUILD_NUMBER)

namespace Version
{
const std::string Version(STATIC_VER);
}
// vim: se sw=8
