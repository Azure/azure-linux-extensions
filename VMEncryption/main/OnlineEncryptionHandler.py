import uuid
import os
import threading
try:
    from queue import Queue # Python 3
except ImportError:
    from Queue import Queue # Python 2

from DiskUtil import DiskUtil
from CryptMountConfigUtil import CryptMountConfigUtil
from BekUtil import BekUtil
from Common import CommonVariables, CryptItem, DeviceItem
from CommandExecutor import CommandExecutor
from OnlineEncryptionResumer import OnlineEncryptionResumer


class OnlineEncryptionItem:
    def __init__(self, crypt_item, bek_file_path):
        self.crypt_item = crypt_item
        self.bek_file_path = bek_file_path


class OnlineEncryptionHandler:
    def __init__(self, logger,security_type=None,public_setting=None):
        self.devices = Queue()
        self.logger = logger
        self.command_executor = CommandExecutor(self.logger)
        self.security_type = security_type
        self.public_setting = public_setting

    def handle(self, device_items_to_encrypt, passphrase_file, disk_util, crypt_mount_config_util, bek_util):
        for device_item in device_items_to_encrypt:
            self.logger.log("Setting up device " + device_item.name)
            device_fs = device_item.file_system.lower()
            if device_fs not in CommonVariables.inplace_supported_file_systems:
                if device_fs in CommonVariables.format_supported_file_systems:
                    msg = "Encrypting {0} file system is not supported for data-preserving encryption. Consider using the encrypt-format-all option.".format(device_fs)
                else:
                    msg = "AzureDiskEncryption does not support the {0} file system".format(device_fs)
                self.logger.log(msg=msg, level=CommonVariables.ErrorLevel)
                return device_item

            umount_status_code = CommonVariables.success
            if device_item.mount_point is not None and device_item.mount_point != "":
                umount_status_code = disk_util.umount(device_item.mount_point)
                if umount_status_code != CommonVariables.success:
                    self.logger.log("error occured when do the umount for: {0} with code: {1}".format(device_item.mount_point, umount_status_code))
                    return device_item
            
            device_dev_path = os.path.join('/dev/', device_item.name)
            luks_header_size = disk_util.get_luks_header_size()
            size_shrink_to = (device_item.size - luks_header_size) / CommonVariables.sector_size
            chk_shrink_result = disk_util.check_shrink_fs(dev_path=device_dev_path, size_shrink_to=size_shrink_to)

            if chk_shrink_result != CommonVariables.process_success:
                self.logger.log(msg="check shrink fs failed with code {0} for {1}".format(chk_shrink_result, device_dev_path),
                           level=CommonVariables.ErrorLevel)
                self.logger.log(msg="Your file system may not have enough space to do the encryption or file System may not support resizing")
                return device_item

            mapper_name = str(uuid.uuid4())
            init_status_code = self.command_executor.ExecuteInBash('cryptsetup reencrypt --encrypt --init-only --reduce-device-size {0} {1} {2} -d {3} -q'.format(CommonVariables.luks_header_sector_v2,
                                                                                                                                                               device_dev_path, mapper_name, passphrase_file))
            if init_status_code != CommonVariables.success:
                self.logger.log("Failed to setup encryption layer for device: " + device_item.name)
                return device_item
            
            if self.security_type== CommonVariables.ConfidentialVM:
                crypt_item = self.update_crypttab_and_fstab(disk_util, crypt_mount_config_util, mapper_name, device_dev_path, device_item.file_system, device_item.mount_point,passphrase_file)
            else:
                crypt_item = self.update_crypttab_and_fstab(disk_util, crypt_mount_config_util, mapper_name, device_dev_path, device_item.file_system, device_item.mount_point)
            self.devices.put(OnlineEncryptionItem(crypt_item, passphrase_file))

    def update_crypttab_and_fstab(self, disk_util, crypt_mount_config_util, mapper_name, device_dev_path, device_filesystem, device_mount_point, passphrase_file=None):
        crypt_item_to_update = CryptItem()
        crypt_item_to_update.mapper_name = mapper_name
        original_dev_name_path = device_dev_path
        crypt_item_to_update.dev_path = disk_util.get_persistent_path_by_sdx_path(original_dev_name_path)
        crypt_item_to_update.luks_header_path = None
        crypt_item_to_update.file_system = device_filesystem
        crypt_item_to_update.uses_cleartext_key = False
        crypt_item_to_update.current_luks_slot = 0
        crypt_item_to_update.keyfile_path = passphrase_file
        # if the original mountpoint is empty, then leave
        # it as None
        mount_point = device_mount_point
        if mount_point == "" or mount_point is None:
            crypt_item_to_update.mount_point = "None"
        else:
            crypt_item_to_update.mount_point = mount_point
        
        device_mapper_path = os.path.join(CommonVariables.dev_mapper_root, mapper_name)

        if mount_point:
            self.logger.log(msg="removing entry for unencrypted drive from fstab", level=CommonVariables.InfoLevel)
            crypt_mount_config_util.modify_fstab_entry_encrypt(mount_point, device_mapper_path)
        else:
            self.logger.log(msg=original_dev_name_path + " is not defined in fstab, no need to update", level=CommonVariables.InfoLevel)

        if crypt_item_to_update.mount_point != "None":
            disk_util.mount_filesystem(device_mapper_path, crypt_item_to_update.mount_point)
            backup_folder = os.path.join(crypt_item_to_update.mount_point, ".azure_ade_backup_mount_info/")
            update_crypt_item_result = crypt_mount_config_util.add_crypt_item(crypt_item_to_update, backup_folder)
        else:
            self.logger.log("the crypt_item_to_update.mount_point is None, so we do not mount it.")
            update_crypt_item_result = crypt_mount_config_util.add_crypt_item(crypt_item_to_update)

        if not update_crypt_item_result:
            self.logger.log(msg="update crypt item failed", level=CommonVariables.ErrorLevel)

        return crypt_item_to_update

    def get_device_items_for_resume(self, crypt_mount_config_util, disk_util):
        crypt_items = crypt_mount_config_util.get_crypt_items()
        for crypt_item in crypt_items:
            self.logger.log("Checking if device {0} needs resume encryption.".format(crypt_item.dev_path))
            if disk_util.luks_check_reencryption(crypt_item.dev_path, crypt_item.luks_header_path):
                self.logger.log("Device {0} needs resume encryption.".format(crypt_item.dev_path))
                self.devices.put(OnlineEncryptionItem(crypt_item, crypt_item.keyfile_path))
        return self.devices.qsize()


    def get_online_encryption_item(self, queue_lock, log_lock):
        online_encryption_item = None
        queue_lock.acquire()
        try:
            if not self.devices.empty():
                online_encryption_item = self.devices.get()
            else:
                self.update_log("No more devices to encrypt.", log_lock)
        except Exception:
            self.update_log("Error while trying to get device to encrypt.", log_lock)
            pass
        finally:
            queue_lock.release()
        return online_encryption_item


    def resume_encryption(self, disk_util, log_lock, queue_lock):
        online_encryption_item = self.get_online_encryption_item(queue_lock, log_lock)
        while online_encryption_item is not None:
            self.update_log("Picked up device "+ online_encryption_item.crypt_item.dev_path, log_lock)
            import_token=False
            if self.security_type==CommonVariables.ConfidentialVM:
                import_token=True
            OnlineEncryptionResumer(online_encryption_item.crypt_item, disk_util, online_encryption_item.bek_file_path, self.logger, None).begin_resume(False, log_lock,import_token,self.public_setting)
            online_encryption_item = self.get_online_encryption_item(queue_lock, log_lock)
        self.devices.task_done()


    def update_log(self, msg, log_lock):
        log_lock.acquire()
        self.logger.log(msg)
        log_lock.release()


    def handle_resume_encryption(self, disk_util):
        max_threads = self.devices.qsize() #For now there will be a thread for each volume
        threads = []
        log_lock = threading.Lock()
        queue_lock = threading.Lock()
        for thr in range(max_threads):
            thread = threading.Thread(target=self.resume_encryption, args=(disk_util, log_lock, queue_lock))
            threads.append(thread)
            threads[thr].start()

        for thr in range(max_threads):
            threads[thr].join()





