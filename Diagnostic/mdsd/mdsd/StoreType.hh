// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _STORETYPE_HH_
#define _STORETYPE_HH_

#include <string>

namespace StoreType {

enum Type { None, XTable, Bond, XJsonBlob, Local, File };

StoreType::Type from_string(const std::string &);

size_t max_name_length(StoreType::Type t);

bool DoSchemaGeneration(StoreType::Type storetype);

bool DoAddIdentityColumns(StoreType::Type storetype);

};

#endif // _STORETYPE_HH_
