// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "TableColumn.hh"

void
TableColumn::AppendXmlSchemaElement(std::string& xmlbody) const
{
	xmlbody += "<Column name=\"";
	xmlbody += _name;
	xmlbody += "\" type=\"";
	xmlbody += _mdstype;
	xmlbody += "\"></Column>";
}

