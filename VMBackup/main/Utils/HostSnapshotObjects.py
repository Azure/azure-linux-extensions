import json

class HostRequestBody:
    def __init__(self, taskId, diskIds, snapshotMetadata):
        self.taskId = taskId
        self.diskIds = diskIds
        self.snapshotMetadata = snapshotMetadata

    def convertToDictionary(self):
        return dict(taskId = self.taskId, diskIds = self.diskIds, snapshotMetadata = self.snapshotMetadata)
