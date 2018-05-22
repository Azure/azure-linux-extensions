// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _PIPELINE_HH_
#define _PIPELINE_HH_

#include "MdsTime.hh"
#include <string>

class CanonicalEntity;

// You must override Name()
// If you override Start() you must finish by calling PipeStage::Start(QIbase)
// If you override Process() and want to pass an item down the pipe, use PipeStage::Process(item)
// If you override Done() you may call PipeStage::Process(item) and must finish by calling PipeStage::Done()

class PipeStage
{
public:
	virtual ~PipeStage();

	virtual void AddSuccessor(PipeStage *next);
	virtual void Start(const MdsTime QIbase);
	virtual void Process(CanonicalEntity *);
	virtual const std::string& Name() const = 0;
	virtual void Done();

protected:
	PipeStage();

private:
	PipeStage *_next;
};
	





#endif // _PIPELINE_HH_
