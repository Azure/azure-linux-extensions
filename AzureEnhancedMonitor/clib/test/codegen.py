#!/usr/bin/env python
#
# Copyright 2014 Microsoft Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import re
import os

code_start="""\
//
// Copyright 2014 Microsoft Corporation
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
//

//
// This file is auto-generated, don't modify it directly.
//

#include <stdlib.h> 
#include <azureperf.h> 

"""

code_tmpl="""\
int ap_metric_{0}_{1}(ap_handler *handler, perf_counter *pc, size_t size)
{{
    if(handler->err)
    {{
        return 0;
    }}
    return get_metric(handler, pc, "{2}", "{3}", size);
}}

"""

head_tmpl="""\
//{0}\{1}
extern int ap_metric_{2}_{3}(ap_handler *handler, perf_counter *pc, size_t size);

"""

test_root = os.path.dirname(os.path.abspath(__file__))

if __name__ == "__main__":

    with open(os.path.join(test_root, "counter_names"), "r") as file_in, \
         open(os.path.join(test_root, "../src/apmetric.c"), "w") as file_out, \
         open(os.path.join(test_root, "../build/metric_def"), "w") as head_out:

        lines = file_in.read().split("\n")
        
        file_out.write(code_start)
        for line in lines:
            match = re.match("([^;]*);([^;]*);([^;]*)", line)
            if match is not None:
                type_name = match.group(1)
                prop_name = match.group(2)
                short_name = match.group(3)
                short_name = short_name.lower()
                short_name = short_name.replace(" ", "_")
                short_name = short_name.replace("-", "_")
                code_snippet = code_tmpl.format(type_name.lower(),
                                                short_name,
                                                type_name,
                                                prop_name)
                file_out.write(code_snippet)
                head_snippet = head_tmpl.format(type_name,
                                                prop_name,
                                                type_name.lower(),
                                                short_name)
                head_out.write(head_snippet)
                print("printf(\">>>>ap_metric_{0}_{1}\\n\");".format(type_name, short_name))
                print("ap_metric_{0}_{1}(handler, &pc, 1);".format(type_name, short_name))
                print("print_counter(&pc);")


