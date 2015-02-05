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
#include <stdlib.h> 
#include <string.h> 

void get_cpuid(unsigned int leaf, unsigned int *cpuid)
{
    asm volatile (
        "cpuid" 
        : "=a" (cpuid[0]), "=b" (cpuid[1]), "=c" (cpuid[2]), "=d" (cpuid[3]) 
        : "a" (leaf));
}

void u32_to_char_arr(char* dest, unsigned int i)
{
    dest[0] = (char)(i       & 0xFF);
    dest[1] = (char)(i >> 8  & 0xFF);
    dest[2] = (char)(i >> 16 & 0xFF);
    dest[3] = (char)(i >> 24 & 0xFF);
}

int main()
{
    unsigned int cpuid[4];
    char vendor_id[13];

    /* Read hypervisor name*/
    memset(cpuid, 0, sizeof(unsigned int) * 4);
    memset(vendor_id, 0, sizeof(char) * 13);
    get_cpuid(0x40000000, cpuid);

    //cpuid[1~3] is hypervisor vendor id signature.
    //In hyper-v, it is:
    //
    //    0x7263694D—“Micr”
    //    0x666F736F—“osof”
    //    0x76482074—“t Hv”
    //
    u32_to_char_arr(vendor_id,     cpuid[1]);
    u32_to_char_arr(vendor_id + 4, cpuid[2]);
    u32_to_char_arr(vendor_id + 8, cpuid[3]);

    printf("%s\n", vendor_id);

    /* Read hypervisor version*/
    memset(cpuid, 0, sizeof(unsigned int) * 4);
    get_cpuid(0x40000001, cpuid);

    // cpuid[0] is hypervisor vendor-neutral interface identification.
    // 0x31237648—“Hv#1. It means the next leaf contains version info.
    if(0x31237648 != cpuid[0])
    {
        return;
    }
    memset(cpuid, 0, sizeof(unsigned int) * 4);
    get_cpuid(0x40000002, cpuid);

    //cpuid[1] is host version. 
    //The high-end 16 bit is major version, while the low-end is minor.
    printf("%d.%d\n", (cpuid[1] >> 16) & 0xFF, (cpuid[1]) & 0xFF);
}

