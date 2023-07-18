from datetime import datetime
import os
import threading

class Event:
    '''
         The agent will only pick the first 3K - 3072 characters.
         Rest of the characters would be discarded from the messages
    '''

    def __init__(self, level: str, message: str, task_name: str, operation_id: str, version: str):
        self.version = version
        self.timestamp = datetime.utcnow().isoformat()
        self.task_name = task_name
        self.event_level = level
        self.message = message
        self.event_pid = str(os.getpid())
        self.event_tid = str(threading.get_ident()).zfill(8)
        self.operation_id = operation_id
    
    def convertToDictionary(self):
        return dict(version = self.version, timestamp = self.timestamp, task_name = self.task_name, event_level = self.event_level, message = self.message, event_pid = self.event_pid, event_tid = self.event_tid, operation_id = self.operation_id)    
    
