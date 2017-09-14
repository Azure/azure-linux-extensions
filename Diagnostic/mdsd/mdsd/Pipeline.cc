// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "Pipeline.hh"

PipeStage::PipeStage()
  :  _next(nullptr)
{
}

PipeStage::~PipeStage()
{
	if (_next) {
		delete _next;
		_next = nullptr;
	}
}

void
PipeStage::AddSuccessor(PipeStage *next)
{
	_next = next;
}

void
PipeStage::Start(const MdsTime QIBase)
{
	if (_next) {
		_next->Start(QIBase);
	}
}

void
PipeStage::Process(CanonicalEntity *item)
{
	if (item != nullptr) {
		if (_next) {
			_next->Process(item);
		} else {
			// Drop on floor; leak the memory, if any.
		}
	}
}

void
PipeStage::Done()
{
	if (_next) {
		_next->Done();
	}
}

// vim: se ai sw=8 :
