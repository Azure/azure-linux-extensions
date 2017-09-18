// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _POOLMGMT_HH_
#define _POOLMGMT_HH_

#include <string>
#include <unordered_set>
#include <boost/pool/pool_alloc.hpp>
#include <iostream>


class PoolMgmt
{
public:
	typedef std::basic_string<char, std::char_traits<char>, boost::fast_pool_allocator<char>> PoolString;

	struct PoolStringHasher
  	{
      	std::size_t operator()(const PoolString& k) const
      	{
         	size_t h = std::hash<std::string>()(k.data());
         	return h;
      	}
  	};

	struct PoolStringEqualTo
	{
	    bool operator()(const PoolString& p1, const PoolString& p2) const 
	    {
	        return (0 == std::strcmp(p1.data(), p2.data()));
	    }
	};  	

	// This will release all memory blocks that aren’t used at the moment.
	// The memory will be returned to OS.
	static void ReleaseMemory()
	{
		boost::singleton_pool<boost::fast_pool_allocator_tag, sizeof(char)>::release_memory();
		boost::singleton_pool<boost::fast_pool_allocator_tag, sizeof(int)>::release_memory();
		boost::singleton_pool<boost::fast_pool_allocator_tag, sizeof(PoolString)>::release_memory();
	}

	// This will release all memory blocks including those currently used. 
	// The memory will be returned to OS.
	static void PurgeMemory()
	{
		boost::singleton_pool<boost::fast_pool_allocator_tag, sizeof(char)>::purge_memory();
		boost::singleton_pool<boost::fast_pool_allocator_tag, sizeof(int)>::purge_memory();
		boost::singleton_pool<boost::fast_pool_allocator_tag, sizeof(PoolString)>::purge_memory();		
	}
};

typedef std::unordered_set<PoolMgmt::PoolString, PoolMgmt::PoolStringHasher, PoolMgmt::PoolStringEqualTo, boost::fast_pool_allocator<PoolMgmt::PoolString>> PoolStringUnorderedSet;


#endif

// vim: se sw=8 :
