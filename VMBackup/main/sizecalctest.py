from common import CommonVariables
from patch import GetMyPatching
from Utils import HandlerUtil
from backuplogger import Backuplogger
from Utils import SizeCalculation
from parameterparser import ParameterParser

HandlerUtil.waagent.LoggerInit('/dev/console','/dev/stdout')
hutil = HandlerUtil.HandlerUtility(HandlerUtil.waagent.Log, HandlerUtil.waagent.Error, CommonVariables.extension_name)
backup_logger = Backuplogger(hutil)
configSeqNo = -1
hutil.try_parse_context(configSeqNo)

protected_settings = hutil._context._config['runtimeSettings'][0]['handlerSettings'].get('protectedSettings', {})
public_settings = hutil._context._config['runtimeSettings'][0]['handlerSettings'].get('publicSettings')
para_parser = ParameterParser(protected_settings, public_settings, backup_logger)

MyPatching, patch_class_name, orig_distro = GetMyPatching(backup_logger)
sizeCalculation = SizeCalculation.SizeCalculation(patching = MyPatching , hutil = hutil, logger = backup_logger , para_parser = para_parser)
total_used_size,size_calculation_failed = sizeCalculation.get_total_used_size()

print("Total Used Size: ", total_used_size)
print("Size Calculation Failed: ", size_calculation_failed)