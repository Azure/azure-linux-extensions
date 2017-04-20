#!/usr/bin/env python
#
# Azure Linux extension
#
# Copyright (c) Microsoft Corporation
# All rights reserved.
# MIT License
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the ""Software""), to deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit
# persons to whom the Software is furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the
# Software.
# THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
# WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
# OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

# Various XML templates definitions for use in constructing mdsd XML config file.

per_eh_url_tmpl = """    <EventStreamingAnnotation name="{eh_name}">
       <EventPublisher>
         <Key decryptKeyPath="{key_path}">{enc_eh_url}</Key>
       </EventPublisher>
    </EventStreamingAnnotation>
"""


top_level_tmpl_for_logging_only = """
<MonitoringManagement eventVersion="2" namespace="" timestamp="2014-12-01T20:00:00.000" version="1.0">
  <Sources>
{sources}  </Sources>

  <Events>
    <MdsdEvents>
{events}    </MdsdEvents>
  </Events>

  <EventStreamingAnnotations>
{eh_urls}  </EventStreamingAnnotations>
</MonitoringManagement>
"""


per_source_tmpl = """    <Source name="{name}" dynamic_schema="true" />
"""


per_MdsdEventSource_tmpl = """      <MdsdEventSource source="{source}">
        {routeevents}
      </MdsdEventSource>
"""


per_RouteEvent_tmpl = """
    <RouteEvent dontUsePerNDayTable="true" eventName="{event_name}" priority="High" {opt_store_type} />
"""


derived_event = """
<DerivedEvent duration="{interval}" eventName="{target}" isFullName="true" source="{source}" storeType="{type}"/>
"""


lad_query = '<LADQuery columnName="CounterName" columnValue="Value" partitionKey="" />'


obo_field = '<OboDirectPartitionField name="{name}" value="{value}" />'


entire_xml_cfg_tmpl = """
<MonitoringManagement eventVersion="2" namespace="" timestamp="2017-03-27T19:45:00.000" version="1.0">
  <Accounts>
    <Account account="" isDefault="true" key="" moniker="moniker" tableEndpoint="" />
    <SharedAccessSignature account="" isDefault="true" key="" moniker="moniker" tableEndpoint="" />
  </Accounts>

  <Management defaultRetentionInDays="90" eventVolume="">
    <Identity>
      <IdentityComponent name="DeploymentId" />
      <IdentityComponent name="Host" useComputerName="true" />
    </Identity>
    <AgentResourceUsage diskQuotaInMB="50000" />
  </Management>

  <Schemas>
  </Schemas>

  <Sources>
  </Sources>

  <Events>
    <MdsdEvents>
    </MdsdEvents>

    <OMI>
    </OMI>

    <DerivedEvents>
    </DerivedEvents>
  </Events>

  <EventStreamingAnnotations>
  </EventStreamingAnnotations>

</MonitoringManagement>
"""