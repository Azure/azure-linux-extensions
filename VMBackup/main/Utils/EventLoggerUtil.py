import os
import threading
import json
import sys
import datetime
import time
import uuid
if sys.version_info[0] == 2:
    import Queue as queue
else:
    # if python version is > 3
    import queue
import shutil
from Utils.LogHelper import FileHelpers,LoggingConstants,Severity
from Utils.StringHelper import StringHelper
from Utils.Event import Event

class EventLogger:
    _instance = None
    _lock = threading.Lock()
    
    
    def __init__(self, event_directory, severity_level):
        self.temporary_directory = os.path.join(event_directory, 'Temp')
        self.space_available_in_event_directory = 0
        self.event_processing_interval = 0
        self.disposed = False
        self.event_processing_task = None  
        self.current_message_len = 0
        self.event_logging_enabled = False
        self.event_logging_error_count = 0
        self.events_folder = event_directory
        self.event_logging_enabled = bool(self.events_folder)
        self.filehelper = FileHelpers()

        if self.event_logging_enabled:
            self.extension_version = os.path.basename(os.getcwd())
            self.operation_id = uuid.UUID(int=0)
            self.log_severity_level = severity_level
            print("Information: EventLogging severity level setting is ",self.log_severity_level)
			# creating a temp directory
            if not os.path.exists(self.temporary_directory):
                os.makedirs(self.temporary_directory)
            FileHelpers.clearOldJsonFilesInDirectory(self.temporary_directory)

            FileHelpers.clearOldJsonFilesInDirectory(self.events_folder)
            
            self.event_processing_signal = threading.Event() # an event object that runs continuously until signal is set
            self.current_message = ''
            self.event_queue = queue.Queue()
            
			
            space_available = LoggingConstants.MaxEventDirectorySize - FileHelpers.getSizeOfDir(self.events_folder)
            self.space_available_in_event_directory = max(0, space_available)
            print("Information: Space available in event directory : %sB" %(self.space_available_in_event_directory))
            
            self.event_processing_interval = LoggingConstants.MinEventProcesingInterval
            print("Information: Setting event reporting interval to %ss" %(self.event_processing_interval))
            
            self.begin_event_queue_polling()
        else:
            print("Warning: EventsFolder parameter is empty. Guest Agent does not support event logging.")
            
    @staticmethod
    def GetInstance(self, backup_logger, event_directory, severity_level):
        try:
            self.logger = backup_logger
            if EventLogger._instance is None:
                with EventLogger._lock:
                    if EventLogger._instance is None:
                        EventLogger._instance = EventLogger(event_directory, severity_level)
        except Exception as e:
            self.logger.log("Exception has occurred {0}".format(str(e)))
        return EventLogger._instance
        
    def update_properties(self, task_id):
        self.operation_id = task_id

    def severity(self, severity_level):
        level = 0
        level = Severity[severity_level].value
        return level

    def trace_message(self, severity_level, message):
      
        level = self.severity(severity_level)
        if self.event_logging_enabled and level >= self.log_severity_level:
            stringhelper = StringHelper()
            message = stringhelper.resolve_string(severity_level, message)
            try:
                message_len = len(message)
                message_max_len = LoggingConstants.MaxMessageLenLimit
                
                if message_len > message_max_len:
                    num_chunks = (message_len + message_max_len - 1) // message_max_len
                    msg_date_time = datetime.datetime.utcnow().strftime(u'%Y-%m-%dT%H:%M:%S.%fZ')
                    
                    for string_part in range(num_chunks):
                        start_index = string_part * message_max_len
                        length = min(message_max_len, message_len - start_index)
                        message_part = '%s [%d/%d] %s' % (msg_date_time, string_part + 1, num_chunks, message[start_index:start_index+length])
                        self.log_event(message_part)
                else:
                    self.log_event(message)
            except Exception as ex:
                self.event_logging_error_count += 1
                if self.event_logging_error_count > 10:
                    self.event_logging_enabled = False
                    print("Warning: Count(EventLoggingErrors) > 10. Disabling eventLogging. Continue with execution")
                    print("Exception: %s" %(str(ex)))

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
                self.current_message += message
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
            if sys.version_info[0] == 2:
                event_file_path = os.path.join(self.temporary_directory, "{}.json".format(int(time.time() * 1000000000)))
            else:
                event_file_path = os.path.join(self.temporary_directory, "{}.json".format(int(datetime.datetime.utcnow().timestamp() * 1000000000)))
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
        success_msg = "Successfully created new event file: %s" % event_file_path
        retry_msg = "Failed to write events to file: %s. Retrying..." % event_file_path
        err_msg = "Failed to write events to file %s after %d attempts. No longer retrying. Events for this iteration will not be reported." % (event_file_path, LoggingConstants.MaxAttemptsForEventFileCreationWriteMove)

        stream_writer = self.filehelper.execute_with_retries(
            LoggingConstants.MaxAttemptsForEventFileCreationWriteMove,
            LoggingConstants.ThreadSleepDuration,
            success_msg,
            retry_msg,
            err_msg,
            lambda: open(event_file_path, "w")
        )
        
        return stream_writer

    def _write_events_to_event_file(self, file, events, event_file_path):
        data_list = []
        while not events.empty():
            data = events.get()
            data_list.append(data)
        json_data = json.dumps(data_list)
        if not json_data:
            print("Warning: Unable to serialize events. Events for this iteration will not be reported.")
            return

        success_msg = "Successfully wrote events to file: %s" % event_file_path
        retry_msg = "Failed to write events to file: %s. Retrying..." % event_file_path
        err_msg = "Failed to write events to file %s after %d attempts. No longer retrying. Events for this iteration will not be reported." % (event_file_path, LoggingConstants.MaxAttemptsForEventFileCreationWriteMove)

        self.filehelper.execute_with_retries(
            LoggingConstants.MaxAttemptsForEventFileCreationWriteMove,
            LoggingConstants.ThreadSleepDuration,
            success_msg,
            retry_msg,
            err_msg,
            lambda: file.write(json_data)
        )

    def _send_event_file_to_event_directory(self, file_path, events_folder, space_available_in_event_directory):
        file_info = os.stat(file_path)
        file_size = file_info.st_size

        if space_available_in_event_directory - file_size >= 0:
            new_path_for_event_file = os.path.join(events_folder, os.path.basename(file_path))
            success_msg = "Successfully moved event file to event directory: %s" % new_path_for_event_file
            retry_msg = "Unable to move event file to event directory: %s. Retrying..." % file_path
            err_msg = "Unable to move event file to event directory: %s . No longer retrying. Events for this iteration will not be reported." % file_path

            self.filehelper.execute_with_retries(
                LoggingConstants.MaxAttemptsForEventFileCreationWriteMove,
                LoggingConstants.ThreadSleepDuration,
                success_msg,
                retry_msg,
                err_msg,
                lambda: shutil.move(file_path, new_path_for_event_file)
            )

            space_available_in_event_directory -= file_size
        else:
            space_available_in_event_directory = 0
            FileHelpers.deleteFile(file_path)
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