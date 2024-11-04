class NodeBasedConstants:

    service_name = "Microsoft.Azure.RecoveryServices.VMSnapshotLinux.service"
    config_section = 'NodeBasedService'
    pid_file = "VMSnapshotLinux.pid"

    HOST_IP_ADDRESS = "168.63.129.16"

    GET_SNAPSHOT_REQUESTS_URI = "http://{}/xdisksvc/snapshotrequest".format(HOST_IP_ADDRESS)
    START_SNAPSHOT_REQUESTS_URI = "http://{}/xdisksvc/startsnapshots".format(HOST_IP_ADDRESS)
    END_SNAPSHOT_REQUESTS_URI = "http://{}/xdisksvc/endsnapshots".format(HOST_IP_ADDRESS)

    SERVICE_POLLING_INTERVAL_IN_SECS = 300
    EXTENSION_TIMEOUT_IN_MINS = 10