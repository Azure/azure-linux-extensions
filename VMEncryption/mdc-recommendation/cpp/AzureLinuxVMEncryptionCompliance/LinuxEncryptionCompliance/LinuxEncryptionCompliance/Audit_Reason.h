/* @migen@ */
/*
**==============================================================================
**
** WARNING: THIS FILE WAS AUTOMATICALLY GENERATED. PLEASE DO NOT EDIT.
**
**==============================================================================
*/
#ifndef _Audit_Reason_h
#define _Audit_Reason_h

#include <MI.h>

/*
**==============================================================================
**
** Audit_Reason [Audit_Reason]
**
** Keys:
**
**==============================================================================
*/

typedef struct _Audit_Reason
{
    MI_Instance __instance;
    /* Audit_Reason properties */
    MI_ConstStringField Phrase;
    MI_ConstStringField Code;
}
Audit_Reason;

typedef struct _Audit_Reason_Ref
{
    Audit_Reason* value;
    MI_Boolean exists;
    MI_Uint8 flags;
}
Audit_Reason_Ref;

typedef struct _Audit_Reason_ConstRef
{
    MI_CONST Audit_Reason* value;
    MI_Boolean exists;
    MI_Uint8 flags;
}
Audit_Reason_ConstRef;

typedef struct _Audit_Reason_Array
{
    struct _Audit_Reason** data;
    MI_Uint32 size;
}
Audit_Reason_Array;

typedef struct _Audit_Reason_ConstArray
{
    struct _Audit_Reason MI_CONST* MI_CONST* data;
    MI_Uint32 size;
}
Audit_Reason_ConstArray;

typedef struct _Audit_Reason_ArrayRef
{
    Audit_Reason_Array value;
    MI_Boolean exists;
    MI_Uint8 flags;
}
Audit_Reason_ArrayRef;

typedef struct _Audit_Reason_ConstArrayRef
{
    Audit_Reason_ConstArray value;
    MI_Boolean exists;
    MI_Uint8 flags;
}
Audit_Reason_ConstArrayRef;

MI_EXTERN_C MI_CONST MI_ClassDecl Audit_Reason_rtti;

MI_INLINE MI_Result MI_CALL Audit_Reason_Construct(
    _Out_ Audit_Reason* self,
    _In_ MI_Context* context)
{
    return MI_Context_ConstructInstance(context, &Audit_Reason_rtti,
        (MI_Instance*)&self->__instance);
}

MI_INLINE MI_Result MI_CALL Audit_Reason_Clone(
    _In_ const Audit_Reason* self,
    _Outptr_ Audit_Reason** newInstance)
{
    return MI_Instance_Clone(
        &self->__instance, (MI_Instance**)newInstance);
}

MI_INLINE MI_Boolean MI_CALL Audit_Reason_IsA(
    _In_ const MI_Instance* self)
{
    MI_Boolean res = MI_FALSE;
    return MI_Instance_IsA(self, &Audit_Reason_rtti, &res) == MI_RESULT_OK && res;
}

MI_INLINE MI_Result MI_CALL Audit_Reason_Destruct(_Inout_ Audit_Reason* self)
{
    return MI_Instance_Destruct(&self->__instance);
}

MI_INLINE MI_Result MI_CALL Audit_Reason_Delete(_Inout_ Audit_Reason* self)
{
    return MI_Instance_Delete(&self->__instance);
}

MI_INLINE MI_Result MI_CALL Audit_Reason_Post(
    _In_ const Audit_Reason* self,
    _In_ MI_Context* context)
{
    return MI_Context_PostInstance(context, &self->__instance);
}

MI_INLINE MI_Result MI_CALL Audit_Reason_Set_Phrase(
    _Inout_ Audit_Reason* self,
    _In_z_ const MI_Char* str)
{
    return self->__instance.ft->SetElementAt(
        (MI_Instance*)&self->__instance,
        0,
        (MI_Value*)&str,
        MI_STRING,
        0);
}

MI_INLINE MI_Result MI_CALL Audit_Reason_SetPtr_Phrase(
    _Inout_ Audit_Reason* self,
    _In_z_ const MI_Char* str)
{
    return self->__instance.ft->SetElementAt(
        (MI_Instance*)&self->__instance,
        0,
        (MI_Value*)&str,
        MI_STRING,
        MI_FLAG_BORROW);
}

MI_INLINE MI_Result MI_CALL Audit_Reason_Clear_Phrase(
    _Inout_ Audit_Reason* self)
{
    return self->__instance.ft->ClearElementAt(
        (MI_Instance*)&self->__instance,
        0);
}

MI_INLINE MI_Result MI_CALL Audit_Reason_Set_Code(
    _Inout_ Audit_Reason* self,
    _In_z_ const MI_Char* str)
{
    return self->__instance.ft->SetElementAt(
        (MI_Instance*)&self->__instance,
        1,
        (MI_Value*)&str,
        MI_STRING,
        0);
}

MI_INLINE MI_Result MI_CALL Audit_Reason_SetPtr_Code(
    _Inout_ Audit_Reason* self,
    _In_z_ const MI_Char* str)
{
    return self->__instance.ft->SetElementAt(
        (MI_Instance*)&self->__instance,
        1,
        (MI_Value*)&str,
        MI_STRING,
        MI_FLAG_BORROW);
}

MI_INLINE MI_Result MI_CALL Audit_Reason_Clear_Code(
    _Inout_ Audit_Reason* self)
{
    return self->__instance.ft->ClearElementAt(
        (MI_Instance*)&self->__instance,
        1);
}


#endif /* _Audit_Reason_h */
