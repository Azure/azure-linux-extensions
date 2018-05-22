// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "TableSchema.hh"
#include "TableColumn.hh"
#include "Engine.hh"
#include <functional>
#include <string>

TableSchema::~TableSchema()
{
	for (TableColumn * tblcol : _columns) {
		delete tblcol;
	}
}

TableSchema::ErrorCode
TableSchema::AddColumn(const std::string& name, const std::string& srctype, const std::string& mdstype)
{
	if (! _legal_types.count(srctype)) return BadSrcType;
	if (! _legal_mdstypes.count(mdstype)) return BadMdsType;

	for (TableColumn * tblcol : _columns) {
		if (tblcol->Name() == name) return DupeColumn;
	}

	typeconverter_t converter;
	if (! Engine::GetEngine()->GetConverter(srctype, mdstype, converter)) {
		return NoConverter;
	}

	auto newcolumn = new TableColumn(name, mdstype, converter);
	_columns.push_back(newcolumn);
	return Ok;
}

void
TableSchema::PushColumnInfo(std::back_insert_iterator<std::vector<std::pair<std::string, std::string> > > inserter)
const
{
	for (const auto & tblcol : _columns) {
		*(inserter++) = std::make_pair(tblcol->Name(), tblcol->MdsType());
	}
}

std::set<std::string> TableSchema::_legal_types = {
	"bool",
	"int",
	"str",
	"double",
	"int-timet",
	"double-timet",
	"str-rfc3339",
	"str-rfc3194"
};

std::set<std::string> TableSchema::_legal_mdstypes = {
	"mt:bool",
	"mt:wstr",
	"mt:float64",
	"mt:int32",
	"mt:int64",
	"mt:utc"
};

// vim: se sw=8 :
