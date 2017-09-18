// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _TABLESCHEMA_HH_
#define _TABLESCHEMA_HH_

#include "MdsValue.hh"
#include "TableColumn.hh"
#include <vector>
#include <set>
#include <utility>
#include <string>
#include <iterator>

class TableSchema
{
public:
	TableSchema(const std::string& n) : _name(n) {}
	~TableSchema();

	enum ErrorCode {
		Ok = 0,
		NoConverter = 1,
		DupeColumn = 2,
		BadSrcType = 3,
		BadMdsType = 4
	};

	/// <summary>Add a column to this schema.</summary>
	/// <param name="n">Name of the column</param>
	/// <param name="srctype">The JSON type for the column, as the data arrives in an event</param>
	/// <param name="mdstype">The MDS type for the column in MDS</param>
	ErrorCode AddColumn(const std::string& n, const std::string& srctype, const std::string& mdstype);

	// Act kinda like a container; allow iterators on the vector of TableColumn*.
	typedef std::vector<TableColumn*>::iterator iterator;
	typedef std::vector<TableColumn*>::const_iterator const_iterator;

	iterator begin() { return _columns.begin(); }
	const_iterator begin() const { return _columns.begin(); }
	iterator end() { return _columns.end(); }
	const_iterator end() const { return _columns.end(); }

	size_t Size() const { return _columns.size(); }

	/// <summary>Push pairs of [column name, column typename] into a vector</summary>
	void PushColumnInfo(std::back_insert_iterator<std::vector<std::pair<std::string, std::string> > >) const;

	const std::string& Name() const { return _name; }

private:
	TableSchema();

	const std::string _name;
	std::vector<TableColumn*> _columns;

	static std::set<std::string> _legal_types;
	static std::set<std::string> _legal_mdstypes;
};

#endif //_TABLESCHEMA_HH_
