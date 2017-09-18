// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "XTableConst.hh"

unsigned int XTableConstants::_backoffBaseTime = 10;
unsigned int XTableConstants::_backoffLimit = 3;

int XTableConstants::_sdkRetryPolicyInterval = 3;
int XTableConstants::_sdkRetryPolicyLimit = 5;
int XTableConstants::_initialOpTimeout = 30;
int XTableConstants::_defaultOpTimeout = 30;
