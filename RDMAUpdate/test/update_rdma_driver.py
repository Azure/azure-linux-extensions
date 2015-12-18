import subprocess, re, os

def RunGetOutput(cmd,chk_err=True):
	try:
		output=subprocess.check_output(cmd,stderr=subprocess.STDOUT,shell=True)
	except subprocess.CalledProcessError,e :
		if chk_err :
			print('CalledProcessError.  Error Code is ' + str(e.returncode)  )
			print('CalledProcessError.  Command string was ' + e.cmd  )
			print('CalledProcessError.  Command result was ' + (e.output[:-1]).decode('latin-1'))
		return e.returncode,e.output.decode('latin-1')
	return 0,output.decode('latin-1')
#def

def InstallRDMADriver(host_version) :

	#make sure we have the correct repo configured
	error, output = RunGetOutput("zypper lr -u")
	if not re.search("msft-rdma-pack", output) :
		RunGetOutput("zypper ar https://drivers.suse.com/microsoft/Microsoft-LIS-RDMA/sle-12/updates msft-rdma-pack")

	#install the wrapper package, that will put the driver RPM packages under /opt/microsoft/rdma
	RunGetOutput("zypper --non-interactive install --force msft-rdma-drivers")

	#install the driver RPM package
	r = os.listdir("/opt/microsoft/rdma")
	if r :
		for filename in r :
			if re.match("msft-lis-rdma-kmp-default-\d{8}\.(%s).+" % host_version, filename) :
				print "Installing RPM /opt/microsoft/rdma/" + filename
				RunGetOutput("zypper --non-interactive install --force /opt/microsoft/rdma/%s" % filename)
				return

	print "RDMA drivers not found in /opt/microsoft/rdma"
#def

#1. check if kvp daemon is running, if not install it and reboot
error, output = RunGetOutput("ps -ef")	# how about error != 0
r = re.search("hv_kvp_daemon", output)
if not r :
	print "KVP deamon is not running, install it"
	RunGetOutput("zypper --non-interactive install --force hyper-v")
	RunGetOutput("reboot")
else :
	print "KVP deamon is running"


#2. get the host ND version
f = open("/var/lib/hyperv/.kvp_pool_0", "r")
lines = f.read();
f.close()

r = re.match("NdDriverVersion\0+(\d\d\d\.\d)", lines)
if r :
	NdDriverVersion = r.groups()[0]
	print "ND version = " + NdDriverVersion		#e.g. NdDriverVersion = 142.0
else :
	print "Error: NdDriverVersion not found. Abort"
	exit()


#3. if the ND version doesn't match the RDMA driver package version, do an update
error, output = RunGetOutput("zypper --non-interactive info msft-lis-rdma-kmp-default")

r = re.search("Version:\s+(\S+)", output)
if r :
	package_version = r.groups()[0]		# e.g. package_version is "20151119.142.0_k3.12.28_4-1.1"
	print "msft-lis-rdma-kmp-default package version = " + package_version

	r = re.match("\d{8}\.(%s).+" % NdDriverVersion, package_version)	# NdDriverVersion should be at the end of package version
	if not r :	#host ND version is the same as the package version, do an update
		print "ND and package version don't match, doing an update"
		RunGetOutput("zypper --non-interactive remove msft-lis-rdma-kmp-default")
		InstallRDMADriver(NdDriverVersion)
		RunGetOutput("reboot")
	else :
		print "ND and package version match, not doing an update"

else :
	print "msft-lis-rdma-kmp-default not found, installing new version"

	InstallRDMADriver(NdDriverVersion)
	RunGetOutput("reboot");
