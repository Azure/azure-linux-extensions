// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _CFGCONTEXT_HH_
#define _CFGCONTEXT_HH_

#include <string>
#include <map>
#include <functional>
#include "SaxParserBase.hh"

class CfgContext;
class MdsdConfig;

/// <summary>
/// Maps from a (permitted) subelement name to the function which returns an appropriate new context.
/// </summary>
typedef std::map<std::string, std::function<CfgContext* (CfgContext*)> > subelementmap_t;

/// <summary>
/// XML element attribute list
/// </summary>
typedef SaxParserBase::AttributeMap xmlattr_t;

/// <summary>
/// const iterator on an XML attribute list
/// </summary>
typedef SaxParserBase::AttributeMap::const_iterator xmlattr_iter_t;

/// <summary>
/// This pure virtual class is really an Interface class for all parsing context classes.
/// </summary>
class CfgContext
{
public:
	virtual ~CfgContext() {}

	/// <summary>
	/// Asks the current context to construct a child context given the name of a subelement.
	/// If the current context doesn't permit a subelement of that name, a new Error context is
	/// returned.
	/// </summary>
	CfgContext* SubContextFactory(const std::string& name);

	/// <summary>
	/// Provides attributes of the just-entered XML element to the context for the element.
	/// </summary>
	virtual void Enter(const xmlattr_t& properties) = 0;

	/// <summary>
	/// Provides the body of the current XML element to the context for the element. May be
	/// called for each chunk of characters found between subelements. By default, just
	/// accumulate chunks into the Body member variable.
	/// </summary>
	virtual void HandleBody(const std::string& body) { Body += body; }

	/// <summary>
	/// Provides the CDATA text of the current XML element to the context of the element.
	/// By default, just accumulate chunks into the CdataText member variable.
	/// Example for CDATA: <![CDATA[SomeMessage]]>
	/// </summary>
	virtual void HandleCdata(const std::string& cdata) { Body += cdata; }

	/// <summary>
	/// Invoked when the parser is leaving the element. The context should finish its work
	/// (e.g. finalize changes to the MdsdConfig object). Once this member is called, the class
	/// instance is ready to be destroyed. Base class implementation warns if the body is
	/// non-empty but otherwise does nothing.
	/// </summary>
	virtual CfgContext* Leave();

	/// <summary>Fetch the printable name for the context.</summary>
	virtual const std::string& Name() const = 0;

	/// <summary>Fetch the context map of permitted subelements.</summary>
	virtual const subelementmap_t& GetSubelementMap() const = 0;

	/// <summary>True if the parse is in "error" state</summary>
	virtual bool IsErrorContext() const { return false; }

	void INFO(const std::string& msg);
	void WARNING(const std::string& msg);
	void ERROR(const std::string& msg);
	void FATAL(const std::string& msg);

private:
	/// <summary>
	/// Disallow default constructor.
	/// </summary>
	CfgContext() : ParentContext(NULL), Config(NULL) {}	

	/// <summary>
	/// Convert a list of XML SaxParser attributes to a printable string
	/// </summary>
	/// <param name="properties">The attribute list for the element</param>
	std::string stringize_attributes(const xmlattr_t& properties);

protected:

	/// <summary>The context object for the XML element that contains this one.</summary>
	CfgContext* const ParentContext;

	// Should provide an accessor to allow derived classes to call methods through this pointer, with the
	// pointer itself remaining private.
	MdsdConfig* const Config;

	/// <summary>Accumulated body of the element</summary>
	std::string Body;

	/// <summary>
	/// Creates a context representing a particular element an XML document. Knows how to handle attributes
	/// of the element and any content (body text). Knows what sub-elements are legal.
	/// </summary>
	/// <param name="previousContext">A pointer to the parent (enveloping) context.</param>
	CfgContext(CfgContext* previousContext) : ParentContext(previousContext), Config(previousContext->Config) {}

	/// <summary>
	/// Creates a context representing the root element an XML document.
	/// </summary>
	/// <param name="previousContext">A pointer to the parent (enveloping) context.</param>
	CfgContext(MdsdConfig* config) : ParentContext(NULL), Config(config) {}

	/// <summary>
	/// Add an Info message recording entry into a new element
	/// </summary>
	/// <param name="properties">The attribute list for the element</param>
	void log_entry(const xmlattr_t& properties);

	/// <summary>
	/// Add an Info message recording a body-chunk for the current element
	/// </summary>
	/// <param name="body">The body text found within the element</param>
	void log_body(const std::string& body);

	/// <summary>
	/// Return true if the accumulated body of the element is empty or whitespace
	/// </summary>
	bool empty_or_whitespace();

	/// <summary>
	/// Add a warning message if any attributes were specified
	/// </summary>
	/// <param name="properties">The attribute list for the element</param>
	void warn_if_attributes(const xmlattr_t& properties);

	void parse_singleton_attribute(const std::string & itemname, const std::string & itemval,
		const std::string & attrname, std::string& attrval);

	void fatal_if_no_attributes(const std::string & attrname, const std::string & attrval);

	void warn_if_attribute_unexpected(const std::string & attrname)
	{
		WARNING("Ignoring unexpected <" + Name() + "> attribute \"" + attrname + "\"");
	}

	void fatal_if_impossible_subelement()
	{
		FATAL("Found <" + Name() + "> in <" + ParentContext->Name() + ">; that can't happen.");
	}

};

#endif //_CFGCONTEXT_HH_

// vim: se sw=8 :
