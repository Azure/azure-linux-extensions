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

int ap_metric_config_cloud_provider(ap_handler *handler, perf_counter *pc, size_t size)
{
    if(handler->err)
    {
        return 0;
    }
    return get_metric(handler, pc, "config", "Cloud Provider", size);
}

int ap_metric_config_cpu_over_provisioning(ap_handler *handler, perf_counter *pc, size_t size)
{
    if(handler->err)
    {
        return 0;
    }
    return get_metric(handler, pc, "config", "CPU Over-Provisioning", size);
}

int ap_metric_config_memory_over_provisioning(ap_handler *handler, perf_counter *pc, size_t size)
{
    if(handler->err)
    {
        return 0;
    }
    return get_metric(handler, pc, "config", "Memory Over-Provisioning", size);
}

int ap_metric_config_data_provider_version(ap_handler *handler, perf_counter *pc, size_t size)
{
    if(handler->err)
    {
        return 0;
    }
    return get_metric(handler, pc, "config", "Data Provider Version", size);
}

int ap_metric_config_data_sources(ap_handler *handler, perf_counter *pc, size_t size)
{
    if(handler->err)
    {
        return 0;
    }
    return get_metric(handler, pc, "config", "Data Sources", size);
}

int ap_metric_config_instance_type(ap_handler *handler, perf_counter *pc, size_t size)
{
    if(handler->err)
    {
        return 0;
    }
    return get_metric(handler, pc, "config", "Instance Type", size);
}

int ap_metric_config_virtualization_solution(ap_handler *handler, perf_counter *pc, size_t size)
{
    if(handler->err)
    {
        return 0;
    }
    return get_metric(handler, pc, "config", "Virtualization Solution", size);
}

int ap_metric_config_virtualization_solution_version(ap_handler *handler, perf_counter *pc, size_t size)
{
    if(handler->err)
    {
        return 0;
    }
    return get_metric(handler, pc, "config", "Virtualization Solution Version", size);
}

int ap_metric_cpu_current_hw_frequency(ap_handler *handler, perf_counter *pc, size_t size)
{
    if(handler->err)
    {
        return 0;
    }
    return get_metric(handler, pc, "cpu", "Current Hw Frequency", size);
}

int ap_metric_cpu_max_hw_frequency(ap_handler *handler, perf_counter *pc, size_t size)
{
    if(handler->err)
    {
        return 0;
    }
    return get_metric(handler, pc, "cpu", "Max Hw Frequency", size);
}

int ap_metric_cpu_current_vm_processing_power(ap_handler *handler, perf_counter *pc, size_t size)
{
    if(handler->err)
    {
        return 0;
    }
    return get_metric(handler, pc, "cpu", "Current VM Processing Power", size);
}

int ap_metric_cpu_guaranteed_vm_processing_power(ap_handler *handler, perf_counter *pc, size_t size)
{
    if(handler->err)
    {
        return 0;
    }
    return get_metric(handler, pc, "cpu", "Guaranteed VM Processing Power", size);
}

int ap_metric_cpu_max_vm_processing_power(ap_handler *handler, perf_counter *pc, size_t size)
{
    if(handler->err)
    {
        return 0;
    }
    return get_metric(handler, pc, "cpu", "Max. VM Processing Power", size);
}

int ap_metric_cpu_number_of_cores_per_cpu(ap_handler *handler, perf_counter *pc, size_t size)
{
    if(handler->err)
    {
        return 0;
    }
    return get_metric(handler, pc, "cpu", "Number of Cores per CPU", size);
}

int ap_metric_cpu_number_of_threads_per_core(ap_handler *handler, perf_counter *pc, size_t size)
{
    if(handler->err)
    {
        return 0;
    }
    return get_metric(handler, pc, "cpu", "Number of Threads per Core", size);
}

int ap_metric_cpu_phys_processing_power_per_vcpu(ap_handler *handler, perf_counter *pc, size_t size)
{
    if(handler->err)
    {
        return 0;
    }
    return get_metric(handler, pc, "cpu", "Phys. Processing Power per vCPU", size);
}

int ap_metric_cpu_processor_type(ap_handler *handler, perf_counter *pc, size_t size)
{
    if(handler->err)
    {
        return 0;
    }
    return get_metric(handler, pc, "cpu", "Processor Type", size);
}

int ap_metric_cpu_reference_compute_unit(ap_handler *handler, perf_counter *pc, size_t size)
{
    if(handler->err)
    {
        return 0;
    }
    return get_metric(handler, pc, "cpu", "Reference Compute Unit", size);
}

int ap_metric_cpu_vcpu_mapping(ap_handler *handler, perf_counter *pc, size_t size)
{
    if(handler->err)
    {
        return 0;
    }
    return get_metric(handler, pc, "cpu", "vCPU Mapping", size);
}

int ap_metric_cpu_vm_processing_power_consumption(ap_handler *handler, perf_counter *pc, size_t size)
{
    if(handler->err)
    {
        return 0;
    }
    return get_metric(handler, pc, "cpu", "VM Processing Power Consumption", size);
}

int ap_metric_memory_current_memory_assigned(ap_handler *handler, perf_counter *pc, size_t size)
{
    if(handler->err)
    {
        return 0;
    }
    return get_metric(handler, pc, "memory", "Current Memory assigned", size);
}

int ap_metric_memory_guaranteed_memory_assigned(ap_handler *handler, perf_counter *pc, size_t size)
{
    if(handler->err)
    {
        return 0;
    }
    return get_metric(handler, pc, "memory", "Guaranteed Memory assigned", size);
}

int ap_metric_memory_max_memory_assigned(ap_handler *handler, perf_counter *pc, size_t size)
{
    if(handler->err)
    {
        return 0;
    }
    return get_metric(handler, pc, "memory", "Max Memory assigned", size);
}

int ap_metric_memory_vm_memory_consumption(ap_handler *handler, perf_counter *pc, size_t size)
{
    if(handler->err)
    {
        return 0;
    }
    return get_metric(handler, pc, "memory", "VM Memory Consumption", size);
}

int ap_metric_network_adapter_id(ap_handler *handler, perf_counter *pc, size_t size)
{
    if(handler->err)
    {
        return 0;
    }
    return get_metric(handler, pc, "network", "Adapter Id", size);
}

int ap_metric_network_mapping(ap_handler *handler, perf_counter *pc, size_t size)
{
    if(handler->err)
    {
        return 0;
    }
    return get_metric(handler, pc, "network", "Mapping", size);
}

int ap_metric_network_min_network_bandwidth(ap_handler *handler, perf_counter *pc, size_t size)
{
    if(handler->err)
    {
        return 0;
    }
    return get_metric(handler, pc, "network", "Minimum Network Bandwidth", size);
}

int ap_metric_network_max_network_bandwidth(ap_handler *handler, perf_counter *pc, size_t size)
{
    if(handler->err)
    {
        return 0;
    }
    return get_metric(handler, pc, "network", "Maximum Network Bandwidth", size);
}

int ap_metric_network_network_read_bytes(ap_handler *handler, perf_counter *pc, size_t size)
{
    if(handler->err)
    {
        return 0;
    }
    return get_metric(handler, pc, "network", "Network Read Bytes", size);
}

int ap_metric_network_network_write_bytes(ap_handler *handler, perf_counter *pc, size_t size)
{
    if(handler->err)
    {
        return 0;
    }
    return get_metric(handler, pc, "network", "Network Write Bytes", size);
}

int ap_metric_network_packets_retransmitted(ap_handler *handler, perf_counter *pc, size_t size)
{
    if(handler->err)
    {
        return 0;
    }
    return get_metric(handler, pc, "network", "Packets Retransmitted", size);
}

int ap_metric_config_last_hardware_change(ap_handler *handler, perf_counter *pc, size_t size)
{
    if(handler->err)
    {
        return 0;
    }
    return get_metric(handler, pc, "config", "Last Hardware Change", size);
}

int ap_metric_storage_phys_disc_to_storage_mapping(ap_handler *handler, perf_counter *pc, size_t size)
{
    if(handler->err)
    {
        return 0;
    }
    return get_metric(handler, pc, "storage", "Phys. Disc to Storage Mapping", size);
}

int ap_metric_storage_storage_id(ap_handler *handler, perf_counter *pc, size_t size)
{
    if(handler->err)
    {
        return 0;
    }
    return get_metric(handler, pc, "storage", "Storage ID", size);
}

int ap_metric_storage_read_bytes(ap_handler *handler, perf_counter *pc, size_t size)
{
    if(handler->err)
    {
        return 0;
    }
    return get_metric(handler, pc, "storage", "Storage Read Bytes", size);
}

int ap_metric_storage_read_ops(ap_handler *handler, perf_counter *pc, size_t size)
{
    if(handler->err)
    {
        return 0;
    }
    return get_metric(handler, pc, "storage", "Storage Read Ops", size);
}

int ap_metric_storage_read_op_latency_e2e(ap_handler *handler, perf_counter *pc, size_t size)
{
    if(handler->err)
    {
        return 0;
    }
    return get_metric(handler, pc, "storage", "Storage Read Op Latency E2E msec", size);
}

int ap_metric_storage_read_op_latency_server(ap_handler *handler, perf_counter *pc, size_t size)
{
    if(handler->err)
    {
        return 0;
    }
    return get_metric(handler, pc, "storage", "Storage Read Op Latency Server msec", size);
}

int ap_metric_storage_read_throughput_e2e(ap_handler *handler, perf_counter *pc, size_t size)
{
    if(handler->err)
    {
        return 0;
    }
    return get_metric(handler, pc, "storage", "Storage Read Throughput E2E MB/sec", size);
}

int ap_metric_storage_write_bytes(ap_handler *handler, perf_counter *pc, size_t size)
{
    if(handler->err)
    {
        return 0;
    }
    return get_metric(handler, pc, "storage", "Storage Write Bytes", size);
}

int ap_metric_storage_write_ops(ap_handler *handler, perf_counter *pc, size_t size)
{
    if(handler->err)
    {
        return 0;
    }
    return get_metric(handler, pc, "storage", "Storage Write Ops", size);
}

int ap_metric_storage_write_op_latency_e2e(ap_handler *handler, perf_counter *pc, size_t size)
{
    if(handler->err)
    {
        return 0;
    }
    return get_metric(handler, pc, "storage", "Storage Write Op Latency E2E msec", size);
}

int ap_metric_storage_write_op_latency_server(ap_handler *handler, perf_counter *pc, size_t size)
{
    if(handler->err)
    {
        return 0;
    }
    return get_metric(handler, pc, "storage", "Storage Write Op Latency Server msec", size);
}

int ap_metric_storage_write_throughput_e2e(ap_handler *handler, perf_counter *pc, size_t size)
{
    if(handler->err)
    {
        return 0;
    }
    return get_metric(handler, pc, "storage", "Storage Write Throughput E2E MB/sec", size);
}

