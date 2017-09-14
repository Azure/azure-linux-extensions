// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "CfgCtxHeartBeats.hh"

////////////////// CfgCtxHeartBeats

subelementmap_t CfgCtxHeartBeats::_subelements = {
	{ "HeartBeat", [](CfgContext* parent) -> CfgContext* { return new CfgCtxHeartBeat(parent); } }
};

std::string CfgCtxHeartBeats::_name = "HeartBeats";

////////////////// CfgCtxHeartBeat

subelementmap_t CfgCtxHeartBeat::_subelements;

std::string CfgCtxHeartBeat::_name = "HeartBeat";
