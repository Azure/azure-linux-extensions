import os
import datetime
import shutil
import time

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

    @staticmethod
    def clearOldFilesInDirectory(directory, extension, file_limit):
        """
        Deletes older files if the number of files with the given extension exceeds the file_limit.
        
        Parameters:
        directory (str): The directory to clean up.
        extension (str): The file extension to filter (e.g., ".status", ".settings").
        file_limit (int): Maximum allowed number of files with the given extension.
        """
        try:
            # Ensure the directory exists
            if not os.path.isdir(directory):
                print("Directory '{0}' does not exist.".format(directory))
                return

            # Collect all files with the specified extension
            files_with_ext = [
                os.path.join(directory, f)
                for f in os.listdir(directory)
                if f.endswith(extension) and os.path.isfile(os.path.join(directory, f))
            ]

            # Sort the files by modification time (oldest first)
            files_with_ext.sort(key=lambda f: os.path.getmtime(f))

            # Check if the number of files exceeds the limit
            if len(files_with_ext) > file_limit:
                files_to_delete = files_with_ext[:len(files_with_ext) - file_limit]

                # Delete the excess files
                for file in files_to_delete:
                    try:
                        os.remove(file)
                        print("Deleted: {0}".format(file))
                    except Exception as e:
                        print("Error deleting {0}: {1}".format(file, str(e)))
            else:
                print("No files need to be deleted. Total files ({0}) are within the limit.".format(len(files_with_ext)))
        
        except Exception as e:
            print("An unexpected error occurred while clearing old files: {0}".format(str(e)))

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
        return None