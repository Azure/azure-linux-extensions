The systemd process manages the lifecycle of the service, including starting, stopping, restarting, and keeping track of whether it’s running or not.

A service is registered typically by placing its .service file in /etc/systemd/system/

To start: 
sudo systemctl start <service_name>

ExecStart defines what executable or script is launched when the service starts.
Systemd spawns a child process to run the command in ExecStart

Typically, daemons write their PID to a PID file themselves (e.g., /var/run/<service>.pid) to track their process.