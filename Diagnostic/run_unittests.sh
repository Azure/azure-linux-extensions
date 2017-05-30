#!/bin/bash

for test in watchertests test_commonActions test_lad_logging_config test_lad_config_all test_LadDiagnosticUtil \
                test_builtin test_lad_ext_settings; do
    python -m tests.$test
done
