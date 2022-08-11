1. 'LinuxEncryptionCompliance.mof' defines the class schema for the DSC resource for ADE/HBE. It includes a 'reasons' property which is defined in 'Audit_Reason' file. 
2. The codegen.cmd file is used to generate the skeleton code for DSC resource module in C/C++. Below were the updates made to the generated skeleton code. 
	-The business logic for ADE/HBE detection is implemented in the 'LinuxEncryptionCompliance.cpp' file.
	-The 'Audit_Reason' file defines the schema for the 'reasons' property which will display the reason for non-compliance to users through Guest Config RP. 
	-The CMakeLists.txt file needs to be updated whenever a new build dependency is added to artifact.
3. No other class/file in the generated skeleton code needs to be updated, unless necessary. 
