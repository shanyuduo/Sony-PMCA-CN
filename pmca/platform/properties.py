import binascii
from collections import OrderedDict
import io

from .backend import *
from .backup import *

class Property(abc.ABC):
 def __init__(self, backend):
  self.backend = backend

 @abc.abstractmethod
 def get(self):
  pass


class BackupProperty(Property):
 def __init__(self, backend, name):
  super(BackupProperty, self).__init__(backend)
  self._backup = BackupInterface(BackupPlatformDataInterface(backend))
  self.name = name

 def _read(self):
  return self._backup.readProp(self.name)


class StrBackupProperty(BackupProperty):
 def get(self):
  return self._read().decode('latin1').rstrip('\0')


class HexBackupProperty(BackupProperty):
 def get(self):
  return binascii.hexlify(self._read()).decode('ascii').lstrip('0')


class BackupRegionProperty(Property):
 def __init__(self, backend):
  super(BackupRegionProperty, self).__init__(backend)
  self._backup = BackupInterface(BackupPlatformDataInterface(backend))

 def get(self):
  return self._backup.getRegion()


class FirmwareVersionProperty(Property):
 def get(self):
  f = io.BytesIO()
  self.backend.readFile('/setting/updater/dat4', f)
  data = f.getvalue()
  if len(data) != 2:
   raise Exception('版本文件大小错误')
  return '%x.%02x' % (ord(data[1:]), ord(data[:1]))


class PropertyInterface:
 def __init__(self, backend):
  self._props = OrderedDict()

  if isinstance(backend, BackupPlatformBackend):
   self.addProp('modelName', '型号', StrBackupProperty(backend, 'modelName'))
   self.addProp('modelCode', '产品代码', HexBackupProperty(backend, 'modelCode'))
   self.addProp('serialNumber', '序列号', HexBackupProperty(backend, 'serialNumber'))
   self.addProp('backupRegion', '备份区域', BackupRegionProperty(backend))
  if isinstance(backend, FilePlatformBackend):
   self.addProp('firmwareVersion', '固件版本', FirmwareVersionProperty(backend))
  if isinstance(backend, BackupPlatformBackend):
   self.addProp('androidPlatformVersion', 'Android 平台版本', StrBackupProperty(backend, 'androidPlatformVersion'))

 def addProp(self, name, desc, prop):
  self._props[name] = (desc, prop)

 def getProp(self, name):
  return self._props[name][1].get()

 def getProps(self):
  for name, (desc, prop) in self._props.items():
   try:
    yield name, desc, prop.get()
   except:
    pass
