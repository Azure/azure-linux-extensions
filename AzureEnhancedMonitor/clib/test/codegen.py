#!/bin/env python

import re;
import os;

code_tmpl="""\
void ap_metric_{0}_{1}(ap_handler *handler, perf_counter *pc)
{{
    if(handler->err)
    {{
        return;
    }}
    find_first(handler, pc, "{2}", "{3}");
}}

"""

test_root = os.path.dirname(os.path.abspath(__file__))

if __name__ == "__main__":
    file_in = open(os.path.join(test_root, "CounterNames"), "r")
    file_out = open(os.path.join(test_root, "autocode"), "w") 
    lines = file_in.read().split("\n")
    
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

            print code_snippet
            file_out.write(code_snippet)

    file_in.close()
    file_out.close()
