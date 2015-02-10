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
#ifndef AZURE_PERF
#define AZURE_PERF

/*All the strings are utf-8 encoded*/

/*The max buf size for all string*/
#define STR_BUF_MAX         (256)

#define TYPE_NAME_MAX       (64)
#define PROPERTY_NAME_MAX   (128)
#define INSTANCE_NAME_MAX   (256)
#define STRING_VALUE_MAX    (256)
#define UNIT_NAME_MAX       (64)
#define MACHINE_NAME_MAX    (128)

#define PERF_COUNT_MAX      (128)

#define PERF_COUNTER_TYPE_INVALID	(0)
#define PERF_COUNTER_TYPE_INT		(1)
#define PERF_COUNTER_TYPE_DOUBLE	(2)
#define PERF_COUNTER_TYPE_LARGE	    (3)
#define PERF_COUNTER_TYPE_STRING	(4)

#define AP_ERR_PC_NOT_FOUND                 (-1)
#define AP_ERR_PC_BUF_OVERFLOW              (-2) 
#define AP_ERR_INVALID_COUNTER_TYPE         (-11)
#define AP_ERR_INVALID_TYPE_NAME            (-12)
#define AP_ERR_INVALID_PROPERTY_NAME        (-13)
#define AP_ERR_INVALID_INSTANCE_NAME        (-14)
#define AP_ERR_INVALID_IS_EMPTY_FLAG        (-15)
#define AP_ERR_INVALID_VALUE                (-15)
#define AP_ERR_INVALID_UNIT_NAME            (-16)
#define AP_ERR_INVALID_REFRESH_INTERVAL     (-17)
#define AP_ERR_INVALID_TIMESTAMP            (-18)
#define AP_ERR_INVALID_MACHINE_NAME         (-19)


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
    char            *ap_file;
} ap_handler;

ap_handler* ap_open();

extern void ap_close(ap_handler* handler);

extern void ap_refresh(ap_handler* handler);

extern int ap_metric_all(ap_handler *handler, perf_counter *pc, size_t size);

//config\Cloud Provider
extern int ap_metric_config_cloud_provider(ap_handler *handler, perf_counter *pc, size_t size);

//config\CPU Over-Provisioning
extern int ap_metric_config_cpu_over_provisioning(ap_handler *handler, perf_counter *pc, size_t size);

//config\Memory Over-Provisioning
extern int ap_metric_config_memory_over_provisioning(ap_handler *handler, perf_counter *pc, size_t size);

//config\Data Provider Version
extern int ap_metric_config_data_provider_version(ap_handler *handler, perf_counter *pc, size_t size);

//config\Data Sources
extern int ap_metric_config_data_sources(ap_handler *handler, perf_counter *pc, size_t size);

//config\Instance Type
extern int ap_metric_config_instance_type(ap_handler *handler, perf_counter *pc, size_t size);

//config\Virtualization Solution
extern int ap_metric_config_virtualization_solution(ap_handler *handler, perf_counter *pc, size_t size);

//config\Virtualization Solution Version
extern int ap_metric_config_virtualization_solution_version(ap_handler *handler, perf_counter *pc, size_t size);

//cpu\Current Hw Frequency
extern int ap_metric_cpu_current_hw_frequency(ap_handler *handler, perf_counter *pc, size_t size);

//cpu\Max Hw Frequency
extern int ap_metric_cpu_max_hw_frequency(ap_handler *handler, perf_counter *pc, size_t size);

//cpu\Current VM Processing Power
extern int ap_metric_cpu_current_vm_processing_power(ap_handler *handler, perf_counter *pc, size_t size);

//cpu\Guaranteed VM Processing Power
extern int ap_metric_cpu_guaranteed_vm_processing_power(ap_handler *handler, perf_counter *pc, size_t size);

//cpu\Max. VM Processing Power
extern int ap_metric_cpu_max_vm_processing_power(ap_handler *handler, perf_counter *pc, size_t size);

//cpu\Number of Cores per CPU
extern int ap_metric_cpu_number_of_cores_per_cpu(ap_handler *handler, perf_counter *pc, size_t size);

//cpu\Number of Threads per Core
extern int ap_metric_cpu_number_of_threads_per_core(ap_handler *handler, perf_counter *pc, size_t size);

//cpu\Phys. Processing Power per vCPU
extern int ap_metric_cpu_phys_processing_power_per_vcpu(ap_handler *handler, perf_counter *pc, size_t size);

//cpu\Processor Type
extern int ap_metric_cpu_processor_type(ap_handler *handler, perf_counter *pc, size_t size);

#endif
