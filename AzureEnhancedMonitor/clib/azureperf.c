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
#include <errno.h>
#include <azureperf.h> 

#define INTMIN(X, Y) (((X) < (Y)) ? (X) : (Y))
#define INTMAX(X, Y) (((X) > (Y)) ? (X) : (Y))

#define MATCH_SUCCESS       (1)
#define MATCH_FAILED        (0)
#define STRICT_MATCH        (1)
#define NON_STRICT_MATCH    (0)

static char FIELD_SEPRATOR = ';';
static char DEFAULT_AP_FILE[] = "/var/lib/AzureEnhancedMonitor/PerfCounters";

ap_handler* ap_open()
{
    ap_handler *handler = malloc(sizeof(ap_handler));
    handler->ap_file = DEFAULT_AP_FILE;
    memset(handler, 0, sizeof(ap_handler));
    return handler;
}

void ap_close(ap_handler *handler)
{
    free(handler);
}

int read_sperator(ap_handler *handler, FILE *fp, int strict)
{
    int c;
    c = fgetc(fp);
    while(strict == NON_STRICT_MATCH && c != EOF && c != FIELD_SEPRATOR)
    {
        c = fgetc(fp);
    }
    if(c != FIELD_SEPRATOR)
    {
        handler->err = AP_ERR_BAD_FORMAT; 
        return MATCH_FAILED;
    }
    else
    {
        return MATCH_SUCCESS;
    }
}

int read_int(ap_handler* handler, FILE *fp, int *val)
{
    int ret = EOF;
    ret = fscanf(fp, "%d", val);
    if(ret != 1)
    {
        handler->err =  AP_ERR_BAD_FORMAT;
        return MATCH_FAILED;
    }
    else
    {
        return read_sperator(handler, fp, STRICT_MATCH);
    }
}

int read_int64(ap_handler* handler, FILE *fp, long long *val)
{
    int ret = EOF;
    ret = fscanf(fp, "%Ld", val);
    if(ret != 1)
    {
        handler->err =  AP_ERR_BAD_FORMAT;
        return MATCH_FAILED;
    }
    else
    {
        return read_sperator(handler, fp, STRICT_MATCH);
    } 
}

int read_double(ap_handler* handler, FILE *fp, double *val)
{
    int ret = EOF;
    ret = fscanf(fp, "%lf", val);
    if(ret != 1)
    {
        handler->err =  AP_ERR_BAD_FORMAT;
        return MATCH_FAILED;
    }
    else
    {
        return read_sperator(handler, fp, STRICT_MATCH);
    } 
}

int read_str(ap_handler* handler, FILE *fp, char* str, int max_size)
{
    char buf[STR_BUF_MAX];
    int c = EOF;
    int i = 0;

    if(max_size > STR_BUF_MAX)
    {
        return -1;
    }

    memset(buf, 0, STR_BUF_MAX);
    for(; i < max_size - 1; i++)
    {
        c = fgetc(fp);
        if(c == EOF)
        {
            handler->err = AP_ERR_BAD_FORMAT;
            return MATCH_FAILED;
        }
        if(c == FIELD_SEPRATOR)
        {
            break;
        }
        buf[i] = c;
    }
    strncpy(str, buf, i);
    if(c == FIELD_SEPRATOR)
    {
        return MATCH_SUCCESS;
    }
    else
    {
        return read_sperator(handler, fp, NON_STRICT_MATCH); 
    }
}

int read_pc_from_file(ap_handler* handler, FILE *fp)
{
    int ret = MATCH_FAILED;
    perf_counter *pc;

    if(handler->len == PERF_COUNT_MAX)
    {
        handler->err = AP_ERR_BUF_OVERFLOW; 
        goto EXIT; 
    }
    pc = &handler->buf[handler->len];

    ret = read_int(handler, fp, &pc->counter_typer);
    if(ret == MATCH_FAILED)
    {
        goto EXIT;
    }

    ret = read_str(handler, fp, pc->type_name, TYPE_NAME_MAX);
    if(ret == MATCH_FAILED)
    {
        goto EXIT;
    }

    ret = read_str(handler, fp, pc->property_name, PROPERTY_NAME_MAX);
    if(ret == MATCH_FAILED)
    {
        goto EXIT;
    }

    ret = read_str(handler, fp, pc->instance_name, INSTANCE_NAME_MAX);
    if(ret == MATCH_FAILED)
    {
        goto EXIT;
    }
    
    ret = read_int(handler, fp, &pc->is_empty);
    if(ret == MATCH_FAILED)
    {
        goto EXIT;
    }

    if(!pc->is_empty)
    {
        switch(pc->counter_typer)
        {
            case PERF_COUNTER_TYPE_INT:
               ret = read_int(handler, fp, &pc->val_int);
               break;
            case PERF_COUNTER_TYPE_LARGE:
               ret = read_int64(handler, fp, &pc->val_large);
               break;
            case PERF_COUNTER_TYPE_DOUBLE:
               ret = read_double(handler, fp, &pc->val_double);
               break;
            case PERF_COUNTER_TYPE_STRING:
               ret = read_str(handler, fp, pc->val_str, STRING_VALUE_MAX);
               break;
        }
        if(ret == MATCH_FAILED)
        {
            goto EXIT;
        }
    }
    
    ret = read_str(handler, fp, pc->unit_name, UNIT_NAME_MAX);
    if(ret == MATCH_FAILED)
    {
        goto EXIT;
    }

    ret = read_int(handler, fp, &pc->refresh_interval);
    if(ret == MATCH_FAILED)
    {
        goto EXIT;
    }

    ret = read_int64(handler, fp, &pc->timestamp);
    if(ret == MATCH_FAILED)
    {
        goto EXIT;
    }

    ret = read_str(handler, fp, pc->machine_name, MACHINE_NAME_MAX);
    if(ret == MATCH_FAILED)
    {
        goto EXIT;
    }

    handler->len++;

    //Discard line end if exits.
    fscanf(fp, "\n");
    
EXIT:
    return ret;
}

void ap_refresh(ap_handler *handler)
{
    FILE *fp = 0;
    perf_counter *next = 0;
   
    //Reset handler 
    memset(handler->buf, 0, sizeof(perf_counter) * PERF_COUNT_MAX);
    handler->len = 0;
   
    errno = 0;
    fp = fopen(handler->ap_file, "r");
    if(errno || 0 == fp){
        handler->err = AP_ERR_IO_ERR;
        sprintf(handler->err_msg, "fopen failed, errno:%d", errno);
        goto EXIT;  
    }
    
    while(read_pc_from_file(handler, fp) != EOF)
    {
        if(handler->err != 0)
        {
            goto EXIT;
        }
    }

EXIT:
    if(fp)
    {
        fclose(fp);
    }
}

void ap_metric_all(ap_handler *handler, perf_counter *all, int size)
{
    int size_to_cp = 0;
    if(handler->err)
    {
        return;
    }
    size_to_cp = INTMIN(handler->len, size);
    if(size_to_cp > 0)
    {
        memcpy(all, handler->buf, sizeof(perf_counter) * size_to_cp);
    }
}

void find_first(ap_handler *handler, perf_counter *pc, 
               const char *type_name, const char* property_name)
{
   int i = 0; 
   for(;i < handler->len; i++)
   {
       if(0 == strcmp(handler->buf[i].type_name, type_name) && 
          0 == strcmp(handler->buf[i].property_name, property_name))
       {
            memcpy(pc, &handler->buf[i], sizeof(perf_counter));
       }
   }
   handler->err = AP_ERR_NOT_FOUND;
}

void ap_metric_machine_cloudprovider(ap_handler* handler, perf_counter* pc)
{
    if(handler->err)
    {
        return;
    }
    find_first(handler, pc, "config", "Cloud Provider");
}
