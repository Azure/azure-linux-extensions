// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _MDSDMETRICS_HH_
#define _MDSDMETRICS_HH_

#include <map>
#include <unordered_set>
#include <mutex>
#include <string>

#ifdef DOING_MEMCHECK
#define QUITABORT if (_allFree) return
#else
#define QUITABORT
#endif

class MdsdMetrics
{
public:
	static MdsdMetrics &GetInstance() { if (_instance == nullptr) { std::lock_guard<std::mutex> lock(_setLock);
					       _instance = new MdsdMetrics(); _instances.insert(_instance); } return *_instance; }

	static void Count(const std::string &metric) { QUITABORT; GetInstance().CountThis(metric); }
	static void Count(const std::string &metric, unsigned long long delta) { QUITABORT; GetInstance().CountThis(metric, delta); }
	void CountThis(const std::string &metric) { QUITABORT; _metrics[metric]++; }
	void CountThis(const std::string &metric, unsigned long long delta) { QUITABORT; _metrics[metric] += delta; }

	static std::map<std::string, unsigned long long> AggregateAll();
	static unsigned long long AggregateMetric(const std::string &metric);

private:
	// One instance in each thread; that makes access within a thread lock-free
	static thread_local MdsdMetrics * _instance;

	// One global list of all per-thread instances...
	static std::unordered_set<MdsdMetrics *> _instances;

	// One lock protects the global list
	static std::mutex _setLock;

	std::map<std::string, unsigned long long> _metrics;

#ifdef DOING_MEMCHECK
public:
	void ClearMetrics();
	static bool _allFree;
private:
#endif

	MdsdMetrics() {}
};

#endif // _MDSDMETRICS_HH_
// vim: se sw=8 :
