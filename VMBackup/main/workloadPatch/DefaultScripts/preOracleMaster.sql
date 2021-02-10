REM ================================================================================
REM File:       preOracleMaster.sql
REM Date:       16-Sep 2020
REM Type:       Oracle SQL*Plus script
REM Author:     Microsoft CAE team
REM
REM Description:
REM             Oracle SQL*Plus script called as an Azure Backup "pre" script, to
REM             be run immediately prior to a backup snapshot.
REM
REM             SQL*Plus is executed in RESTRICTED LEVEL 2 mode, which means that
REM             commands like HOST and SPOOL are not permitted, but commands like
REM             START are permitted.
REM ================================================================================
REM
REM ********************************************************************************
REM Format standard output to be terse...
REM ********************************************************************************

SET ECHO OFF FEEDBACK OFF TIMING OFF PAGESIZE 0 LINESIZE 130 TRIMOUT ON TRIMSPOOL ON

REM
REM ********************************************************************************
REM Uncomment the following SET command to make commands, status feedback, and
REM timings visible for debugging...
REM ********************************************************************************

REM SET ECHO ON FEEDBACK ON TIMING ON

REM
REM ********************************************************************************
REM Connect this SQL*Plus session to the current database instance as SYSBACKUP...
REM (be sure to leave one blank line before the CONNECT command)
REM ********************************************************************************

CONNECT / AS SYSBACKUP

REM
REM ********************************************************************************
REM Retrieve the status of the Oracle database instance, and exit from SQL*Plus
REM with SUCCESS exit status if database instance is not OPEN...
REM ********************************************************************************

WHENEVER OSERROR EXIT SUCCESS
WHENEVER SQLERROR EXIT SUCCESS
COL STATUS NEW_VALUE V_STATUS
SELECT 'STATUS='||STATUS AS STATUS FROM V$INSTANCE;
EXEC IF '&&V_STATUS' <> 'STATUS=OPEN' THEN RAISE NOT_LOGGED_ON; END IF;

REM
REM ********************************************************************************
REM Next, if SQL*Plus hasn't exited as a result of the last command, now ensure that
REM the failure of any command results in a FAILURE exit status from SQL*Plus...
REM ********************************************************************************

WHENEVER OSERROR EXIT FAILURE
WHENEVER SQLERROR EXIT FAILURE

REM
REM ********************************************************************************
REM Display the LOG_MODE of the database to be captured by the calling Python code...
REM ********************************************************************************

SELECT 'LOG_MODE='||LOG_MODE AS LOG_MODE FROM V$DATABASE;

REM
REM ********************************************************************************
REM Enable emitting DBMS_OUTPUT to standard output...
REM ********************************************************************************

SET SERVEROUTPUT ON SIZE 1000000

REM
REM ********************************************************************************
REM Force a switch of the online redo logfiles, which will force a full checkpoint,
REM and then archive the current logfile...
REM ********************************************************************************

DECLARE
        --
        v_errcontext            varchar2(128);
        noArchiveLogMode        exception;
        pragma                  exception_init(noArchiveLogMode, -258);
        --
BEGIN
        --
        v_errcontext := 'azmessage-1';
        sysbackup.azmessage('INFO - AzBackup pre-script: starting ARCHIVE LOG CURRENT...');
        --
        v_errcontext := 'ARCHIVE LOG CURRENT';
        execute immediate 'ALTER SYSTEM ARCHIVE LOG CURRENT';
        --
        v_errcontext := 'azmessage-2';
        sysbackup.azmessage('INFO - AzBackup pre-script: ARCHIVE LOG CURRENT succeeded');
        --
EXCEPTION
        --
        when noArchiveLogMode then
                begin
                        --
                        v_errcontext := 'azmessage-3';
                        sysbackup.azmessage('INFO - AzBackup pre-script: starting SWITCH LOGFILE...');
                        --
                        v_errcontext := 'SWITCH LOGFILE';
                        execute immediate 'ALTER SYSTEM SWITCH LOGFILE';
                        --
                        v_errcontext := 'azmessage-4';
                        sysbackup.azmessage('INFO - AzBackup pre-script: SWITCH LOGFILE succeeded');
                        --
                exception
                        when others then
                                sysbackup.azmessage('FAIL - AzBackup pre-script: ' || v_errcontext || ' failed');
                                raise;
                end;
        --
        when others then
                sysbackup.azmessage('FAIL - AzBackup pre-script: ' || v_errcontext || ' failed');
                raise;
        --
END;
/

REM
REM ********************************************************************************
REM Attempt to put the database into BACKUP mode, which will succeed only if the
REM database is presently in ARCHIVELOG mode
REM ********************************************************************************

DECLARE
        --
        v_errcontext            varchar2(128);
        noArchiveLogMode        exception;
        pragma                  exception_init(noArchiveLogMode, -1123);
        --
BEGIN
        --
        v_errcontext := 'azmessage-5';
        sysbackup.azmessage('INFO - AzBackup pre-script: BEGIN BACKUP starting...');
        --
        v_errcontext := 'BEGIN BACKUP';
        execute immediate 'ALTER DATABASE BEGIN BACKUP';
        --
        v_errcontext := 'azmessage-6';
        sysbackup.azmessage('INFO - AzBackup pre-script: BEGIN BACKUP succeeded');
        --
EXCEPTION
        --
        when noArchiveLogMode then
                --
                sysbackup.azmessage('INFO - AzBackup pre-script: BEGIN BACKUP in NOARCHIVELOG failed - no action needed...');
        --
        when others then
                sysbackup.azmessage('FAIL - AzBackup pre-script: ' || v_errcontext || ' failed');
                raise;
        --
END;
/

REM
REM ********************************************************************************
REM Exit from Oracle SQL*Plus with SUCCESS exit status...
REM ********************************************************************************

EXIT SUCCESS