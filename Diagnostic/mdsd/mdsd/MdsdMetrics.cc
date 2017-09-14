// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "MdsdMetrics.hh"

thread_local MdsdMetrics *MdsdMetrics::_instance = nullptr;

std::unordered_set<MdsdMetrics *> MdsdMetrics::_instances;

std::mutex MdsdMetrics::_setLock;

std::map<std::string, unsigned long long>
MdsdMetrics::AggregateAll()
{
	std::map<std::string, unsigned long long> totals;

	for (const MdsdMetrics * pinstance : _instances) {
		for (const auto & item : pinstance->_metrics) {
			totals[item.first] += item.second;
		}
	}

	return totals;
}

unsigned long long
MdsdMetrics::AggregateMetric(const std::string &metric)
{
	unsigned long long total = 0;

	for (const MdsdMetrics * pinstance : _instances) {
		auto & inst_map = pinstance->_metrics;
		auto iter = inst_map.find(metric);
		if (iter != inst_map.end()) {
		    total += iter->second;
		}
	}

	return total;
}

#ifdef DOING_MEMCHECK
bool MdsdMetrics::_allFree = false;

void
MdsdMetrics::ClearMetrics()
{
	std::lock_guard<std::mutex> lock(_setLock);
	_allFree = true;
	for (MdsdMetrics *item : _instances) {
	    delete item;
	}
	_instances.clear();
}

#endif

// vim: se sw=8 :
