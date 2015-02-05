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

#include <stdio.h>
#include <string.h>
#include <azureperf.h> 

int main()
{
    run_test("./test/cases/positive_case");
}

int run_test(char* ap_file)
{
    int ret = 0;
    ap_handler *handler = 0;
    int i = 0;
    perf_counter pc;

    handler = ap_open();
    handler->ap_file = ap_file;
    ap_refresh(handler);
    if(handler->err)
    {
        ret = handler->err;
        printf("Error code:%d\n", handler->err);
        goto EXIT;
    }
    printf("Found counters:%d\n", handler->len);
    for(; i < handler->len; i++)
    {
        pc = handler->buf[i];
        printf("%d: %s\t%s\t",i , pc.type_name, pc.property_name);
        switch(pc.counter_typer)
        {
            case PERF_COUNTER_TYPE_INT:
                printf("%d\n", pc.val_int);
                break;
            case PERF_COUNTER_TYPE_LARGE:
                printf("%Ld\n", pc.val_large);
                break;
            case PERF_COUNTER_TYPE_DOUBLE:
                printf("%lf\n", pc.val_double);
                break;
            case PERF_COUNTER_TYPE_STRING:
            default:
                printf("%s\n", pc.val_str);
                break;
        }
        memset(&pc, 0 , sizeof(perf_counter));
    }
    ap_metric_config_cloud_provider(handler, &pc, 1);
    printf(">>%s\t%s\t%s\n", pc.type_name, pc.property_name, pc.val_str);

EXIT:
    ap_close(handler);
    return ret;
}
