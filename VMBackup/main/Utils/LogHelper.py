import os
import datetime
import shutil

class LoggingConstants:
    MaxDayAgeOfStaleFiles = -1  # We don't store unprocessed files beyond 1 day from current processing time
    LogFileWriteRetryAttempts = 3
    LogFileWriteRetryTime = 500  # milliseconds
    MaxAttemptsForEventFileCreationWriteMove = 3
    MinEventProcesingInterval = 10  # 10 seconds
    ThreadSleepDuration = 10000  # 10 seconds
    MaxEventDirectorySize = 39981250  # ~= 39Mb
    MaxEventsPerRun = 300
    MaxMessageLenLimit = 32#2900  # 3072 to be precise
    MaxMessageLengthPerEvent = 34#3000  # 3072 to be precise
    DefaultEventTaskName = "Enable"
    # ToDo: The third param-TaskName is by default set to "Enable". We can add a mechanism to send the program file name
    LogLevelSettingFile = "LogSeverity.json"
    DefaultEventLogLevel = "Warning"
    AllLogEnabledLevel = "Verbose"

class LoggingLevel:
    #def __init__(self, file_log_level, event_log_level):
    def __init__(self, event_log_level):
        #self.FileLogLevel = file_log_level
        self.EventLogLevel = event_log_level

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
                print(f"Information: Successfully deleted file: {file_path}")
            except Exception as ex:
                print(f"Warning: Failed to delete file {file_path}. Exception: {ex}")
        else:
            print(f"Error: Attempted to delete non-existent file: {file_path}")

    @staticmethod
    def deleteDirectory(directory_path):
        if os.path.exists(directory_path):
            try:
                shutil.rmtree(directory_path)
                print(f"Information: Successfully deleted directory: {directory_path}")
            except Exception as ex:
                print(f"Warning: Failed to delete directory {directory_path}. Exception: {ex}")
        else:
            print(f"Error: Attempted to delete non-existent directory: {directory_path}")

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
                            print(f"Warning: Failed to delete old JSON file {file_path}. Exception: {ex}")
            print(f"Information: Cleared {LoggingConstants.MaxDayAgeOfStaleFiles} day old JSON files in directory at path {file_path}, NumberOfFilesRemoved/NumberOfJSONFilesPresent = {files_deleted}/{len(files)}")
        except Exception as ex:
            print(f"Warning: Failed to delete old JSON files at path {file_path}. Exception: {str(ex)}")

    def execute_with_retries(max_attempts, delay, success_msg, retry_msg, err_msg, operation):
        attempts = 0
        while attempts < max_attempts:
            try:
                result = operation()
                print("Information: " + success_msg)
                return result
            except Exception as ex:
                attempts += 1
                print(f"Warning: {retry_msg}, Exception: {str(ex)}")
                if attempts < max_attempts:
                    time.sleep(delay)
    
        print("Warning: " + err_msg)
        return None
