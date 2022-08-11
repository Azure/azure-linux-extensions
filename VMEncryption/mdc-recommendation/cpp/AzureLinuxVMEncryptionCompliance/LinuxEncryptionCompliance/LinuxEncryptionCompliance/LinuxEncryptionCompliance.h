/* @migen@ */
/*
**==============================================================================
**
** WARNING: THIS FILE WAS AUTOMATICALLY GENERATED. PLEASE DO NOT EDIT.
**
**==============================================================================
*/
#ifndef _LinuxEncryptionCompliance_h
#define _LinuxEncryptionCompliance_h

#include <MI.h>
#include "OMI_BaseResource.h"
#include "MSFT_Credential.h"
#include "Audit_Reason.h"
#include "LinuxEncryptionCompliance.h"

/*
**==============================================================================
**
** LinuxEncryptionCompliance [LinuxEncryptionCompliance]
**
** Keys:
**    PolicyName
**
**==============================================================================
*/

typedef struct _LinuxEncryptionCompliance /* extends OMI_BaseResource */
{
    MI_Instance __instance;
    /* OMI_BaseResource properties */
    MI_ConstStringField ResourceId;
    MI_ConstStringField SourceInfo;
    MI_ConstStringAField DependsOn;
    MI_ConstStringField ModuleName;
    MI_ConstStringField ModuleVersion;
    MI_ConstStringField ConfigurationName;
    MSFT_Credential_ConstRef PsDscRunAsCredential;
    /* LinuxEncryptionCompliance properties */
    /*KEY*/ MI_ConstStringField PolicyName;
    Audit_Reason_ConstArrayRef Reasons;
}
LinuxEncryptionCompliance;

typedef struct _LinuxEncryptionCompliance_Ref
{
    LinuxEncryptionCompliance* value;
    MI_Boolean exists;
    MI_Uint8 flags;
}
LinuxEncryptionCompliance_Ref;

typedef struct _LinuxEncryptionCompliance_ConstRef
{
    MI_CONST LinuxEncryptionCompliance* value;
    MI_Boolean exists;
    MI_Uint8 flags;
}
LinuxEncryptionCompliance_ConstRef;

typedef struct _LinuxEncryptionCompliance_Array
{
    struct _LinuxEncryptionCompliance** data;
    MI_Uint32 size;
}
LinuxEncryptionCompliance_Array;

typedef struct _LinuxEncryptionCompliance_ConstArray
{
    struct _LinuxEncryptionCompliance MI_CONST* MI_CONST* data;
    MI_Uint32 size;
}
LinuxEncryptionCompliance_ConstArray;

typedef struct _LinuxEncryptionCompliance_ArrayRef
{
    LinuxEncryptionCompliance_Array value;
    MI_Boolean exists;
    MI_Uint8 flags;
}
LinuxEncryptionCompliance_ArrayRef;

typedef struct _LinuxEncryptionCompliance_ConstArrayRef
{
    LinuxEncryptionCompliance_ConstArray value;
    MI_Boolean exists;
    MI_Uint8 flags;
}
LinuxEncryptionCompliance_ConstArrayRef;

MI_EXTERN_C MI_CONST MI_ClassDecl LinuxEncryptionCompliance_rtti;

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_Construct(
    _Out_ LinuxEncryptionCompliance* self,
    _In_ MI_Context* context)
{
    return MI_Context_ConstructInstance(context, &LinuxEncryptionCompliance_rtti,
        (MI_Instance*)&self->__instance);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_Clone(
    _In_ const LinuxEncryptionCompliance* self,
    _Outptr_ LinuxEncryptionCompliance** newInstance)
{
    return MI_Instance_Clone(
        &self->__instance, (MI_Instance**)newInstance);
}

MI_INLINE MI_Boolean MI_CALL LinuxEncryptionCompliance_IsA(
    _In_ const MI_Instance* self)
{
    MI_Boolean res = MI_FALSE;
    return MI_Instance_IsA(self, &LinuxEncryptionCompliance_rtti, &res) == MI_RESULT_OK && res;
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_Destruct(_Inout_ LinuxEncryptionCompliance* self)
{
    return MI_Instance_Destruct(&self->__instance);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_Delete(_Inout_ LinuxEncryptionCompliance* self)
{
    return MI_Instance_Delete(&self->__instance);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_Post(
    _In_ const LinuxEncryptionCompliance* self,
    _In_ MI_Context* context)
{
    return MI_Context_PostInstance(context, &self->__instance);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_Set_ResourceId(
    _Inout_ LinuxEncryptionCompliance* self,
    _In_z_ const MI_Char* str)
{
    return self->__instance.ft->SetElementAt(
        (MI_Instance*)&self->__instance,
        0,
        (MI_Value*)&str,
        MI_STRING,
        0);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_SetPtr_ResourceId(
    _Inout_ LinuxEncryptionCompliance* self,
    _In_z_ const MI_Char* str)
{
    return self->__instance.ft->SetElementAt(
        (MI_Instance*)&self->__instance,
        0,
        (MI_Value*)&str,
        MI_STRING,
        MI_FLAG_BORROW);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_Clear_ResourceId(
    _Inout_ LinuxEncryptionCompliance* self)
{
    return self->__instance.ft->ClearElementAt(
        (MI_Instance*)&self->__instance,
        0);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_Set_SourceInfo(
    _Inout_ LinuxEncryptionCompliance* self,
    _In_z_ const MI_Char* str)
{
    return self->__instance.ft->SetElementAt(
        (MI_Instance*)&self->__instance,
        1,
        (MI_Value*)&str,
        MI_STRING,
        0);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_SetPtr_SourceInfo(
    _Inout_ LinuxEncryptionCompliance* self,
    _In_z_ const MI_Char* str)
{
    return self->__instance.ft->SetElementAt(
        (MI_Instance*)&self->__instance,
        1,
        (MI_Value*)&str,
        MI_STRING,
        MI_FLAG_BORROW);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_Clear_SourceInfo(
    _Inout_ LinuxEncryptionCompliance* self)
{
    return self->__instance.ft->ClearElementAt(
        (MI_Instance*)&self->__instance,
        1);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_Set_DependsOn(
    _Inout_ LinuxEncryptionCompliance* self,
    _In_reads_opt_(size) const MI_Char** data,
    _In_ MI_Uint32 size)
{
    MI_Array arr;
    arr.data = (void*)data;
    arr.size = size;
    return self->__instance.ft->SetElementAt(
        (MI_Instance*)&self->__instance,
        2,
        (MI_Value*)&arr,
        MI_STRINGA,
        0);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_SetPtr_DependsOn(
    _Inout_ LinuxEncryptionCompliance* self,
    _In_reads_opt_(size) const MI_Char** data,
    _In_ MI_Uint32 size)
{
    MI_Array arr;
    arr.data = (void*)data;
    arr.size = size;
    return self->__instance.ft->SetElementAt(
        (MI_Instance*)&self->__instance,
        2,
        (MI_Value*)&arr,
        MI_STRINGA,
        MI_FLAG_BORROW);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_Clear_DependsOn(
    _Inout_ LinuxEncryptionCompliance* self)
{
    return self->__instance.ft->ClearElementAt(
        (MI_Instance*)&self->__instance,
        2);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_Set_ModuleName(
    _Inout_ LinuxEncryptionCompliance* self,
    _In_z_ const MI_Char* str)
{
    return self->__instance.ft->SetElementAt(
        (MI_Instance*)&self->__instance,
        3,
        (MI_Value*)&str,
        MI_STRING,
        0);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_SetPtr_ModuleName(
    _Inout_ LinuxEncryptionCompliance* self,
    _In_z_ const MI_Char* str)
{
    return self->__instance.ft->SetElementAt(
        (MI_Instance*)&self->__instance,
        3,
        (MI_Value*)&str,
        MI_STRING,
        MI_FLAG_BORROW);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_Clear_ModuleName(
    _Inout_ LinuxEncryptionCompliance* self)
{
    return self->__instance.ft->ClearElementAt(
        (MI_Instance*)&self->__instance,
        3);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_Set_ModuleVersion(
    _Inout_ LinuxEncryptionCompliance* self,
    _In_z_ const MI_Char* str)
{
    return self->__instance.ft->SetElementAt(
        (MI_Instance*)&self->__instance,
        4,
        (MI_Value*)&str,
        MI_STRING,
        0);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_SetPtr_ModuleVersion(
    _Inout_ LinuxEncryptionCompliance* self,
    _In_z_ const MI_Char* str)
{
    return self->__instance.ft->SetElementAt(
        (MI_Instance*)&self->__instance,
        4,
        (MI_Value*)&str,
        MI_STRING,
        MI_FLAG_BORROW);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_Clear_ModuleVersion(
    _Inout_ LinuxEncryptionCompliance* self)
{
    return self->__instance.ft->ClearElementAt(
        (MI_Instance*)&self->__instance,
        4);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_Set_ConfigurationName(
    _Inout_ LinuxEncryptionCompliance* self,
    _In_z_ const MI_Char* str)
{
    return self->__instance.ft->SetElementAt(
        (MI_Instance*)&self->__instance,
        5,
        (MI_Value*)&str,
        MI_STRING,
        0);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_SetPtr_ConfigurationName(
    _Inout_ LinuxEncryptionCompliance* self,
    _In_z_ const MI_Char* str)
{
    return self->__instance.ft->SetElementAt(
        (MI_Instance*)&self->__instance,
        5,
        (MI_Value*)&str,
        MI_STRING,
        MI_FLAG_BORROW);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_Clear_ConfigurationName(
    _Inout_ LinuxEncryptionCompliance* self)
{
    return self->__instance.ft->ClearElementAt(
        (MI_Instance*)&self->__instance,
        5);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_Set_PsDscRunAsCredential(
    _Inout_ LinuxEncryptionCompliance* self,
    _In_ const MSFT_Credential* x)
{
    return self->__instance.ft->SetElementAt(
        (MI_Instance*)&self->__instance,
        6,
        (MI_Value*)&x,
        MI_INSTANCE,
        0);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_SetPtr_PsDscRunAsCredential(
    _Inout_ LinuxEncryptionCompliance* self,
    _In_ const MSFT_Credential* x)
{
    return self->__instance.ft->SetElementAt(
        (MI_Instance*)&self->__instance,
        6,
        (MI_Value*)&x,
        MI_INSTANCE,
        MI_FLAG_BORROW);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_Clear_PsDscRunAsCredential(
    _Inout_ LinuxEncryptionCompliance* self)
{
    return self->__instance.ft->ClearElementAt(
        (MI_Instance*)&self->__instance,
        6);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_Set_PolicyName(
    _Inout_ LinuxEncryptionCompliance* self,
    _In_z_ const MI_Char* str)
{
    return self->__instance.ft->SetElementAt(
        (MI_Instance*)&self->__instance,
        7,
        (MI_Value*)&str,
        MI_STRING,
        0);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_SetPtr_PolicyName(
    _Inout_ LinuxEncryptionCompliance* self,
    _In_z_ const MI_Char* str)
{
    return self->__instance.ft->SetElementAt(
        (MI_Instance*)&self->__instance,
        7,
        (MI_Value*)&str,
        MI_STRING,
        MI_FLAG_BORROW);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_Clear_PolicyName(
    _Inout_ LinuxEncryptionCompliance* self)
{
    return self->__instance.ft->ClearElementAt(
        (MI_Instance*)&self->__instance,
        7);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_Set_Reasons(
    _Inout_ LinuxEncryptionCompliance* self,
    _In_reads_opt_(size) const Audit_Reason * const * data,
    _In_ MI_Uint32 size)
{
    MI_Array arr;
    arr.data = (void*)data;
    arr.size = size;
    return self->__instance.ft->SetElementAt(
        (MI_Instance*)&self->__instance,
        8,
        (MI_Value*)&arr,
        MI_INSTANCEA,
        0);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_SetPtr_Reasons(
    _Inout_ LinuxEncryptionCompliance* self,
    _In_reads_opt_(size) const Audit_Reason * const * data,
    _In_ MI_Uint32 size)
{
    MI_Array arr;
    arr.data = (void*)data;
    arr.size = size;
    return self->__instance.ft->SetElementAt(
        (MI_Instance*)&self->__instance,
        8,
        (MI_Value*)&arr,
        MI_INSTANCEA,
        MI_FLAG_BORROW);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_Clear_Reasons(
    _Inout_ LinuxEncryptionCompliance* self)
{
    return self->__instance.ft->ClearElementAt(
        (MI_Instance*)&self->__instance,
        8);
}

/*
**==============================================================================
**
** LinuxEncryptionCompliance.GetTargetResource()
**
**==============================================================================
*/

typedef struct _LinuxEncryptionCompliance_GetTargetResource
{
    MI_Instance __instance;
    /*OUT*/ MI_ConstUint32Field MIReturn;
    /*IN*/ LinuxEncryptionCompliance_ConstRef InputResource;
    /*IN*/ MI_ConstUint32Field Flags;
    /*OUT*/ LinuxEncryptionCompliance_ConstRef OutputResource;
}
LinuxEncryptionCompliance_GetTargetResource;

MI_EXTERN_C MI_CONST MI_MethodDecl LinuxEncryptionCompliance_GetTargetResource_rtti;

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_GetTargetResource_Construct(
    _Out_ LinuxEncryptionCompliance_GetTargetResource* self,
    _In_ MI_Context* context)
{
    return MI_Context_ConstructParameters(context, &LinuxEncryptionCompliance_GetTargetResource_rtti,
        (MI_Instance*)&self->__instance);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_GetTargetResource_Clone(
    _In_ const LinuxEncryptionCompliance_GetTargetResource* self,
    _Outptr_ LinuxEncryptionCompliance_GetTargetResource** newInstance)
{
    return MI_Instance_Clone(
        &self->__instance, (MI_Instance**)newInstance);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_GetTargetResource_Destruct(
    _Inout_ LinuxEncryptionCompliance_GetTargetResource* self)
{
    return MI_Instance_Destruct(&self->__instance);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_GetTargetResource_Delete(
    _Inout_ LinuxEncryptionCompliance_GetTargetResource* self)
{
    return MI_Instance_Delete(&self->__instance);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_GetTargetResource_Post(
    _In_ const LinuxEncryptionCompliance_GetTargetResource* self,
    _In_ MI_Context* context)
{
    return MI_Context_PostInstance(context, &self->__instance);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_GetTargetResource_Set_MIReturn(
    _Inout_ LinuxEncryptionCompliance_GetTargetResource* self,
    _In_ MI_Uint32 x)
{
    ((MI_Uint32Field*)&self->MIReturn)->value = x;
    ((MI_Uint32Field*)&self->MIReturn)->exists = 1;
    return MI_RESULT_OK;
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_GetTargetResource_Clear_MIReturn(
    _Inout_ LinuxEncryptionCompliance_GetTargetResource* self)
{
    memset((void*)&self->MIReturn, 0, sizeof(self->MIReturn));
    return MI_RESULT_OK;
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_GetTargetResource_Set_InputResource(
    _Inout_ LinuxEncryptionCompliance_GetTargetResource* self,
    _In_ const LinuxEncryptionCompliance* x)
{
    return self->__instance.ft->SetElementAt(
        (MI_Instance*)&self->__instance,
        1,
        (MI_Value*)&x,
        MI_INSTANCE,
        0);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_GetTargetResource_SetPtr_InputResource(
    _Inout_ LinuxEncryptionCompliance_GetTargetResource* self,
    _In_ const LinuxEncryptionCompliance* x)
{
    return self->__instance.ft->SetElementAt(
        (MI_Instance*)&self->__instance,
        1,
        (MI_Value*)&x,
        MI_INSTANCE,
        MI_FLAG_BORROW);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_GetTargetResource_Clear_InputResource(
    _Inout_ LinuxEncryptionCompliance_GetTargetResource* self)
{
    return self->__instance.ft->ClearElementAt(
        (MI_Instance*)&self->__instance,
        1);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_GetTargetResource_Set_Flags(
    _Inout_ LinuxEncryptionCompliance_GetTargetResource* self,
    _In_ MI_Uint32 x)
{
    ((MI_Uint32Field*)&self->Flags)->value = x;
    ((MI_Uint32Field*)&self->Flags)->exists = 1;
    return MI_RESULT_OK;
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_GetTargetResource_Clear_Flags(
    _Inout_ LinuxEncryptionCompliance_GetTargetResource* self)
{
    memset((void*)&self->Flags, 0, sizeof(self->Flags));
    return MI_RESULT_OK;
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_GetTargetResource_Set_OutputResource(
    _Inout_ LinuxEncryptionCompliance_GetTargetResource* self,
    _In_ const LinuxEncryptionCompliance* x)
{
    return self->__instance.ft->SetElementAt(
        (MI_Instance*)&self->__instance,
        3,
        (MI_Value*)&x,
        MI_INSTANCE,
        0);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_GetTargetResource_SetPtr_OutputResource(
    _Inout_ LinuxEncryptionCompliance_GetTargetResource* self,
    _In_ const LinuxEncryptionCompliance* x)
{
    return self->__instance.ft->SetElementAt(
        (MI_Instance*)&self->__instance,
        3,
        (MI_Value*)&x,
        MI_INSTANCE,
        MI_FLAG_BORROW);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_GetTargetResource_Clear_OutputResource(
    _Inout_ LinuxEncryptionCompliance_GetTargetResource* self)
{
    return self->__instance.ft->ClearElementAt(
        (MI_Instance*)&self->__instance,
        3);
}

/*
**==============================================================================
**
** LinuxEncryptionCompliance.TestTargetResource()
**
**==============================================================================
*/

typedef struct _LinuxEncryptionCompliance_TestTargetResource
{
    MI_Instance __instance;
    /*OUT*/ MI_ConstUint32Field MIReturn;
    /*IN*/ LinuxEncryptionCompliance_ConstRef InputResource;
    /*IN*/ MI_ConstUint32Field Flags;
    /*OUT*/ MI_ConstBooleanField Result;
    /*OUT*/ MI_ConstUint64Field ProviderContext;
}
LinuxEncryptionCompliance_TestTargetResource;

MI_EXTERN_C MI_CONST MI_MethodDecl LinuxEncryptionCompliance_TestTargetResource_rtti;

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_TestTargetResource_Construct(
    _Out_ LinuxEncryptionCompliance_TestTargetResource* self,
    _In_ MI_Context* context)
{
    return MI_Context_ConstructParameters(context, &LinuxEncryptionCompliance_TestTargetResource_rtti,
        (MI_Instance*)&self->__instance);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_TestTargetResource_Clone(
    _In_ const LinuxEncryptionCompliance_TestTargetResource* self,
    _Outptr_ LinuxEncryptionCompliance_TestTargetResource** newInstance)
{
    return MI_Instance_Clone(
        &self->__instance, (MI_Instance**)newInstance);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_TestTargetResource_Destruct(
    _Inout_ LinuxEncryptionCompliance_TestTargetResource* self)
{
    return MI_Instance_Destruct(&self->__instance);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_TestTargetResource_Delete(
    _Inout_ LinuxEncryptionCompliance_TestTargetResource* self)
{
    return MI_Instance_Delete(&self->__instance);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_TestTargetResource_Post(
    _In_ const LinuxEncryptionCompliance_TestTargetResource* self,
    _In_ MI_Context* context)
{
    return MI_Context_PostInstance(context, &self->__instance);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_TestTargetResource_Set_MIReturn(
    _Inout_ LinuxEncryptionCompliance_TestTargetResource* self,
    _In_ MI_Uint32 x)
{
    ((MI_Uint32Field*)&self->MIReturn)->value = x;
    ((MI_Uint32Field*)&self->MIReturn)->exists = 1;
    return MI_RESULT_OK;
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_TestTargetResource_Clear_MIReturn(
    _Inout_ LinuxEncryptionCompliance_TestTargetResource* self)
{
    memset((void*)&self->MIReturn, 0, sizeof(self->MIReturn));
    return MI_RESULT_OK;
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_TestTargetResource_Set_InputResource(
    _Inout_ LinuxEncryptionCompliance_TestTargetResource* self,
    _In_ const LinuxEncryptionCompliance* x)
{
    return self->__instance.ft->SetElementAt(
        (MI_Instance*)&self->__instance,
        1,
        (MI_Value*)&x,
        MI_INSTANCE,
        0);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_TestTargetResource_SetPtr_InputResource(
    _Inout_ LinuxEncryptionCompliance_TestTargetResource* self,
    _In_ const LinuxEncryptionCompliance* x)
{
    return self->__instance.ft->SetElementAt(
        (MI_Instance*)&self->__instance,
        1,
        (MI_Value*)&x,
        MI_INSTANCE,
        MI_FLAG_BORROW);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_TestTargetResource_Clear_InputResource(
    _Inout_ LinuxEncryptionCompliance_TestTargetResource* self)
{
    return self->__instance.ft->ClearElementAt(
        (MI_Instance*)&self->__instance,
        1);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_TestTargetResource_Set_Flags(
    _Inout_ LinuxEncryptionCompliance_TestTargetResource* self,
    _In_ MI_Uint32 x)
{
    ((MI_Uint32Field*)&self->Flags)->value = x;
    ((MI_Uint32Field*)&self->Flags)->exists = 1;
    return MI_RESULT_OK;
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_TestTargetResource_Clear_Flags(
    _Inout_ LinuxEncryptionCompliance_TestTargetResource* self)
{
    memset((void*)&self->Flags, 0, sizeof(self->Flags));
    return MI_RESULT_OK;
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_TestTargetResource_Set_Result(
    _Inout_ LinuxEncryptionCompliance_TestTargetResource* self,
    _In_ MI_Boolean x)
{
    ((MI_BooleanField*)&self->Result)->value = x;
    ((MI_BooleanField*)&self->Result)->exists = 1;
    return MI_RESULT_OK;
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_TestTargetResource_Clear_Result(
    _Inout_ LinuxEncryptionCompliance_TestTargetResource* self)
{
    memset((void*)&self->Result, 0, sizeof(self->Result));
    return MI_RESULT_OK;
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_TestTargetResource_Set_ProviderContext(
    _Inout_ LinuxEncryptionCompliance_TestTargetResource* self,
    _In_ MI_Uint64 x)
{
    ((MI_Uint64Field*)&self->ProviderContext)->value = x;
    ((MI_Uint64Field*)&self->ProviderContext)->exists = 1;
    return MI_RESULT_OK;
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_TestTargetResource_Clear_ProviderContext(
    _Inout_ LinuxEncryptionCompliance_TestTargetResource* self)
{
    memset((void*)&self->ProviderContext, 0, sizeof(self->ProviderContext));
    return MI_RESULT_OK;
}

/*
**==============================================================================
**
** LinuxEncryptionCompliance.SetTargetResource()
**
**==============================================================================
*/

typedef struct _LinuxEncryptionCompliance_SetTargetResource
{
    MI_Instance __instance;
    /*OUT*/ MI_ConstUint32Field MIReturn;
    /*IN*/ LinuxEncryptionCompliance_ConstRef InputResource;
    /*IN*/ MI_ConstUint64Field ProviderContext;
    /*IN*/ MI_ConstUint32Field Flags;
}
LinuxEncryptionCompliance_SetTargetResource;

MI_EXTERN_C MI_CONST MI_MethodDecl LinuxEncryptionCompliance_SetTargetResource_rtti;

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_SetTargetResource_Construct(
    _Out_ LinuxEncryptionCompliance_SetTargetResource* self,
    _In_ MI_Context* context)
{
    return MI_Context_ConstructParameters(context, &LinuxEncryptionCompliance_SetTargetResource_rtti,
        (MI_Instance*)&self->__instance);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_SetTargetResource_Clone(
    _In_ const LinuxEncryptionCompliance_SetTargetResource* self,
    _Outptr_ LinuxEncryptionCompliance_SetTargetResource** newInstance)
{
    return MI_Instance_Clone(
        &self->__instance, (MI_Instance**)newInstance);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_SetTargetResource_Destruct(
    _Inout_ LinuxEncryptionCompliance_SetTargetResource* self)
{
    return MI_Instance_Destruct(&self->__instance);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_SetTargetResource_Delete(
    _Inout_ LinuxEncryptionCompliance_SetTargetResource* self)
{
    return MI_Instance_Delete(&self->__instance);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_SetTargetResource_Post(
    _In_ const LinuxEncryptionCompliance_SetTargetResource* self,
    _In_ MI_Context* context)
{
    return MI_Context_PostInstance(context, &self->__instance);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_SetTargetResource_Set_MIReturn(
    _Inout_ LinuxEncryptionCompliance_SetTargetResource* self,
    _In_ MI_Uint32 x)
{
    ((MI_Uint32Field*)&self->MIReturn)->value = x;
    ((MI_Uint32Field*)&self->MIReturn)->exists = 1;
    return MI_RESULT_OK;
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_SetTargetResource_Clear_MIReturn(
    _Inout_ LinuxEncryptionCompliance_SetTargetResource* self)
{
    memset((void*)&self->MIReturn, 0, sizeof(self->MIReturn));
    return MI_RESULT_OK;
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_SetTargetResource_Set_InputResource(
    _Inout_ LinuxEncryptionCompliance_SetTargetResource* self,
    _In_ const LinuxEncryptionCompliance* x)
{
    return self->__instance.ft->SetElementAt(
        (MI_Instance*)&self->__instance,
        1,
        (MI_Value*)&x,
        MI_INSTANCE,
        0);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_SetTargetResource_SetPtr_InputResource(
    _Inout_ LinuxEncryptionCompliance_SetTargetResource* self,
    _In_ const LinuxEncryptionCompliance* x)
{
    return self->__instance.ft->SetElementAt(
        (MI_Instance*)&self->__instance,
        1,
        (MI_Value*)&x,
        MI_INSTANCE,
        MI_FLAG_BORROW);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_SetTargetResource_Clear_InputResource(
    _Inout_ LinuxEncryptionCompliance_SetTargetResource* self)
{
    return self->__instance.ft->ClearElementAt(
        (MI_Instance*)&self->__instance,
        1);
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_SetTargetResource_Set_ProviderContext(
    _Inout_ LinuxEncryptionCompliance_SetTargetResource* self,
    _In_ MI_Uint64 x)
{
    ((MI_Uint64Field*)&self->ProviderContext)->value = x;
    ((MI_Uint64Field*)&self->ProviderContext)->exists = 1;
    return MI_RESULT_OK;
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_SetTargetResource_Clear_ProviderContext(
    _Inout_ LinuxEncryptionCompliance_SetTargetResource* self)
{
    memset((void*)&self->ProviderContext, 0, sizeof(self->ProviderContext));
    return MI_RESULT_OK;
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_SetTargetResource_Set_Flags(
    _Inout_ LinuxEncryptionCompliance_SetTargetResource* self,
    _In_ MI_Uint32 x)
{
    ((MI_Uint32Field*)&self->Flags)->value = x;
    ((MI_Uint32Field*)&self->Flags)->exists = 1;
    return MI_RESULT_OK;
}

MI_INLINE MI_Result MI_CALL LinuxEncryptionCompliance_SetTargetResource_Clear_Flags(
    _Inout_ LinuxEncryptionCompliance_SetTargetResource* self)
{
    memset((void*)&self->Flags, 0, sizeof(self->Flags));
    return MI_RESULT_OK;
}

/*
**==============================================================================
**
** LinuxEncryptionCompliance provider function prototypes
**
**==============================================================================
*/

/* The developer may optionally define this structure */
typedef struct _LinuxEncryptionCompliance_Self LinuxEncryptionCompliance_Self;

MI_EXTERN_C void MI_CALL LinuxEncryptionCompliance_Load(
    _Outptr_result_maybenull_ LinuxEncryptionCompliance_Self** self,
    _In_opt_ MI_Module_Self* selfModule,
    _In_ MI_Context* context);

MI_EXTERN_C void MI_CALL LinuxEncryptionCompliance_Unload(
    _In_opt_ LinuxEncryptionCompliance_Self* self,
    _In_ MI_Context* context);

MI_EXTERN_C void MI_CALL LinuxEncryptionCompliance_EnumerateInstances(
    _In_opt_ LinuxEncryptionCompliance_Self* self,
    _In_ MI_Context* context,
    _In_opt_z_ const MI_Char* nameSpace,
    _In_opt_z_ const MI_Char* className,
    _In_opt_ const MI_PropertySet* propertySet,
    _In_ MI_Boolean keysOnly,
    _In_opt_ const MI_Filter* filter);

MI_EXTERN_C void MI_CALL LinuxEncryptionCompliance_GetInstance(
    _In_opt_ LinuxEncryptionCompliance_Self* self,
    _In_ MI_Context* context,
    _In_opt_z_ const MI_Char* nameSpace,
    _In_opt_z_ const MI_Char* className,
    _In_ const LinuxEncryptionCompliance* instanceName,
    _In_opt_ const MI_PropertySet* propertySet);

MI_EXTERN_C void MI_CALL LinuxEncryptionCompliance_CreateInstance(
    _In_opt_ LinuxEncryptionCompliance_Self* self,
    _In_ MI_Context* context,
    _In_opt_z_ const MI_Char* nameSpace,
    _In_opt_z_ const MI_Char* className,
    _In_ const LinuxEncryptionCompliance* newInstance);

MI_EXTERN_C void MI_CALL LinuxEncryptionCompliance_ModifyInstance(
    _In_opt_ LinuxEncryptionCompliance_Self* self,
    _In_ MI_Context* context,
    _In_opt_z_ const MI_Char* nameSpace,
    _In_opt_z_ const MI_Char* className,
    _In_ const LinuxEncryptionCompliance* modifiedInstance,
    _In_opt_ const MI_PropertySet* propertySet);

MI_EXTERN_C void MI_CALL LinuxEncryptionCompliance_DeleteInstance(
    _In_opt_ LinuxEncryptionCompliance_Self* self,
    _In_ MI_Context* context,
    _In_opt_z_ const MI_Char* nameSpace,
    _In_opt_z_ const MI_Char* className,
    _In_ const LinuxEncryptionCompliance* instanceName);

MI_EXTERN_C void MI_CALL LinuxEncryptionCompliance_Invoke_GetTargetResource(
    _In_opt_ LinuxEncryptionCompliance_Self* self,
    _In_ MI_Context* context,
    _In_opt_z_ const MI_Char* nameSpace,
    _In_opt_z_ const MI_Char* className,
    _In_opt_z_ const MI_Char* methodName,
    _In_ const LinuxEncryptionCompliance* instanceName,
    _In_opt_ const LinuxEncryptionCompliance_GetTargetResource* in);

MI_EXTERN_C void MI_CALL LinuxEncryptionCompliance_Invoke_TestTargetResource(
    _In_opt_ LinuxEncryptionCompliance_Self* self,
    _In_ MI_Context* context,
    _In_opt_z_ const MI_Char* nameSpace,
    _In_opt_z_ const MI_Char* className,
    _In_opt_z_ const MI_Char* methodName,
    _In_ const LinuxEncryptionCompliance* instanceName,
    _In_opt_ const LinuxEncryptionCompliance_TestTargetResource* in);

MI_EXTERN_C void MI_CALL LinuxEncryptionCompliance_Invoke_SetTargetResource(
    _In_opt_ LinuxEncryptionCompliance_Self* self,
    _In_ MI_Context* context,
    _In_opt_z_ const MI_Char* nameSpace,
    _In_opt_z_ const MI_Char* className,
    _In_opt_z_ const MI_Char* methodName,
    _In_ const LinuxEncryptionCompliance* instanceName,
    _In_opt_ const LinuxEncryptionCompliance_SetTargetResource* in);


#endif /* _LinuxEncryptionCompliance_h */
