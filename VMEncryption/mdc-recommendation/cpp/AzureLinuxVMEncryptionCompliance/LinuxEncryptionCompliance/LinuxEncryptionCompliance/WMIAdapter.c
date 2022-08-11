/* @migen@ */
#include <windows.h>
#include <stdlib.h>
#include <mi.h>

#define STR_HELPERDLLNAME L"wmitomi.dll"
#define STR_REGISTERDLL "Adapter_RegisterDLL"
#define STR_UNREGISTERDLL "Adapter_UnRegisterDLL"
#define STR_DLLCANUNLOADNOW "Adapter_DllCanUnloadNow"
#define STR_DLLGETCLASSOBJECT "Adapter_DllGetClassObject"

typedef MI_Module* (MI_MAIN_CALL * fnMI_Main)(_In_ MI_Server* server);
typedef HRESULT (__stdcall * fnRegisterDLL)(HINSTANCE module, GUID classId);
typedef HRESULT (__stdcall * fnUnRegisterDLL)(GUID classId);
typedef HRESULT (__stdcall * fnDllCanUnloadNow)(void);
typedef HRESULT (__stdcall * fnDllGetClassObject)(CLSID supportedClassIds,
    fnMI_Main main,
    REFCLSID rclsid,
    REFIID riid,
    LPVOID * ppv);

// Helper DLL module handle
volatile HMODULE g_hHelper = NULL;

// Main provider entry point for MI provider. The framework
// needs to call into this to get all run time type information.
MI_EXTERN_C MI_Module* MI_MAIN_CALL MI_Main(_In_ MI_Server* server);

// DLL module handle, needed for COM registration
HINSTANCE g_hModule = NULL;

// Unique provider ID
// {6BD33B25-350E-49F3-97DC-E4169D53EAF9}
CLSID g_providerClassID = { 0x6bd33b25, 0x350e, 0x49f3, { 0x97, 0xdc, 0xe4, 0x16, 0x9d, 0x53, 0xea, 0xf9 } };

// DllMain is needed to get the module handle for registration.
EXTERN_C BOOL WINAPI DllMain(_In_ HINSTANCE hInstance,
                             _In_ ULONG ulReason,
                             _In_opt_ LPVOID pvReserved)
{
    MI_UNREFERENCED_PARAMETER(pvReserved);

    if (DLL_PROCESS_ATTACH == ulReason)
    {
        DisableThreadLibraryCalls(hInstance);
        g_hModule = hInstance;
    }
    else if (DLL_PROCESS_DETACH == ulReason)
    {
        if(g_hHelper)
        {
            FreeLibrary(g_hHelper);
        }
    }
    return TRUE;
}

// Retrieve provider class ID
STDAPI GetProviderClassID(_Out_ CLSID * classId)
{
    if (classId == NULL)
    {
        return ERROR_INVALID_PARAMETER;
    }
    memcpy(classId, &g_providerClassID, sizeof(g_providerClassID));
    return NO_ERROR;
}

// Get helper dll full path
wchar_t * GetHelperDllFullPath()
{
    int nRet;
    wchar_t pwszSysDir[MAX_PATH];
    wchar_t * pwszFullDllPath = NULL;
    pwszSysDir[0] = L'\0';
    nRet = GetSystemDirectoryW(pwszSysDir, MAX_PATH);
    if (nRet == 0 || nRet > MAX_PATH)
    {
        return NULL;
    }
    pwszFullDllPath = (wchar_t *)malloc(sizeof(wchar_t) * MAX_PATH);
    if (pwszFullDllPath == NULL)
    {
        return NULL;
    }
    nRet = swprintf_s(pwszFullDllPath, MAX_PATH, L"%s\\%s", pwszSysDir, STR_HELPERDLLNAME);
    if (nRet == -1)
    {
        free(pwszFullDllPath);
        return NULL;
    }
    return pwszFullDllPath;
}

// Load helper DLL
HRESULT LoadHelperDLL()
{
    if(InterlockedCompareExchangePointer((volatile PVOID *)&g_hHelper, NULL, NULL) == NULL)
    {
        wchar_t * pwszFullDllPath;
        HMODULE hHelper;
        pwszFullDllPath = GetHelperDllFullPath();
        if (NULL == pwszFullDllPath)
        {
            return E_FAIL;
        }
        hHelper = LoadLibraryExW(pwszFullDllPath, NULL, 0);
        free(pwszFullDllPath);
        if (NULL == hHelper)
        {
            return HRESULT_FROM_WIN32(GetLastError());
        }
        if (InterlockedCompareExchangePointer((volatile PVOID *)&g_hHelper, hHelper, NULL) != NULL)
        {
            FreeLibrary(hHelper);
        }
    }
    return S_OK;
}

// Dynamically get function pointer from helper DLL
// return S_OK if successfully get the function pointer
// otherwise return error code
HRESULT GetFunctionPointer(_In_z_ LPCSTR functionName, _Outptr_ FARPROC * ppFuncPtr)
{
    HRESULT hr = S_OK;
    hr = LoadHelperDLL();
    if (SUCCEEDED(hr))
    {
        *ppFuncPtr = GetProcAddress(g_hHelper, functionName);
        if (NULL == *ppFuncPtr)
        {
            hr = HRESULT_FROM_WIN32(GetLastError());
        }
    }
    else
    {
        *ppFuncPtr = NULL;
    }
    return hr;
}

// COM Support function: Register provider
STDAPI DllRegisterServer(void)
{
    fnRegisterDLL fpRegisterDLL = NULL;
    HRESULT hr = GetFunctionPointer(STR_REGISTERDLL, (FARPROC*)&fpRegisterDLL);
    if (hr == S_OK)
    {
        hr = fpRegisterDLL(g_hModule, g_providerClassID);
    }
    return hr;
}

// COM Support function: Unregister the provider
STDAPI DllUnregisterServer(void)
{
    fnUnRegisterDLL fpUnRegisterDLL = NULL;
    HRESULT hr = GetFunctionPointer(STR_UNREGISTERDLL, (FARPROC*)&fpUnRegisterDLL);
    if (hr == S_OK)
    {
        hr = fpUnRegisterDLL(g_providerClassID);
    }
    return hr;
}

// COM Support function: Can DLL be unloaded now
STDAPI DllCanUnloadNow(void)
{
    fnDllCanUnloadNow fpDllCanUnloadNow = NULL;
    HRESULT hr = GetFunctionPointer(STR_DLLCANUNLOADNOW, (FARPROC*)&fpDllCanUnloadNow);
    if (hr == S_OK)
    {
        hr = fpDllCanUnloadNow();
    }
    return hr;
}

// COM Support function: Get the class object
STDAPI DllGetClassObject(_In_ REFCLSID rclsid,
                         _In_ REFIID riid,
                         _Outptr_result_maybenull_ LPVOID * ppv)
{
    fnDllGetClassObject fpDllGetClassObject = NULL;
    HRESULT hr = GetFunctionPointer(STR_DLLGETCLASSOBJECT, (FARPROC*)&fpDllGetClassObject);
    if (hr == S_OK)
    {
        hr = fpDllGetClassObject(g_providerClassID, MI_Main, rclsid, riid, ppv);
    }
    else
    {
        *ppv = NULL;
    }
    return hr;
}

