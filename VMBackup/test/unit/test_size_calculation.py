"""Tests for the used size calculation reported in the backup status."""

import os
import shutil
import sys
import tempfile
import types
import unittest

from test.helpers import tools


_MAIN_DIR = os.path.join(tools.VMBACKUP_DIR, "main")
_STUBBED_MODULES = ("Utils.HandlerUtil", "Utils.DiskUtil", "Utils.ResourceDiskUtil")
_LOADED_MODULES = ("Utils", "Utils.SizeCalculation", "common") + _STUBBED_MODULES


class _HandlerUtility(object):
    telemetry = {}

    @staticmethod
    def add_to_telemetery_data(key, value):
        _HandlerUtility.telemetry[key] = value

    @staticmethod
    def split(logger, txt):
        return txt.split()


class _FakeDiskUtil(object):
    file_systems_info = []

    @staticmethod
    def get_instance(patching, logger):
        return _FakeDiskUtil()

    def get_mount_file_systems(self):
        return list(_FakeDiskUtil.file_systems_info)

    def get_device_items(self, dev_path):
        return []


class _FakeResourceDiskUtil(object):
    partition = "sdb1"

    def __init__(self, patching, logger):
        pass

    def get_resource_disk_mount_point(self, option=1):
        return _FakeResourceDiskUtil.partition


def _install_stubs():
    tools.purge_modules(*_LOADED_MODULES)
    sys.path.insert(0, _MAIN_DIR)
    import Utils
    stubs = {
        "Utils.HandlerUtil": {"HandlerUtility": _HandlerUtility},
        "Utils.DiskUtil": {"DiskUtil": _FakeDiskUtil},
        "Utils.ResourceDiskUtil": {"ResourceDiskUtil": _FakeResourceDiskUtil},
    }
    for name, attributes in stubs.items():
        module = types.ModuleType(name)
        for attribute, value in attributes.items():
            setattr(module, attribute, value)
        sys.modules[name] = module
        setattr(Utils, name.split(".")[1], module)
    import Utils.SizeCalculation
    return Utils.SizeCalculation


class _Logger(object):
    def __init__(self):
        self.messages = []

    def log(self, msg, *args, **kwargs):
        self.messages.append(msg)


class _HUtil(object):
    def get_strvalue_from_configfile(self, key, default):
        return default

    def get_intvalue_from_configfile(self, key, default):
        return default


class _ParaParser(object):
    def __init__(self, lun_list, is_any_disk_excluded):
        self.customSettings = ""
        self.includeLunList = lun_list
        self.includedDisks = {"isAnyDiskExcluded": is_any_disk_excluded}


def _df(*rows):
    lines = ["Filesystem 1024-blocks Used Available Capacity Mounted on"]
    for device, used, mountpoint in rows:
        lines.append("{0} 100000000 {1} 1000 1% {2}".format(device, used, mountpoint))
    return "\n".join(lines) + "\n"


class SizeCalculationTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.module = _install_stubs()

    @classmethod
    def tearDownClass(cls):
        tools.purge_modules(*_LOADED_MODULES)
        sys.path.remove(_MAIN_DIR)

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="vmbackup-size-test-")
        self.saved_constants = (self.module.AZURE_DISK_SYMLINK_DIR, self.module.SYS_BLOCK_DIR, self.module.DF_TIMEOUT_IN_SECONDS, self.module.PROC_MOUNTS_FILE)
        self.module.AZURE_DISK_SYMLINK_DIR = os.path.join(self.temp_dir, "azure")
        self.module.SYS_BLOCK_DIR = os.path.join(self.temp_dir, "sys", "block")
        self.module.PROC_MOUNTS_FILE = os.path.join(self.temp_dir, "proc_mounts")
        _FakeResourceDiskUtil.partition = "sdb1"
        _FakeDiskUtil.file_systems_info = []
        _HandlerUtility.telemetry = {}

    def tearDown(self):
        self.module.AZURE_DISK_SYMLINK_DIR, self.module.SYS_BLOCK_DIR, self.module.DF_TIMEOUT_IN_SECONDS, self.module.PROC_MOUNTS_FILE = self.saved_constants
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _calculator(self, lun_list, is_any_disk_excluded=False, df_output="", lsscsi=None, lsblk=None, pvs=None, lvs=None):
        calc = self.module.SizeCalculation(patching=None, hutil=_HUtil(), logger=_Logger(),
                                           para_parser=_ParaParser(lun_list, is_any_disk_excluded))
        calc.get_df_output = lambda command: df_output

        def fake_lsscsi():
            calc.lsscsi_list = lsscsi or []

        def fake_lsblk():
            calc.output_lsblk = lsblk or []

        def fake_pvs():
            calc.pvs_output = pvs or []

        def fake_lvs():
            calc.lvs_output = lvs or []

        calc.get_lsscsi_list = fake_lsscsi
        calc.get_lsblk_list = fake_lsblk
        calc.get_pvs_list = fake_pvs
        calc.get_lvs_list = fake_lvs
        return calc

    def _write(self, path, content=""):
        if not os.path.isdir(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))
        with open(path, "w") as f:
            f.write(content)

    def test_is_device_on_disk(self):
        is_on = self.module.SizeCalculation.is_device_on_disk
        self.assertTrue(is_on("/dev/sdc", "/dev/sdc"))
        self.assertTrue(is_on("/dev/sdc1", "/dev/sdc"))
        self.assertTrue(is_on("/dev/nvme0n2p1", "/dev/nvme0n2"))
        self.assertFalse(is_on("/dev/sdca1", "/dev/sdc"))
        self.assertFalse(is_on("/dev/nvme0n21", "/dev/nvme0n2"))
        self.assertFalse(is_on("/dev/mapper/rootvg-rootlv", "/dev/sda"))

    def test_get_vg_name(self):
        calc = self._calculator([0])
        calc.pvs_dict = {"datavg": ["/dev/sdc1"]}
        self.assertEqual("rootvg", calc.get_vg_name("/dev/mapper/rootvg-rootlv"))
        self.assertEqual("app-vg", calc.get_vg_name("/dev/mapper/app--vg-data--lv"))
        self.assertEqual(("app-vg", "data-lv"), calc.get_vg_lv_name("/dev/mapper/app--vg-data--lv"))
        self.assertEqual("datavg", calc.get_vg_name("/dev/datavg/lv1"))
        self.assertIsNone(calc.get_vg_name("/dev/sda1"))
        self.assertIsNone(calc.get_vg_name("/dev/mapper/nohyphen"))

    def test_local_file_systems_are_not_treated_as_network_shares(self):
        calc = self._calculator([0])
        for fstype in ("btrfs", "zfs", "fuseblk", "xfs"):
            self.assertFalse(calc.is_non_physical_fs(fstype), fstype)
        for fstype in ("nfs4", "cifs", "fuse.sshfs", "overlay", "iso9660"):
            self.assertTrue(calc.is_non_physical_fs(fstype), fstype)

    def test_temp_disk_detection_falls_back_to_dataloss_warning_file(self):
        calc = self._calculator([0])
        temp_mount = os.path.join(self.temp_dir, "resource")
        self._write(os.path.join(temp_mount, self.module.TEMP_DISK_WARNING_FILE))
        self.assertTrue(calc.is_temp_disk("/dev/sdb1", "/mnt/resource", "/dev/sdb1"))
        self.assertFalse(calc.is_temp_disk("/dev/sdb1", "/datadisk", "/dev/sdc1"))
        self.assertTrue(calc.is_temp_disk("/dev/sdx1", temp_mount, None))
        self.assertFalse(calc.is_temp_disk("/dev/sdb1", self.temp_dir, None))

    def test_all_disks_included_counts_sdb1_data_disk_btrfs_and_ntfs(self):
        # VM size without a temp disk, sdb1 is a data disk
        _FakeResourceDiskUtil.partition = ""
        _FakeDiskUtil.file_systems_info = [
            ("/dev/sda2", "btrfs", "/"),
            ("/dev/sdb1", "xfs", "/datadisk"),
            ("/dev/sdc1", "fuseblk", "/windows data"),
            ("server:/export", "nfs4", "/mnt/nfs"),
            ("tmpfs", "tmpfs", "/run"),
        ]
        df_output = _df(("/dev/sda2", 1000, "/"),
                        ("/dev/sdb1", 2000, "/datadisk"),
                        ("/dev/sdc1", 4000, "/windows data"),
                        ("server:/export", 8000, "/mnt/nfs"),
                        ("tmpfs", 16000, "/run"))
        calc = self._calculator([-1, 0, 1], df_output=df_output)

        total, failed = calc.get_total_used_size()

        self.assertFalse(failed)
        self.assertEqual((1000 + 2000 + 4000) * 1024, total)

    def test_btrfs_subvolumes_and_bind_mounts_are_counted_once(self):
        _FakeDiskUtil.file_systems_info = [
            ("/dev/sda3", "btrfs", "/"),
            ("/dev/sda3", "btrfs", "/home"),
            ("/dev/sda3", "btrfs", "/var"),
            ("/dev/sdc1", "xfs", "/data"),
            ("/dev/sdc1", "xfs", "/srv/data"),
        ]
        df_output = _df(("/dev/sda3", 5000, "/"),
                        ("/dev/sda3", 5000, "/home"),
                        ("/dev/sda3", 5000, "/var"),
                        ("/dev/sdc1", 7000, "/data"),
                        ("/dev/sdc1", 7000, "/srv/data"))
        calc = self._calculator([-1, 0], df_output=df_output)

        total, failed = calc.get_total_used_size()

        self.assertFalse(failed)
        self.assertEqual((5000 + 7000) * 1024, total)

    def test_only_block_device_file_systems_are_counted(self):
        # Seen in production: cluster / network file systems with unknown type names and
        # NFS / tmpfs mounted after the cached mount output was taken (empty fstype)
        _FakeDiskUtil.file_systems_info = [
            ("/dev/sda1", "xfs", "/"),
            ("10.70.32.100/wkafs01", "wekafs", "/cpfs/wkafs01"),
            ("mvfs", "mvfs", "/rview"),
            ("snfs1", "cvfs", "/data/snfs1"),
            ("rpool/data", "zfs", "/rpool/data"),
        ]
        self._write(self.module.PROC_MOUNTS_FILE,
                    "/dev/sda1 / xfs rw 0 0\n"
                    "10.24.34.76:/sd/mount/oracle /mnt/oracle\\040backup nfs4 rw 0 0\n"
                    "tmpfs /run/user/1000 tmpfs rw 0 0\n")
        df_output = _df(("/dev/sda1", 1000, "/"),
                        ("10.70.32.100/wkafs01", 10000000, "/cpfs/wkafs01"),
                        ("mvfs", 20000000, "/rview"),
                        ("snfs1", 30000000, "/data/snfs1"),
                        ("10.24.34.76:/sd/mount/oracle", 40000000, "/mnt/oracle backup"),
                        ("tmpfs", 50000000, "/run/user/1000"),
                        ("/dev/sdx1", 60000000, "/late/unknown"),
                        ("rpool/data", 2000, "/rpool/data"))
        calc = self._calculator([-1, 0], df_output=df_output)

        total, failed = calc.get_total_used_size()

        self.assertFalse(failed)
        self.assertEqual((1000 + 60000000 + 2000) * 1024, total)
        self.assertEqual("nfs4", calc.get_proc_mounts_fstypes()[("10.24.34.76:/sd/mount/oracle", "/mnt/oracle backup")])

    def test_resource_disk_is_excluded(self):
        _FakeDiskUtil.file_systems_info = [("/dev/sda1", "ext4", "/"), ("/dev/sdb1", "ext4", "/mnt")]
        df_output = _df(("/dev/sda1", 1000, "/"), ("/dev/sdb1", 2000, "/mnt"))
        calc = self._calculator([-1], df_output=df_output)

        total, failed = calc.get_total_used_size()

        self.assertFalse(failed)
        self.assertEqual(1000 * 1024, total)

    def test_unparseable_df_line_keeps_total_and_marks_failure(self):
        _FakeDiskUtil.file_systems_info = [("/dev/sda1", "ext4", "/"), ("/dev/sdc1", "ext4", "/data")]
        df_output = _df(("/dev/sda1", 1000, "/"), ("/dev/sdc1", 2000, "/data")) + "garbage line\n"
        calc = self._calculator([-1, 0], df_output=df_output)

        total, failed = calc.get_total_used_size()

        self.assertTrue(failed)
        self.assertEqual(3000 * 1024, total)

    def test_df_failure_marks_size_computation_failed(self):
        calc = self._calculator([-1])
        calc.get_df_output = lambda command: None

        total, failed = calc.get_total_used_size()

        self.assertTrue(failed)
        self.assertEqual(0, total)

    def test_excluded_disks_gen1_lvm_os_disk_is_detected(self):
        # Gen1 RHEL LVM layout: no /boot/efi, "/" on LVM, OS disk reports LUN 0 in lsscsi
        _FakeDiskUtil.file_systems_info = [
            ("/dev/mapper/rootvg-rootlv", "xfs", "/"),
            ("/dev/mapper/rootvg-usrlv", "xfs", "/usr"),
            ("/dev/sda1", "xfs", "/boot"),
            ("/dev/sdb1", "ext4", "/mnt/resource"),
            ("/dev/sdc1", "xfs", "/excluded"),
            ("/dev/sdd1", "xfs", "/data one"),
            ("/dev/mapper/app--vg-lv1", "xfs", "/app"),
            ("/dev/mapper/skipvg-lv1", "xfs", "/skip"),
        ]
        lsscsi = [
            "[0:0:0:0]    disk    Msft     Virtual Disk     1.0   /dev/sda",
            "[1:0:1:0]    disk    Msft     Virtual Disk     1.0   /dev/sdb",
            "[3:0:0:0]    disk    Msft     Virtual Disk     1.0   /dev/sdc",
            "[3:0:0:1]    disk    Msft     Virtual Disk     1.0   /dev/sdd",
        ]
        lsblk = ["sda", "sda1 /boot", "sda4", "rootvg-rootlv /", "rootvg-usrlv /usr",
                 "sdb", "sdb1 /mnt/resource", "sdc", "sdc1 /excluded", "sdc2",
                 "sdd", "sdd1 /data one", "sdd2", "app--vg-lv1 /app", "skipvg-lv1 /skip"]
        pvs = ["  /dev/sda4  rootvg", "  /dev/sdd2  app-vg", "  /dev/sdc2  skipvg", "  /dev/sde"]
        df_output = _df(("/dev/mapper/rootvg-rootlv", 1, "/"),
                        ("/dev/mapper/rootvg-usrlv", 10, "/usr"),
                        ("/dev/sda1", 100, "/boot"),
                        ("/dev/sdb1", 1000, "/mnt/resource"),
                        ("/dev/sdc1", 10000, "/excluded"),
                        ("/dev/sdd1", 100000, "/data one"),
                        ("/dev/mapper/app--vg-lv1", 1000000, "/app"),
                        ("/dev/mapper/skipvg-lv1", 10000000, "/skip"))
        # OS disk and LUN 1 are backed up, LUN 0 is excluded
        calc = self._calculator([-1, 1], is_any_disk_excluded=True, df_output=df_output,
                                lsscsi=lsscsi, lsblk=lsblk, pvs=pvs)

        total, failed = calc.get_total_used_size()

        self.assertFalse(failed)
        self.assertEqual(["/dev/sda", "/dev/sdd"], calc.disksToBeIncluded)
        self.assertEqual((1 + 10 + 100 + 100000 + 1000000) * 1024, total)

    def test_partially_included_volume_group_is_billed_per_extent(self):
        lvs = [
            "  datavg:linear:100:/dev/sdd1(0):",
            "  datavg:spanned:100:/dev/sdc1(0):",
            "  datavg:spanned:300:/dev/sdd1(100):",
            "  datavg:striped:200:/dev/sdc1(100),/dev/sdd1(400):",
            "  datavg:raid:50:raid_rimage_0(0),raid_rimage_1(0):",
            "  datavg:[raid_rimage_0]:50:/dev/sdc1(300):",
            "  datavg:[raid_rimage_1]:50:/dev/sdd1(500):",
            "  datavg:pool:400:pool_tdata(0):",
            "  datavg:[pool_tdata]:100:/dev/sdc1(400):",
            "  datavg:[pool_tdata]:300:/dev/sdd1(600):",
            "  datavg:thin-lv:1000::pool",
            "  datavg:excluded:100:/dev/sdc1(500):",
        ]
        calc = self._calculator([1], lvs=lvs)
        calc.disksToBeIncluded = ["/dev/sdd"]
        calc.pvs_output = ["/dev/sdc1 datavg", "/dev/sdd1 datavg", "/dev/sde1 othervg"]
        calc.build_pvs_dict()

        calc.get_logicalVolumes_for_billing()

        self.assertEqual([], calc.logicalVolume_to_bill)
        self.assertEqual(["datavg"], calc.partial_logicalVolumeGroups)
        fraction = calc.get_lv_billing_fraction
        self.assertEqual(1.0, fraction("/dev/mapper/datavg-linear"))
        self.assertEqual(0.75, fraction("/dev/mapper/datavg-spanned"))
        self.assertEqual(0.5, fraction("/dev/datavg/striped"))
        self.assertEqual(0.5, fraction("/dev/mapper/datavg-raid"))
        self.assertEqual(0.75, fraction("/dev/mapper/datavg-thin--lv"))
        self.assertEqual(0, fraction("/dev/mapper/datavg-excluded"))
        self.assertEqual(0, fraction("/dev/mapper/datavg-unknown"))
        self.assertEqual(0, fraction("/dev/mapper/othervg-lv"))
        self.assertEqual(300, calc.get_billable_lv_used("/dev/mapper/datavg-spanned", 400))

    def test_excluded_disks_partial_volume_group_is_billed_proportionally(self):
        _FakeDiskUtil.file_systems_info = [
            ("/dev/sda1", "ext4", "/"),
            ("/dev/mapper/datavg-spanned", "xfs", "/spanned"),
            ("/dev/mapper/datavg-excluded", "xfs", "/excluded"),
        ]
        lsscsi = [
            "[0:0:0:0]    disk    Msft     Virtual Disk     1.0   /dev/sda",
            "[3:0:0:0]    disk    Msft     Virtual Disk     1.0   /dev/sdc",
            "[3:0:0:1]    disk    Msft     Virtual Disk     1.0   /dev/sdd",
        ]
        lsblk = ["sda1 /", "datavg-spanned /spanned", "datavg-excluded /excluded"]
        pvs = ["/dev/sdc1 datavg", "/dev/sdd1 datavg"]
        lvs = ["datavg:spanned:100:/dev/sdc1(0):", "datavg:spanned:300:/dev/sdd1(0):",
               "datavg:excluded:100:/dev/sdc1(100):"]
        df_output = _df(("/dev/sda1", 1000, "/"),
                        ("/dev/mapper/datavg-spanned", 40000, "/spanned"),
                        ("/dev/mapper/datavg-excluded", 900000, "/excluded"))
        calc = self._calculator([-1, 1], is_any_disk_excluded=True, df_output=df_output,
                                lsscsi=lsscsi, lsblk=lsblk, pvs=pvs, lvs=lvs)

        total, failed = calc.get_total_used_size()

        self.assertFalse(failed)
        self.assertEqual((1000 + 30000) * 1024, total)

    def test_azure_nvme_namespaces_are_mapped_to_luns(self):
        accelerator = self.module.AZURE_NVME_REMOTE_DISK_MODEL
        self._write(os.path.join(self.module.SYS_BLOCK_DIR, "nvme0n1", "device", "model"), accelerator + "\n")
        self._write(os.path.join(self.module.SYS_BLOCK_DIR, "nvme0n2", "device", "model"), accelerator + "\n")
        self._write(os.path.join(self.module.SYS_BLOCK_DIR, "nvme0n4", "device", "model"), accelerator + "\n")
        self._write(os.path.join(self.module.SYS_BLOCK_DIR, "nvme1n1", "device", "model"), "Microsoft NVMe Direct Disk v2\n")
        calc = self._calculator([-1, 2])
        calc.lsscsi_list = ["[N:0:1:2]    disk    MSFT NVMe Accelerator v1.0__1   /dev/nvme0n2"]

        disk_luns = calc.get_disk_luns()

        self.assertEqual({"/dev/nvme0n1": -1, "/dev/nvme0n2": 0, "/dev/nvme0n4": 2}, disk_luns)
        calc.disk_list_for_billing()
        self.assertEqual(["/dev/nvme0n1", "/dev/nvme0n4"], calc.disksToBeIncluded)

    def test_azure_disk_symlinks_take_precedence(self):
        azure_dir = self.module.AZURE_DISK_SYMLINK_DIR
        dev_dir = os.path.join(self.temp_dir, "dev")
        for name in ("sda", "sdc", "sdc1"):
            self._write(os.path.join(dev_dir, name))
        os.makedirs(os.path.join(azure_dir, "scsi1"))
        try:
            os.symlink(os.path.join(dev_dir, "sda"), os.path.join(azure_dir, "root"))
            os.symlink(os.path.join(dev_dir, "sdc"), os.path.join(azure_dir, "scsi1", "lun3"))
            os.symlink(os.path.join(dev_dir, "sdc1"), os.path.join(azure_dir, "scsi1", "lun3-part1"))
        except (OSError, NotImplementedError, AttributeError):
            self.skipTest("symlinks are not supported")
        calc = self._calculator([-1])

        disk_luns = calc.get_disk_luns_from_azure_symlinks()

        self.assertEqual({os.path.realpath(os.path.join(dev_dir, "sda")): -1,
                          os.path.realpath(os.path.join(dev_dir, "sdc")): 3}, disk_luns)

    def test_get_df_output_reads_large_output(self):
        calc = self._calculator([0])
        command = [sys.executable, "-c", "import sys; sys.stdout.write('x' * 1048576)"]

        output = self.module.SizeCalculation.get_df_output(calc, command)

        self.assertEqual(1048576, len(output))

    def test_get_df_output_times_out(self):
        self.module.DF_TIMEOUT_IN_SECONDS = 1
        calc = self._calculator([0])
        command = [sys.executable, "-c", "import time; time.sleep(60)"]

        self.assertIsNone(self.module.SizeCalculation.get_df_output(calc, command))


if __name__ == "__main__":
    unittest.main()
