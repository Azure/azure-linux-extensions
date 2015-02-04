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
#include <azureperf.h> 


int main()
{
    run_test("./cases/positive_case");
}

int run_test(char* ap_file)
{
    int ret = 0;
    ap_handler *handler = 0;
    int i = 0;

    handler = ap_open();
    handler->ap_file = ap_file;
    ap_refresh(handler);
    if(handler->err)
    {
        ret = handler->err;
        printf("Error code:%d\n", handler->err);
    }
    printf("Found counters:%d\n", handler->len);
    ap_close(handler);
    return ret;
}
