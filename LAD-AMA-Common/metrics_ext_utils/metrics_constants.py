#!/usr/bin/env python
#
# Azure Linux extension
#
# Copyright (c) Microsoft Corporation
# All rights reserved.
# MIT License
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the ""Software""), to deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit
# persons to whom the Software is furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the
# Software.
# THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
# WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
# OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

# This File contains constants used for Platform Metrics feature in LAD and Azure Monitor Extension

lad_metrics_extension_bin = "/usr/local/lad/bin/MetricsExtension"
ama_metrics_extension_bin = "/usr/sbin/MetricsExtension"
lad_telegraf_bin = "/usr/local/lad/bin/telegraf"
ama_telegraf_bin = "/usr/sbin/telegraf"
metrics_extension_service_path = "/lib/systemd/system/metrics-extension.service"
metrics_extension_service_path_usr_lib = "/usr/lib/systemd/system/metrics-extension.service"
telegraf_service_path = "/lib/systemd/system/metrics-sourcer.service"
telegraf_service_path_usr_lib = "/usr/lib/systemd/system/metrics-sourcer.service"
lad_metrics_extension_udp_port = "13459"
ama_metrics_extension_udp_port = "17659"
lad_metrics_extension_influx_udp_url = "udp://127.0.0.1:" + lad_metrics_extension_udp_port
telegraf_influx_url = "unix:///var/run/mdsd/lad_mdsd_influx.socket"
metrics_extension_namespace = "Azure.VM.Linux.GuestMetrics"