REM copy OMI_error from admin\wmi\winomi\omiutils\mofs\OMI_Errors.mof, remove pragma and cim_error definition otherwise 'Stream' qualifier will be declared multiple times.
REM copy CIM-2.2.60 CIM schema (http://www.dmtf.org/standards/cim/cim_schema_v2260) to ProviderGenerationTool folder.
REM copy Convert-MofToprovider.exe to ProviderGenerationTool folder.
REM use -OldRcPath to retain old rc resource numbers
"convert-moftoprovider.exe" ^
   -MofFile LinuxEncryptionCompliance.mof ^
            MSFT_DSCResource.mof ^
            OMI_Errors.mof ^
   -ClassList LinuxEncryptionCompliance ^
   -IncludePath CIM-2.26.0 ^
   -ExtraClass OMI_Error ^
               MSFT_DSCResource ^
   -OutPath LinuxEncryptionCompliance