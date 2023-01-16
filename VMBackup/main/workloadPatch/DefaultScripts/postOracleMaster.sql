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
REM
REM Modifications:
REM     TGorman 05oct22 v0.1 - remove external dependency on AZMESSAGE procedure
REM     TGorman 13dec22 v0.2 - support for DATABASE_ROLE = 'STANDBY'
REM ================================================================================
REM
REM ********************************************************************************
REM store script version into SQL*Plus substitution variable...
REM ********************************************************************************
define V_SCRIPT_VERSION="0.2"

REM
REM ********************************************************************************
REM Format standard output to be terse...
REM ********************************************************************************

SET ECHO OFF FEEDBACK OFF TIMING OFF PAGESIZE 0 LINESIZE 130 TRIMOUT ON TRIMSPOOL ON VERIFY OFF

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
REM
REM If databases are 11g or older, then please replace the following line with
REM "CONNECT / AS SYSDBA", because the SYSBACKUP role was introduced in 12c...
REM ********************************************************************************

CONNECT / AS SYSBACKUP
REM CONNECT / AS SYSDBA

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
REM Next, if SQL*Plus has not exited as a result of the last command, now ensure that
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
REM Display the DATABASE_ROLE of the database to be captured by the calling Python code...
REM ********************************************************************************
SELECT 'DATABASE_ROLE='||database_role AS DATABASE_ROLE FROM V$DATABASE;

REM
REM ********************************************************************************
REM Enable emitting DBMS_OUTPUT to standard output...
REM ********************************************************************************

SET SERVEROUTPUT ON SIZE 1000000

REM
REM ********************************************************************************
REM Attempt to take the database out from BACKUP mode, which will succeed only if the
REM database is presently in ARCHIVELOG mode and if the database was already in
REM BACKUP mode...
REM ********************************************************************************

DECLARE
        --
        v_errcontext            varchar2(128);
        v_timestamp		varchar2(32);
	v_database_role		varchar2(32);
        noArchiveLogMode        exception;
	notInBackup		exception;
        pragma                  exception_init(noArchiveLogMode, -1123);
        pragma                  exception_init(noArchiveLogMode, -1142);
        --
BEGIN
        --
	v_errcontext := 'query DATABASE_ROLE';
	SELECT	DATABASE_ROLE
	INTO	v_database_role
	FROM	V$DATABASE;
	--
	if v_database_role = 'PRIMARY' then
		--
		v_errcontext := 'END BACKUP';
		SELECT TO_CHAR(SYSDATE, 'YYYY-MM-DD HH24:MI:SS')
		INTO v_timestamp FROM DUAL;
		DBMS_OUTPUT.PUT_LINE(v_timestamp || ' - INFO - AzBackup post-script v&&V_SCRIPT_VERSION: starting ' || v_errcontext || '...');
		SYS.DBMS_SYSTEM.KSDWRT(SYS.DBMS_SYSTEM.ALERT_FILE, 'INFO - AzBackup post-script v&&V_SCRIPT_VERSION: starting ' || v_errcontext || '...');
        	--
		execute immediate 'ALTER DATABASE END BACKUP';
		--
		SELECT TO_CHAR(SYSDATE, 'YYYY-MM-DD HH24:MI:SS')
		INTO v_timestamp FROM DUAL;
		DBMS_OUTPUT.PUT_LINE(v_timestamp || ' - INFO - AzBackup post-script v&&V_SCRIPT_VERSION: ' || v_errcontext || ' succeeded');
		SYS.DBMS_SYSTEM.KSDWRT(SYS.DBMS_SYSTEM.ALERT_FILE, 'INFO - AzBackup post-script v&&V_SCRIPT_VERSION: ' || v_errcontext || ' succeeded');
        	--
	end if;
        --
EXCEPTION
        --
        when noArchiveLogMode then
                --
		SELECT TO_CHAR(SYSDATE, 'YYYY-MM-DD HH24:MI:SS')
		INTO v_timestamp FROM DUAL;
		DBMS_OUTPUT.PUT_LINE(v_timestamp || ' - INFO - AzBackup post-script v&&V_SCRIPT_VERSION: ' || v_errcontext || ' in NOARCHIVELOG failed - continuing backup...');
		SYS.DBMS_SYSTEM.KSDWRT(SYS.DBMS_SYSTEM.ALERT_FILE, 'INFO - AzBackup post-script v&&V_SCRIPT_VERSION: ' || v_errcontext || ' in NOARCHIVELOG failed - continuing backup...');
	--
        when notInBackup then
		SELECT TO_CHAR(SYSDATE, 'YYYY-MM-DD HH24:MI:SS')
		INTO v_timestamp FROM DUAL;
		DBMS_OUTPUT.PUT_LINE(v_timestamp || ' - WARN - AzBackup post-script v&&V_SCRIPT_VERSION: ' || v_errcontext || ' failed as no datafiles in BACKUP mode - continuing backup...');
		SYS.DBMS_SYSTEM.KSDWRT(SYS.DBMS_SYSTEM.ALERT_FILE, 'WARN - AzBackup post-script v&&V_SCRIPT_VERSION: ' || v_errcontext || ' failed as no datafiles in BACKUP mode - continuing backup...');
        --
        when others then
		SELECT TO_CHAR(SYSDATE, 'YYYY-MM-DD HH24:MI:SS')
		INTO v_timestamp FROM DUAL;
		DBMS_OUTPUT.PUT_LINE(v_timestamp || ' - FAIL - AzBackup post-script v&&V_SCRIPT_VERSION: ' || v_errcontext || '  failed');
		SYS.DBMS_SYSTEM.KSDWRT(SYS.DBMS_SYSTEM.ALERT_FILE, 'FAIL - AzBackup post-script v&&V_SCRIPT_VERSION: ' || v_errcontext || ' failed');
                raise;
        --
END;
/

REM 
REM ********************************************************************************
REM Force a switch of the online redo logfiles, which will force a full checkpoint,
REM and then archive the current logfile...
REM ********************************************************************************

DECLARE
        --
        v_errcontext            varchar2(128);
        v_timestamp		varchar2(32);
	v_database_role		varchar2(32);
        noArchiveLogMode        exception;
        pragma                  exception_init(noArchiveLogMode, -258);
        --
BEGIN
        --
	v_errcontext := 'query DATABASE_ROLE';
	SELECT	DATABASE_ROLE
	INTO	v_database_role
	FROM	V$DATABASE;
	--
	if v_database_role = 'PRIMARY' then
		--
        	v_errcontext := 'ARCHIVE LOG CURRENT';
		SELECT TO_CHAR(SYSDATE, 'YYYY-MM-DD HH24:MI:SS')
		INTO v_timestamp FROM DUAL;
		DBMS_OUTPUT.PUT_LINE(v_timestamp || ' - INFO - AzBackup post-script v&&V_SCRIPT_VERSION: starting ' || v_errcontext || '...');
		SYS.DBMS_SYSTEM.KSDWRT(SYS.DBMS_SYSTEM.ALERT_FILE, 'INFO - AzBackup post-script v&&V_SCRIPT_VERSION: starting ' || v_errcontext || '...');
        	--
        	execute immediate 'ALTER SYSTEM ARCHIVE LOG CURRENT';
        	--
		SELECT TO_CHAR(SYSDATE, 'YYYY-MM-DD HH24:MI:SS')
		INTO v_timestamp FROM DUAL;
		DBMS_OUTPUT.PUT_LINE(v_timestamp || ' - INFO - AzBackup post-script v&&V_SCRIPT_VERSION: ' || v_errcontext || ' succeeded');
		SYS.DBMS_SYSTEM.KSDWRT(SYS.DBMS_SYSTEM.ALERT_FILE, 'INFO - AzBackup post-script v&&V_SCRIPT_VERSION: ' || v_errcontext || ' succeeded');
		--
	end if;
        --
EXCEPTION
        --
        when noArchiveLogMode then
                begin
                        --
        		v_errcontext := 'SWITCH LOGFILE';
			SELECT TO_CHAR(SYSDATE, 'YYYY-MM-DD HH24:MI:SS')
			INTO v_timestamp FROM DUAL;
			DBMS_OUTPUT.PUT_LINE(v_timestamp || ' - INFO - AzBackup post-script v&&V_SCRIPT_VERSION: starting ' || v_errcontext || '...');
			SYS.DBMS_SYSTEM.KSDWRT(SYS.DBMS_SYSTEM.ALERT_FILE, 'INFO - AzBackup post-script v&&V_SCRIPT_VERSION: starting ' || v_errcontext || '...');
                        --
                        execute immediate 'ALTER SYSTEM SWITCH LOGFILE';
                        --
			SELECT TO_CHAR(SYSDATE, 'YYYY-MM-DD HH24:MI:SS')
			INTO v_timestamp FROM DUAL;
			DBMS_OUTPUT.PUT_LINE(v_timestamp || ' - INFO - AzBackup post-script v&&V_SCRIPT_VERSION: ' || v_errcontext || ' succeeded');
			SYS.DBMS_SYSTEM.KSDWRT(SYS.DBMS_SYSTEM.ALERT_FILE, 'INFO - AzBackup post-script v&&V_SCRIPT_VERSION: ' || v_errcontext || ' succeeded');
                        --
                exception
                        when others then
				SELECT TO_CHAR(SYSDATE, 'YYYY-MM-DD HH24:MI:SS')
				INTO v_timestamp FROM DUAL;
				DBMS_OUTPUT.PUT_LINE(v_timestamp || ' - FAIL - AzBackup post-script v&&V_SCRIPT_VERSION: ' || v_errcontext || ' failed');
				SYS.DBMS_SYSTEM.KSDWRT(SYS.DBMS_SYSTEM.ALERT_FILE, 'FAIL - AzBackup post-script v&&V_SCRIPT_VERSION: ' || v_errcontext || ' failed');
                                raise;
                end;
        --
        when others then
		SELECT TO_CHAR(SYSDATE, 'YYYY-MM-DD HH24:MI:SS')
		INTO v_timestamp FROM DUAL;
		DBMS_OUTPUT.PUT_LINE(v_timestamp || ' - FAIL - AzBackup post-script v&&V_SCRIPT_VERSION: ' || v_errcontext || ' failed');
		SYS.DBMS_SYSTEM.KSDWRT(SYS.DBMS_SYSTEM.ALERT_FILE, 'FAIL - AzBackup post-script v&&V_SCRIPT_VERSION: ' || v_errcontext || ' failed');
                raise;
        --
END;
/

REM
REM ********************************************************************************
REM Exit from Oracle SQL*Plus with SUCCESS exit status...
REM ********************************************************************************

EXIT SUCCESS
