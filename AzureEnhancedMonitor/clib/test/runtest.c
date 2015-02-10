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

static const char default_input[] = "./test/cases/positive_case";

int main(int argc, char ** argv)
{
    char* ap_file = (char*) default_input;
    if(argc == 2)
    {
        ap_file = argv[1];
    }
    printf("Parsing perf counters from: %s\n", ap_file);
    run_test(ap_file);
}

void print_counter(perf_counter *pc)
{
    printf("%-7s | %-24.24s | %-15.15s | ", pc->type_name, pc->property_name, 
            pc->instance_name);
    switch(pc->counter_typer)
    {
        case PERF_COUNTER_TYPE_INT:
            printf("%-30d", pc->val_int);
            break;
        case PERF_COUNTER_TYPE_LARGE:
            printf("%-30Ld", pc->val_large);
            break;
        case PERF_COUNTER_TYPE_DOUBLE:
            printf("%-30lf", pc->val_double);
            break;
        case PERF_COUNTER_TYPE_STRING:
        default:
            printf("%-30.30s", pc->val_str);
            break;
    }
    printf(" |\n");
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
        print_counter(&pc);
        memset(&pc, 0 , sizeof(perf_counter));
    }

    printf(">>>>ap_metric_config_cloud_provider\n");
    ap_metric_config_cloud_provider(handler, &pc, 1);
    print_counter(&pc);
    printf(">>>>ap_metric_config_cpu_over_provisioning\n");
    ap_metric_config_cpu_over_provisioning(handler, &pc, 1);
    print_counter(&pc);
    printf(">>>>ap_metric_config_memory_over_provisioning\n");
    ap_metric_config_memory_over_provisioning(handler, &pc, 1);
    print_counter(&pc);
    printf(">>>>ap_metric_config_data_provider_version\n");
    ap_metric_config_data_provider_version(handler, &pc, 1);
    print_counter(&pc);
    printf(">>>>ap_metric_config_data_sources\n");
    ap_metric_config_data_sources(handler, &pc, 1);
    print_counter(&pc);
    printf(">>>>ap_metric_config_instance_type\n");
    ap_metric_config_instance_type(handler, &pc, 1);
    print_counter(&pc);
    printf(">>>>ap_metric_config_virtualization_solution\n");
    ap_metric_config_virtualization_solution(handler, &pc, 1);
    print_counter(&pc);
    printf(">>>>ap_metric_config_virtualization_solution_version\n");
    ap_metric_config_virtualization_solution_version(handler, &pc, 1);
    print_counter(&pc);
    printf(">>>>ap_metric_cpu_current_hw_frequency\n");
    ap_metric_cpu_current_hw_frequency(handler, &pc, 1);
    print_counter(&pc);
    printf(">>>>ap_metric_cpu_max_hw_frequency\n");
    ap_metric_cpu_max_hw_frequency(handler, &pc, 1);
    print_counter(&pc);
    printf(">>>>ap_metric_cpu_current_vm_processing_power\n");
    ap_metric_cpu_current_vm_processing_power(handler, &pc, 1);
    print_counter(&pc);
    printf(">>>>ap_metric_cpu_guaranteed_vm_processing_power\n");
    ap_metric_cpu_guaranteed_vm_processing_power(handler, &pc, 1);
    print_counter(&pc);
    printf(">>>>ap_metric_cpu_max_vm_processing_power\n");
    ap_metric_cpu_max_vm_processing_power(handler, &pc, 1);
    print_counter(&pc);
    printf(">>>>ap_metric_cpu_number_of_cores_per_cpu\n");
    ap_metric_cpu_number_of_cores_per_cpu(handler, &pc, 1);
    print_counter(&pc);
    printf(">>>>ap_metric_cpu_number_of_threads_per_core\n");
    ap_metric_cpu_number_of_threads_per_core(handler, &pc, 1);
    print_counter(&pc);
    printf(">>>>ap_metric_cpu_phys_processing_power_per_vcpu\n");
    ap_metric_cpu_phys_processing_power_per_vcpu(handler, &pc, 1);
    print_counter(&pc);
    printf(">>>>ap_metric_cpu_processor_type\n");
    ap_metric_cpu_processor_type(handler, &pc, 1);
    print_counter(&pc);
    printf(">>>>ap_metric_cpu_reference_compute_unit\n");
    ap_metric_cpu_reference_compute_unit(handler, &pc, 1);
    print_counter(&pc);
    printf(">>>>ap_metric_cpu_vcpu_mapping\n");
    ap_metric_cpu_vcpu_mapping(handler, &pc, 1);
    print_counter(&pc);
    printf(">>>>ap_metric_cpu_vm_processing_power_consumption\n");
    ap_metric_cpu_vm_processing_power_consumption(handler, &pc, 1);
    print_counter(&pc);
    printf(">>>>ap_metric_memory_current_memory_assigned\n");
    ap_metric_memory_current_memory_assigned(handler, &pc, 1);
    print_counter(&pc);
    printf(">>>>ap_metric_memory_guaranteed_memory_assigned\n");
    ap_metric_memory_guaranteed_memory_assigned(handler, &pc, 1);
    print_counter(&pc);
    printf(">>>>ap_metric_memory_max_memory_assigned\n");
    ap_metric_memory_max_memory_assigned(handler, &pc, 1);
    print_counter(&pc);
    printf(">>>>ap_metric_memory_vm_memory_consumption\n");
    ap_metric_memory_vm_memory_consumption(handler, &pc, 1);
    print_counter(&pc);
    printf(">>>>ap_metric_network_adapter_id\n");
    ap_metric_network_adapter_id(handler, &pc, 1);
    print_counter(&pc);
    printf(">>>>ap_metric_network_mapping\n");
    ap_metric_network_mapping(handler, &pc, 1);
    print_counter(&pc);
    printf(">>>>ap_metric_network_min_network_bandwidth\n");
    ap_metric_network_min_network_bandwidth(handler, &pc, 1);
    print_counter(&pc);
    printf(">>>>ap_metric_network_max_network_bandwidth\n");
    ap_metric_network_max_network_bandwidth(handler, &pc, 1);
    print_counter(&pc);
    printf(">>>>ap_metric_network_network_read_bytes\n");
    ap_metric_network_network_read_bytes(handler, &pc, 1);
    print_counter(&pc);
    printf(">>>>ap_metric_network_network_write_bytes\n");
    ap_metric_network_network_write_bytes(handler, &pc, 1);
    print_counter(&pc);
    printf(">>>>ap_metric_network_packets_retransmitted\n");
    ap_metric_network_packets_retransmitted(handler, &pc, 1);
    print_counter(&pc);
    printf(">>>>ap_metric_config_last_hardware_change\n");
    ap_metric_config_last_hardware_change(handler, &pc, 1);
    print_counter(&pc);
    printf(">>>>ap_metric_storage_phys_disc_to_storage_mapping\n");
    ap_metric_storage_phys_disc_to_storage_mapping(handler, &pc, 1);
    print_counter(&pc);
    printf(">>>>ap_metric_storage_storage_id\n");
    ap_metric_storage_storage_id(handler, &pc, 1);
    print_counter(&pc);
    printf(">>>>ap_metric_storage_read_bytes\n");
    ap_metric_storage_read_bytes(handler, &pc, 1);
    print_counter(&pc);
    printf(">>>>ap_metric_storage_read_ops\n");
    ap_metric_storage_read_ops(handler, &pc, 1);
    print_counter(&pc);
    printf(">>>>ap_metric_storage_read_op_latency_e2e\n");
    ap_metric_storage_read_op_latency_e2e(handler, &pc, 1);
    print_counter(&pc);
    printf(">>>>ap_metric_storage_read_op_latency_server\n");
    ap_metric_storage_read_op_latency_server(handler, &pc, 1);
    print_counter(&pc);
    printf(">>>>ap_metric_storage_read_throughput_e2e\n");
    ap_metric_storage_read_throughput_e2e(handler, &pc, 1);
    print_counter(&pc);
    printf(">>>>ap_metric_storage_write_bytes\n");
    ap_metric_storage_write_bytes(handler, &pc, 1);
    print_counter(&pc);
    printf(">>>>ap_metric_storage_write_ops\n");
    ap_metric_storage_write_ops(handler, &pc, 1);
    print_counter(&pc);
    printf(">>>>ap_metric_storage_write_op_latency_e2e\n");
    ap_metric_storage_write_op_latency_e2e(handler, &pc, 1);
    print_counter(&pc);
    printf(">>>>ap_metric_storage_write_op_latency_server\n");
    ap_metric_storage_write_op_latency_server(handler, &pc, 1);
    print_counter(&pc);
    printf(">>>>ap_metric_storage_write_throughput_e2e\n");
    ap_metric_storage_write_throughput_e2e(handler, &pc, 1);
    print_counter(&pc);
    
EXIT:
    ap_close(handler);
    return ret;
}

