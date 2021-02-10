REM ================================================================================
REM File:       postOracleMaster.sql
REM Date:       16-Sep 2020
REM Type:       Oracle SQL*Plus script
REM Author:     Microsoft CAE team
REM
REM Description:
REM             Oracle SQL*Plus script called as an Azure Backup "post" script to
REM             run immediately following a backup snapshot.
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
REM Attempt to put the database into BACKUP mode, which will succeed only if the
REM database is presently in ARCHIVELOG mode
REM ********************************************************************************

DECLARE
        v_errcontext    varchar2(128);
        noArchiveLog    exception;
        notInBackup     exception;
        pragma          exception_init(noArchiveLog, -1123);
        pragma          exception_init(notInBackup, -1142);
BEGIN
        --
        v_errcontext := 'azmessage-1';
        sysbackup.azmessage('INFO - AzBackup post-script: END BACKUP starting...');
        --
        v_errcontext := 'END BACKUP';
        execute immediate 'ALTER DATABASE END BACKUP';
        --
        v_errcontext := 'azmessage-2';
        sysbackup.azmessage('INFO - AzBackup post-script: END BACKUP succeeded');
        --
EXCEPTION
        when noArchiveLog then
                sysbackup.azmessage('INFO - AzBackup post-script: END BACKUP in NOARCHIVELOG failed, no action required');
        when notInBackup then
                sysbackup.azmessage('WARN - AzBackup post-script: END BACKUP failed - no datafiles in backup');
        when others then
                sysbackup.azmessage('FAIL - AzBackup post-script: ' || v_errcontext || ' failed');
                raise;
END;
/

REM
REM ********************************************************************************
REM Exit from Oracle SQL*Plus with SUCCESS exit status...
REM ********************************************************************************

EXIT SUCCESS