import os
import datetime
import shutil
import time
from enum import Enum

class LoggingConstants:
    MaxDayAgeOfStaleFiles = -1  # We don't store unprocessed files beyond 1 day from current processing time
    LogFileWriteRetryAttempts = 3
    LogFileWriteRetryTime = 500  # milliseconds
    MaxAttemptsForEventFileCreationWriteMove = 3
    MinEventProcesingInterval = 10  # 10 seconds
    ThreadSleepDuration = 10  # 10 seconds
    MaxEventDirectorySize = 39981250  # ~= 39Mb
    MaxEventsPerRun = 300
    MaxMessageLenLimit = 2900  # 3072 to be precise
    MaxMessageLengthPerEvent = 3000  # 3072 to be precise
    DefaultEventTaskName = "Enable"
    # ToDo: The third param-TaskName is by default set to "Enable". We can add a mechanism to send the program file name
    LogLevelSettingFile = "LogSeverity.json"
    DefaultEventLogLevel = 2
    AllLogEnabledLevel = 0

class LoggingLevel:
    def __init__(self, event_log_level):
        self.EventLogLevel = event_log_level
        
class Severity(Enum):
    Verbose = 0
    Info = 1
    Warning = 2
    Error = 3

class FileHelpers:
    @staticmethod
    def getSizeOfDir(path):
        total_size = 0
        for root, dirs, files in os.walk(path):
            for file in files:
                file_path = os.path.join(root, file)
                total_size += os.path.getsize(file_path)
        return total_size

    @staticmethod
    def deleteFile(file_path):
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                print("Information: Successfully deleted file: {0}".format(file_path))
            except Exception as ex:
                print("Warning: Failed to delete file {0}. Exception: {1}".format(file_path, str(ex)))
        else:
            print("Error: Attempted to delete non-existent file: {0}".format(file_path))

    @staticmethod
    def deleteDirectory(directory_path):
        if os.path.exists(directory_path):
            try:
                shutil.rmtree(directory_path)
                print("Information: Successfully deleted directory: {0}".format(directory_path))
            except Exception as ex:
                print("Warning: Failed to delete directory {0}. Exception: {1}".format(directory_path, str(ex)))
        else:
            print("Error: Attempted to delete non-existent directory: {0}".format(directory_path))

    @staticmethod
    def clearOldJsonFilesInDirectory(file_path):
        try:
            current_time = datetime.datetime.now()
            max_day_age = datetime.timedelta(days=LoggingConstants.MaxDayAgeOfStaleFiles)
            files_deleted = 0
            for root, dirs, files in os.walk(file_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    last_write_time = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
                    if last_write_time < current_time + max_day_age:
                        try:
                            os.remove(file_path)
                            files_deleted += 1
                        except Exception as ex:
                            print("Warning: Failed to delete old JSON file {0}. Exception: {1}".format(file_path))
            print("Information: Cleared {0} day old JSON files in directory at path {1}, NumberOfFilesRemoved/NumberOfJSONFilesPresent = {2}/{3}".format(LoggingConstants.MaxDayAgeOfStaleFiles, file_path, files_deleted, len(files)))
        except Exception as ex:
            print("Warning: Failed to delete old JSON files at path {0}. Exception: {1}".format(file_path, str(ex)))

    def execute_with_retries(self, max_attempts, delay, success_msg, retry_msg, err_msg, operation):
        attempts = 0
        while attempts < max_attempts:
            try:
                result = operation()
                print("Information: " + success_msg)
                return result
            except Exception as ex:
                attempts += 1
                print("Warning: {0}, Exception: {1}".format(retry_msg, str(ex)))
                if attempts < max_attempts:
                    time.sleep(delay)
    
        print("Warning: " + err_msg)
        return None:q