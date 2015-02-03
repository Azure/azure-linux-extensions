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

/*The max buf size for all string*/
#define STR_BUF_MAX         (256)

#define TYPE_NAME_MAX       (4)
#define PROPERTY_NAME_MAX   (128)
#define INSTANCE_NAME_MAX   (256)
#define STRING_VALUE_MAX    (256)
#define UNIT_NAME_MAX       (64)
#define MACHINE_NAME_MAX    (128)
#define ERR_MSG_MAX         (128)

#define PERF_COUNT_MAX      (128)

#define PERF_COUNTER_TYPE_INVALID	(0)
#define PERF_COUNTER_TYPE_INT		(1)
#define PERF_COUNTER_TYPE_DOUBLE	(2)
#define PERF_COUNTER_TYPE_LARGE	    (3)
#define PERF_COUNTER_TYPE_STRING	(4)

#define AP_ERR_NOT_FOUND            (-1)
#define AP_ERR_BUF_OVERFLOW         (-2) 
#define AP_ERR_IO_ERR               (-3)
#define AP_ERR_BAD_FORMAT           (-4)
#define AP_ERR_STR_BUF_OVERFLOW     (-5)


typedef struct 
{
	int			    counter_typer;
	char			type_name[TYPE_NAME_MAX];
	char			property_name[PROPERTY_NAME_MAX];
	char			instance_name[STRING_VALUE_MAX];	
    int             is_empty;
    union {
        int         val_int;
        long long   val_large;
        double      val_double;
        char        val_str[STRING_VALUE_MAX];
    };
	char			unit_name[UNIT_NAME_MAX];
    unsigned int	refresh_interval;
	long long		timestamp;
	char			machine_name[MACHINE_NAME_MAX];	
    
} perf_counter;

typedef struct
{
    perf_counter    buf[PERF_COUNT_MAX]; 
    int             len; 
    int             err;
    char            err_msg[ERR_MSG_MAX];
    char            *ap_file;
} ap_handler;

ap_handler* ap_open();

extern void ap_close(ap_handler* handler);

extern void ap_refresh(ap_handler* handler);

//"\config\Cloud Provider";
extern void ap_metric_machine_cloudprovider(ap_handler* handler, 
                                            perf_counter* pc);

