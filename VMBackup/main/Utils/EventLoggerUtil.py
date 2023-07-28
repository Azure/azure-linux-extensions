import os
import threading
import json
import datetime
import time
import queue
import shutil
from Utils.LogHelper import FileHelpers,LoggingConstants
from Utils.StringHelper import StringHelper
from Utils.Event import Event

class EventLogger:
    _instance = None
    _lock = threading.Lock()
    
    
    def __init__(self, log, event_directory, severity_level):
        self.temporary_directory = os.path.join(event_directory, 'Temp')
        self.space_available_in_event_directory = 0
        self.event_processing_interval = 0
        self.logger = log
        self.disposed = False
        self.event_processing_task = None  
        self.current_message_len = 0
        self.event_logging_enabled = False
        self.event_logging_error_count = 0
        self.events_folder = event_directory
        self.event_logging_enabled = bool(self.events_folder)

        if self.event_logging_enabled:
            self.extension_version = os.path.basename(os.getcwd())
            self.operation_id = ''
            self.log_severity_level = severity_level
            print("Information: EventLogging severity level setting is ",self.log_severity_level)
			# creating a temp directory
            os.makedirs(self.temporary_directory, exist_ok=True)
            FileHelpers.clearOldJsonFilesInDirectory(self.temporary_directory)

            FileHelpers.clearOldJsonFilesInDirectory(self.events_folder)
            
            self.event_processing_signal = threading.Event() # an event object that runs continuously until signal is set
            self.current_message = ''
            self.event_queue = queue.Queue()
            
			
            space_available = LoggingConstants.MaxEventDirectorySize - FileHelpers.getSizeOfDir(self.events_folder)
            self.space_available_in_event_directory = max(0, space_available)
            print(f"Information: Space available in event directory : {self.space_available_in_event_directory}B")
            
            self.event_processing_interval = LoggingConstants.MinEventProcesingInterval
            print(f"Information: Setting event reporting interval to {self.event_processing_interval}s")
            
            self.begin_event_queue_polling()
        else:
            print("Warning: EventsFolder parameter is empty. Guest Agent does not support event logging.")
            
    @staticmethod
    def GetInstance(log, event_directory, severity_level):
        if EventLogger._instance is None:
            with EventLogger._lock:
                if EventLogger._instance is None:

                    EventLogger._instance = EventLogger(log, event_directory, severity_level)
        return EventLogger._instance
        
    def update_properties(self, task_id):
        self.operation_id = task_id

    def trace_message(self, message):
        if self.event_logging_enabled:
            self.trace_message_new("Info", message)

    def trace_message_logs(self, message_logs):
        if self.event_logging_enabled:
            if message_logs:
                for message_log in message_logs:
                    self.trace_message("Verbose", message_log)

    def trace_message_new(self, severity_level, message, *args):
        level = 0
        print("inside trace_message_new")
        if (severity_level == "Verbose"):
            level = 0
        elif (severity_level == "Info"):
            level = 1
        elif (severity_level == "Warning"):
            level = 2
        elif(severity_level == "Error"):
            level = 3

        if self.event_logging_enabled and level >= self.log_severity_level:
            stringhelper = StringHelper()
            message = stringhelper.resolve_string(severity_level, message)
            try:
                message_len = len(message)
                message_max_len = LoggingConstants.MaxMessageLenLimit
                
                if message_len > message_max_len:
                    num_chunks = (message_len + message_max_len - 1) // message_max_len
                    msg_date_time = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
                    
                    for string_part in range(num_chunks):
                        start_index = string_part * message_max_len
                        length = min(message_max_len, message_len - start_index)
                        message_part = f'{msg_date_time} [{string_part + 1}/{num_chunks}] {message[start_index:start_index+length]}'
                        self.log_event(message_part)
                else:
                    self.log_event(message)
            except Exception as ex:
                self.event_logging_error_count += 1
                if self.event_logging_error_count > 10:
                    self.event_logging_enabled = False
                    print("Warning: Count(EventLoggingErrors) > 10. Disabling eventLogging. Continue with execution")
                    print(f"Exception: {ex}")

    def log_event(self, message):
        try:
            if self.current_message_len + len(message) > LoggingConstants.MaxMessageLengthPerEvent:
                self.event_queue.put(Event("Info",
                                           self.current_message, LoggingConstants.DefaultEventTaskName,
                                           self.operation_id, self.extension_version).convertToDictionary())
                # Reset the current message
                self.current_message = message
                self.current_message_len = len(message)
            else:
                self.current_message += "\n" + message
                self.current_message_len += len(message)
        except Exception as ex:
            print("Warning: Error adding extension event to queue. Exception: " + str(ex))

    def begin_event_queue_polling(self):
        print("Event polling is starting...")
        self.event_processing_task = threading.Thread(target=self._event_processing_loop)
        self.event_processing_task.start()
        

    def _event_processing_loop(self):
        while not self.event_processing_signal.wait(self.event_processing_interval):
            try:
                self._process_events()
            except Exception as ex:
                print("Warning: Event processing has failed. Exception: " + str(ex))
        print("Information: Exiting function polling...")

    def _process_events(self):
        print("in process event")
        if self.space_available_in_event_directory == 0:
            # There is no space available in the events directory then a check is made to see if space has been
            # created (no files). If there is space available we reset our flags and proceed with processing.
            if not os.listdir(self.events_folder):
                self.space_available_in_event_directory = LoggingConstants.MaxEventDirectorySize
                print("Information: Event directory has space for new event files. Resuming event reporting.")
            else:
                return
        if not self.event_queue.empty():
            event_file_path = os.path.join(self.temporary_directory, f"{int(datetime.datetime.utcnow().timestamp() * 1000000000)}.json")
            with self._create_event_file(event_file_path) as file:
                if file is None:
                    print("Warning: Could not create the event file in the path mentioned.")
                    return
                print("Information: Clearing out event queue for processing...")
                old_queue = self.event_queue
                self.event_queue = queue.Queue()
                self._write_events_to_event_file(file, old_queue, event_file_path)

            self._send_event_file_to_event_directory(event_file_path, self.events_folder, self.space_available_in_event_directory)

    def _create_event_file(self, event_file_path):
        print("Information: Attempting to create a new event file...")
        success_msg = f"Successfully created new event file: {event_file_path}"
        retry_msg = f"Failed to write events to file: {event_file_path}. Retrying..."
        err_msg = f"Failed to write events to file {event_file_path} after {LoggingConstants.MaxAttemptsForEventFileCreationWriteMove} attempts. No longer retrying. Events for this iteration will not be reported."

        stream_writer = FileHelpers.execute_with_retries(
            LoggingConstants.MaxAttemptsForEventFileCreationWriteMove,
            LoggingConstants.ThreadSleepDuration,
            success_msg,
            retry_msg,
            err_msg,
            lambda: open(event_file_path, "w")
        )
        
        return stream_writer

    @staticmethod
    def _write_events_to_event_file(file, events, event_file_path):
        data_list = []
        '''while not events.empty():
            data = events.get()
            data_list.append(data)
        json_data = json.dumps(data_list)
        '''
        while not events.empty():
            data = events.get()
            data_list.append(data)
        json_data = json.dumps(data_list)
        if not json_data:
            print("Warning: Unable to serialize events. Events for this iteration will not be reported.")
            return

        success_msg = f"Successfully wrote events to file: {event_file_path}"
        retry_msg = f"Failed to write events to file: {event_file_path}. Retrying..."
        err_msg = f"Failed to write events to file: {event_file_path} after {LoggingConstants.MaxAttemptsForEventFileCreationWriteMove} attempts. No longer retrying. Events for this iteration will not be reported."
        
        FileHelpers.execute_with_retries(
            LoggingConstants.MaxAttemptsForEventFileCreationWriteMove,
            LoggingConstants.ThreadSleepDuration,
            success_msg,
            retry_msg,
            err_msg,
            lambda: file.write(json_data)
        )

    @staticmethod
    def _send_event_file_to_event_directory(file_path, events_folder, space_available_in_event_directory):
        file_info = os.stat(file_path)
        file_size = file_info.st_size

        if space_available_in_event_directory - file_size >= 0:
            new_path_for_event_file = os.path.join(events_folder, os.path.basename(file_path))
            success_msg = f"Successfully moved event file to event directory: {new_path_for_event_file}"
            retry_msg = f"Unable to move event file to event directory: {file_path}. Retrying..."
            err_msg = f"Unable to move event file to event directory: {file_path}. No longer retrying. Events for this iteration will not be reported."

            was_file_created = FileHelpers.execute_with_retries(
                LoggingConstants.MaxAttemptsForEventFileCreationWriteMove,
                LoggingConstants.ThreadSleepDuration,
                success_msg,
                retry_msg,
                err_msg,
                lambda: shutil.move(file_path, new_path_for_event_file)
            )

            if not was_file_created:
                FileHelpers.delete_file(file_path)
            else:
                space_available_in_event_directory -= file_size
        else:
            space_available_in_event_directory = 0
            FileHelpers.delete_file(file_path)
            print("Information: Event reporting has paused due to reaching maximum capacity in the Event directory. Reporting will resume once space is available. Events for this iteration will not be reported.")

    def dispose(self):
        print("Information: Dispose(), called on EventLogger. Event processing is terminating...")
        self._dispose(True)

    def _dispose(self, disposing):
        try:
            if not self.disposed:
                if disposing and self.event_logging_enabled:
                    self.event_processing_signal.set()
                    self.event_processing_task.join()
                    self.event_processing_signal.clear()
                    if (self.current_message != ''):
                        self.event_queue.put(Event("Info", self.current_message, LoggingConstants.DefaultEventTaskName, self.operation_id, self.extension_version).convertToDictionary())
                    if not self.event_queue.empty():
                        try:
                            self._process_events()
                            self.current_message = ''
                            self.dispose()
                        except Exception as ex:
                            print("Warning: Unable to process events before termination of extension. Exception: " + str(ex))
                self.disposed = True
                print("Information: Event Logger has terminated")
                self.event_logging_enabled = False
        except Exception as ex:
            print("Warning: Processing Dispose() of EventLogger resulted in Exception: " + str(ex))
    
    @staticmethod
    def delete_file(file_path):
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                print(f"Information: Successfully deleted file: {file_path}")
            except Exception as ex:
                print(f"Warning: Failed to delete file {file_path}. Exception: {str(ex)}")
        else:
            print(f"Error: Attempted to delete non-existent file: {file_path}")


