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
#define MATCH_EOF           (-1)
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

int read_sperator(FILE *fp, int strict)
{
    int c;
    c = fgetc(fp);
    //In non-strict mode, Read and discard chars until EOF or FIELD_SEPRATOR
    while(strict == NON_STRICT_MATCH && c != EOF && c != FIELD_SEPRATOR)
    {
        c = fgetc(fp);
    }
    if(c == EOF)
    {
        return MATCH_EOF;
    }
    if(c != FIELD_SEPRATOR)
    {
        return MATCH_FAILED;
    }
    else
    {
        return MATCH_SUCCESS;
    }
}

int read_int(FILE *fp, int *val)
{
    int ret = EOF;
    ret = fscanf(fp, "%d", val);
    if(ret == EOF)
    {
        return MATCH_EOF;
    }
    if(ret != 1)
    {
        return MATCH_FAILED;
    }
    else
    {
        return read_sperator(fp, STRICT_MATCH);
    }
}

int read_int64(FILE *fp, long long *val)
{
    int ret = EOF;
    ret = fscanf(fp, "%Ld", val);
    if(ret == EOF)
    {
        return MATCH_EOF;
    }
    if(ret != 1)
    {
        return MATCH_FAILED;
    }
    else
    {
        return read_sperator(fp, STRICT_MATCH);
    } 
}

int read_double(FILE *fp, double *val)
{
    int ret = EOF;
    ret = fscanf(fp, "%lf", val);
    if(ret == EOF)
    {
        return MATCH_EOF;
    }
    if(ret != 1)
    {
        return MATCH_FAILED;
    }
    else
    {
        return read_sperator(fp, STRICT_MATCH);
    } 
}

int read_str(FILE *fp, char* str, int max_size)
{
    char buf[STR_BUF_MAX];
    int c = EOF;
    int i = 0;

    if(max_size > STR_BUF_MAX)
    {
        return MATCH_FAILED;
    }

    memset(buf, 0, STR_BUF_MAX);
    for(; i < max_size - 1; i++)
    {
        c = fgetc(fp);
        if(c == EOF)
        {
            return MATCH_EOF;
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
    else//Reaches buf max, discard the rest part of string
    {
        return read_sperator(fp, NON_STRICT_MATCH); 
    }
}

void set_handler_err(ap_handler *handler, int err)
{
    handler->err = err;
}

int read_pc_from_file(ap_handler* handler, FILE *fp)
{
    int ret = MATCH_FAILED;
    perf_counter *pc;

    if(handler->len == PERF_COUNT_MAX)
    {
        handler->err = AP_ERR_PC_BUF_OVERFLOW; 
        goto EXIT; 
    }
    pc = &handler->buf[handler->len];

    ret = read_int(fp, &pc->counter_typer);
    if(ret == MATCH_EOF)
    {
        goto EXIT; 
    }
    if(ret != MATCH_SUCCESS)
    {
        set_handler_err(handler, AP_ERR_INVALID_COUNTER_TYPE);
        goto EXIT;
    }

    ret = read_str(fp, pc->type_name, TYPE_NAME_MAX);
    if(ret != MATCH_SUCCESS)
    {
        set_handler_err(handler, AP_ERR_INVALID_TYPE_NAME);
        goto EXIT;
    }

    ret = read_str(fp, pc->property_name, PROPERTY_NAME_MAX);
    if(ret != MATCH_SUCCESS)
    {
        set_handler_err(handler, AP_ERR_INVALID_PROPERTY_NAME);
        goto EXIT;
    }

    ret = read_str(fp, pc->instance_name, INSTANCE_NAME_MAX);
    if(ret != MATCH_SUCCESS)
    {
        set_handler_err(handler, AP_ERR_INVALID_INSTANCE_NAME);
        goto EXIT;
    }
    
    ret = read_int(fp, &pc->is_empty);
    if(ret != MATCH_SUCCESS)
    {
        set_handler_err(handler, AP_ERR_INVALID_IS_EMPTY_FLAG);
        goto EXIT;
    }

    if(!pc->is_empty)
    {
        switch(pc->counter_typer)
        {
            case PERF_COUNTER_TYPE_INT:
               ret = read_int(fp, &pc->val_int);
               break;
            case PERF_COUNTER_TYPE_LARGE:
               ret = read_int64(fp, &pc->val_large);
               break;
            case PERF_COUNTER_TYPE_DOUBLE:
               ret = read_double(fp, &pc->val_double);
               break;
            case PERF_COUNTER_TYPE_STRING:
               ret = read_str(fp, pc->val_str, STRING_VALUE_MAX);
               break;
        }
        if(ret != MATCH_SUCCESS)
        {
            set_handler_err(handler, AP_ERR_INVALID_VALUE);
            goto EXIT;
        }
    }
    else
    {
        ret = read_sperator(fp, NON_STRICT_MATCH);
        if(ret != MATCH_SUCCESS)
        {
            set_handler_err(handler, AP_ERR_INVALID_VALUE);
            goto EXIT;
        }
    }
    
    ret = read_str(fp, pc->unit_name, UNIT_NAME_MAX);
    if(ret != MATCH_SUCCESS)
    {
        set_handler_err(handler, AP_ERR_INVALID_UNIT_NAME);
        goto EXIT;
    }

    ret = read_int(fp, &pc->refresh_interval);
    if(ret != MATCH_SUCCESS)
    {
        set_handler_err(handler, AP_ERR_INVALID_REFRESH_INTERVAL);
        goto EXIT;
    }

    ret = read_int64(fp, &pc->timestamp);
    if(ret != MATCH_SUCCESS)
    {
        set_handler_err(handler, AP_ERR_INVALID_TIMESTAMP);
        goto EXIT;
    }

    ret = read_str(fp, pc->machine_name, MACHINE_NAME_MAX);
    if(ret != MATCH_SUCCESS)
    {
        set_handler_err(handler, AP_ERR_INVALID_MACHINE_NAME);
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
        handler->err = errno;
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

int ap_metric_all(ap_handler *handler, perf_counter *all, size_t size)
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
    return size_to_cp;
}

int get_metric(ap_handler *handler, perf_counter *pc, 
        const char *type_name, const char* property_name, size_t size)
{
    int i = 0; 
    int found = 0;
    for(;i < handler->len && found < size; i++)
    {
        if(0 == strcmp(handler->buf[i].type_name, type_name) && 
                0 == strcmp(handler->buf[i].property_name, property_name))
        {
            memcpy(pc + found, &handler->buf[i], sizeof(perf_counter));
            found++;
        }
    }
    if(!found)
    {
        handler->err = AP_ERR_PC_NOT_FOUND;
    }
    return found;
}

