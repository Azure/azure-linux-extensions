from datetime import datetime
import os
import threading

class Event:
    '''
         The agent will only pick the first 3K - 3072 characters.
         Rest of the characters would be discarded from the messages
    '''

    def __init__(self, level, message, task_name, operation_id, version):
        self.version = version
        self.timestamp = datetime.utcnow().isoformat()
        self.task_name = task_name
        self.event_level = level
        self.message = message
        self.event_pid = str(os.getpid())
        self.event_tid = str(threading.get_ident()).zfill(8)
        self.operation_id = operation_id
    
    def convertToDictionary(self):
        return dict(Version = self.version, Timestamp = self.timestamp, TaskName = self.task_name, EventLevel = self.event_level, Message = self.message, EventPid = self.event_pid, EventTid = self.event_tid, OperationId = self.operation_id)    
    
