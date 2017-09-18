// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _TABLECOLUMN_HH_
#define _TABLECOLUMN_HH_

#include "MdsValue.hh"

class TableColumn
{
public:
	TableColumn(const std::string& n, const std::string& t, typeconverter_t& c)
		: _name(n), _mdstype(t), _converter(c) {}
	~TableColumn() {}
	const std::string& Name() const { return _name; }
	const std::string& MdsType() const { return _mdstype; }
	
	/// <summary>Append to the body the MDS XML "schema" definition element for this column</summary>
	/// <param name="xmlbody">The XML body to which the generated element should be appended</param>
	void AppendXmlSchemaElement(std::string& xmlbody) const;

	/// <summary>Convert a cJSON object to the configured MDS type</summary>
	/// <param name="in">The cJSON entity to be converted</param>
	/// <returns>Pointer to a newly-allocated MdsValue. Returns 0 if the conversion failed.</returns>
	MdsValue* Convert(cJSON * in) const { return _converter(in); }
private:
	TableColumn();

	const std::string _name;
	const std::string _mdstype;
	const typeconverter_t _converter;
};

#endif //_TABLECOLUMN_HH_

// vim: se sw=8 :
