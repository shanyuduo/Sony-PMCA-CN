import contextlib
import io
import json
import os
import sys
import time
import struct
import zipfile

import config
from ..apk import *
from .. import appstore
from .. import firmware
from .. import installer
from ..io import *
from ..marketserver.server import *
from ..platform import *
from ..platform.backend.senser import *
from ..platform.backend.usb import *
from ..usb import *
from ..usb.driver import *
from ..usb.driver.generic import *
from ..usb.sony import *
from ..util import http

scriptRoot = getattr(sys, '_MEIPASS', os.path.dirname(__file__) + '/../..')


def printStatus(status):
 """Print progress"""
 print('%s %d%%' % (status.message, status.percent))


appListCache = None
def listApps(enableCache=False):
 global appListCache
 appStoreRepo = appstore.GithubApi(config.githubAppListUser, config.githubAppListRepo)

 if not appListCache or not enableCache:
  print('正在加载应用列表')
  apps = appstore.AppStore(appStoreRepo).apps
  print('找到 %d 个应用' % len(apps))
  appListCache = apps
 return appListCache


def installApp(dev, apkFile=None, appPackage=None, outFile=None):
 """Installs an app on the specified device."""
 certFile = scriptRoot + '/certs/localtest.me.pem'
 with ServerContext(LocalMarketServer(certFile)) as server:
  apkData = None
  if apkFile:
   apkData = apkFile.read()
  elif appPackage:
   print('正在下载 APK')
   apps = listApps(True)
   if appPackage not in apps:
    raise Exception('未知应用：%s' % appPackage)
   apkData = apps[appPackage].release.asset

  if apkData:
   print('正在分析 APK')
   print('')
   checkApk(io.BytesIO(apkData))
   print('')
   server.setApk(apkData)

  print('正在启动任务')
  xpdData = server.getXpd()

  print('正在开始通信')
  # Point the camera to the web api
  result = installer.install(SonyAppInstallCamera(dev), *server.server_address, xpdData, printStatus)
  if result.code != 0:
   raise Exception('通信错误 %d：%s' % (result.code, result.message))

  result = server.getResult()

  print('任务成功完成')

  if outFile:
   print('正在写入输出文件')
   json.dump(result, outFile, indent=2)

  return result


def checkApk(apkFile):
 try:
  apk = ApkParser(apkFile)

  props = [
   ('包名', apk.getPackageName()),
   ('版本', apk.getVersionName()),
  ]
  apk.getVersionCode()
  for k, v in props:
   print('%-9s%s' % (k + ': ', v))

  sdk = apk.getMinSdkVersion()
  if sdk > 10:
   print('警告：此应用可能与设备不兼容（minSdkVersion = %d）' % sdk)

  try:
   apk.getCert()
  except:
   print('警告：无法读取 APK 证书')

 except:
  print('警告：无效的 APK 文件')


class UsbDriverList(contextlib.AbstractContextManager):
 def __init__(self, *contexts):
  self._contexts = contexts
  self._drivers = []

 def __enter__(self):
  self._drivers = [context.__enter__() for context in self._contexts]
  return self

 def __exit__(self, *ex):
  for context in self._contexts:
   context.__exit__(*ex)
  self._drivers = []

 def listDevices(self, vendor):
  for driver in self._drivers:
   for dev in driver.listDevices(vendor):
    yield dev, driver.classType, driver.openDevice(dev)


def importDriver(driverName=None):
 """Imports the usb driver. Use in a with statement"""
 MscContext = None
 MtpContext = None
 VendorSpecificContext = None
 MscContext2 = None
 MtpContext2 = None
 VendorSpecificContext2 = None

 # Load native drivers
 if driverName == 'native' or driverName is None:
  if sys.platform == 'win32':
   from ..usb.driver.windows.msc import MscContext
   from ..usb.driver.windows.wpd import MtpContext
   from ..usb.driver.windows.driverless import VendorSpecificContext
  elif sys.platform == 'darwin':
   from ..usb.driver.osx import isMscDriverAvailable
   if isMscDriverAvailable():
    from ..usb.driver.osx import MscContext
   else:
    print('未安装原生驱动')
  else:
   print('没有可用的原生驱动')
 elif driverName == 'qemu':
  from ..usb.driver.generic.qemu import MscContext
  from ..usb.driver.generic.qemu import MtpContext
 elif driverName != 'libusb':
  raise Exception('未知驱动')

 # Fallback to libusb
 if MscContext is None or (driverName is None and sys.platform == 'win32'):
  from ..usb.driver.generic.libusb import MscContext as MscContext2
 if MtpContext is None or (driverName is None and sys.platform == 'win32'):
  from ..usb.driver.generic.libusb import MtpContext as MtpContext2
 if (VendorSpecificContext is None and driverName != 'qemu') or (driverName is None and sys.platform == 'win32'):
  from ..usb.driver.generic.libusb import VendorSpecificContext as VendorSpecificContext2

 drivers = [context() for context in [MscContext, MtpContext, VendorSpecificContext, MscContext2, MtpContext2, VendorSpecificContext2] if context]
 print('使用驱动 %s' % ', '.join(d.name for d in drivers))
 return UsbDriverList(*drivers)


def listDevices(driverList, quiet=False):
 """List all Sony usb devices"""
 if not quiet:
  print('正在搜索索尼设备')
 for dev, type, drv in driverList.listDevices(SONY_ID_VENDOR):
  if type == USB_CLASS_MSC:
   if not quiet:
    print('\n正在查询海量存储设备')
   # Get device info
   info = MscDevice(drv).getDeviceInfo()

   if isSonyMscCamera(info):
    if isSonyMscUpdaterCamera(dev):
     if not quiet:
      print('%s %s 是处于固件更新模式的相机' % (info.manufacturer, info.model))
     yield SonyMscUpdaterDevice(drv)
    else:
     if not quiet:
      print('%s %s 是处于海量存储模式的相机' % (info.manufacturer, info.model))
     yield SonyMscExtCmdDevice(drv)

  elif type == USB_CLASS_PTP:
   if not quiet:
    print('\n正在查询 MTP 设备')
   # Get device info
   info = MtpDevice(drv).getDeviceInfo()

   if isSonyMtpCamera(info):
    if not quiet:
     print('%s %s 是处于 MTP 模式的相机' % (info.manufacturer, info.model))
    yield SonyMtpExtCmdDevice(drv)
   elif isSonyMtpAppInstallCamera(info):
    if not quiet:
     print('%s %s 是处于应用安装模式的相机' % (info.manufacturer, info.model))
    yield SonyMtpAppInstallDevice(drv)

  elif type == USB_CLASS_VENDOR_SPECIFIC:
   if isSonySenserCamera(dev):
    print('找到处于服务模式的相机')
    yield SonySenserDevice(drv)

  if not quiet:
   print('')


def getDevice(driver):
 """Check for exactly one Sony usb device"""
 devices = list(listDevices(driver))
 if not devices:
  print('未找到设备。请确保相机已连接。')
 elif len(devices) != 1:
  print('错误：找到太多索尼设备。仅支持一台相机。')
 else:
  return devices[0]


def infoCommand(driverName=None):
 """Display information about the camera connected via usb"""
 with importDriver(driverName) as driver:
  device = getDevice(driver)
  if device:
   if isinstance(device, SonyAppInstallDevice):
    info = installApp(device)
    print('')
    props = [
     ('型号', info['deviceinfo']['name']),
     ('产品代码', info['deviceinfo']['productcode']),
     ('序列号', info['deviceinfo']['deviceid']),
     ('固件版本', info['deviceinfo']['fwversion']),
    ]
   elif isinstance(device, SonyExtCmdDevice):
    dev = SonyExtCmdCamera(device)
    info = dev.getCameraInfo()
    updater = SonyUpdaterCamera(device)
    updater.init()
    firmwareOld, firmwareNew = updater.getFirmwareVersion()
    props = [
     ('型号', info.modelName),
     ('产品代码', info.modelCode),
     ('序列号', info.serial),
     ('固件版本', firmwareOld),
    ]
    try:
     lensInfo = dev.getLensInfo()
     if lensInfo.model != 0:
      props.append(('镜头', '型号 0x%x（固件 %s）' % (lensInfo.model, lensInfo.version)))
    except (InvalidCommandException, UnknownMscException):
     pass
    try:
     gpsInfo = dev.getGpsData()
     props.append(('GPS 数据', '%s - %s' % gpsInfo))
    except (InvalidCommandException, UnknownMscException):
     pass
   else:
    print('错误：无法在此模式下使用相机。请切换到 MTP 或海量存储模式。')
    return
   for k, v in props:
    print('%-20s%s' % (k + ': ', v))


def installCommand(driverName=None, apkFile=None, appPackage=None, outFile=None):
 """Install the given apk on the camera"""
 with importDriver(driverName) as driver:
  device = getDevice(driver)
  if device and isinstance(device, SonyExtCmdDevice):
   print('正在切换到应用安装模式')
   try:
    SonyExtCmdCamera(device).switchToAppInstaller()
   except InvalidCommandException:
    print('错误：此相机不支持应用。请查看兼容性列表。')
    return
   device = None

   print('等待相机切换...')
   for i in range(10):
    time.sleep(.5)
    try:
     devices = list(listDevices(driver, True))
     if len(devices) == 1 and isinstance(devices[0], SonyAppInstallDevice):
      device = devices[0]
      break
    except:
     pass
   else:
    print('操作超时。请在相机连接后重新运行此命令。')

  if device and isinstance(device, SonyAppInstallDevice):
   installApp(device, apkFile, appPackage, outFile)
  elif device:
   print('错误：无法在此模式下使用相机。请切换到 MTP 或海量存储模式。')


def appSelectionCommand():
 apps = list(listApps().values())
 for i, app in enumerate(apps):
  print(' [%2d] %s' % (i+1, app.package))
 i = int(input('输入要安装的应用编号（0 表示取消）：'))
 if i != 0:
  pkg = apps[i - 1].package
  print('')
  print('正在安装 %s' % pkg)
  return pkg


def getFdats():
 fdatDir = scriptRoot + '/updatershell/fdat/'
 for dir in os.listdir(fdatDir):
  if os.path.isdir(fdatDir + dir):
   payloadFile = fdatDir + dir + '.dat'
   if os.path.isfile(payloadFile):
    for model in os.listdir(fdatDir + dir):
     hdrFile = fdatDir + dir + '/' + model
     if os.path.isfile(hdrFile) and hdrFile.endswith('.hdr'):
      yield model[:-4], (hdrFile, payloadFile)


def getFdat(device):
 fdats = dict(getFdats())
 while device != '' and not device[-1:].isdigit() and device not in fdats:
  device = device[:-1]
 if device in fdats:
  hdrFile, payloadFile = fdats[device]
  with open(hdrFile, 'rb') as hdr, open(payloadFile, 'rb') as payload:
   return hdr.read() + payload.read()


def firmwareUpdateCommand(file, driverName=None):
 offset, size = firmware.readDat(file)

 with importDriver(driverName) as driver:
  device = getDevice(driver)
  if device:
   firmwareUpdateCommandInternal(driver, device, file, offset, size)


def updaterShellCommand(model=None, fdatFile=None, driverName=None, complete=None):
 with importDriver(driverName) as driver:
  device = getDevice(driver)
  if device:
   if fdatFile:
    fdat = fdatFile.read()
   else:
    if not model:
     print('正在获取设备信息')
     try:
      model = SonyExtCmdCamera(device).getCameraInfo().modelName
     except:
      print('错误：无法确定相机型号')
      return
     print('使用型号 %s 的固件' % model)
     print('')

    fdat = getFdat(model)
    if not fdat:
     print('错误：型号"%s"不支持自定义固件更新。请查看兼容性列表。' % model)
     return

   if not complete:
    def complete(device):
     print('正在启动固件更新 Shell...')
     print('')
     CameraShell(UsbPlatformBackend(device)).run()
   firmwareUpdateCommandInternal(driver, device, io.BytesIO(fdat), 0, len(fdat), complete)


def firmwareUpdateCommandInternal(driver, device, file, offset, size, complete=None):
 if not isinstance(device, SonyUpdaterDevice) and not isinstance(device, SonyExtCmdDevice):
  print('错误：无法在此模式下使用相机。请切换到 MTP 或海量存储模式。')
  return

 dev = SonyUpdaterCamera(device)

 print('正在初始化固件更新')
 dev.init()
 file.seek(offset)
 dev.checkGuard(file, size)
 versions = dev.getFirmwareVersion()
 if versions[1] != '9.99':
  print('从版本 %s 更新到版本 %s' % versions)

 if not isinstance(device, SonyUpdaterDevice):
  print('正在切换到固件更新模式')
  dev.switchMode()

  device = None
  print('')
  print('等待相机切换...')
  print('请按照相机屏幕上的提示操作。')
  for i in range(60):
   time.sleep(.5)
   try:
    devices = list(listDevices(driver, True))
    if len(devices) == 1 and isinstance(devices[0], SonyUpdaterDevice):
     device = devices[0]
     break
   except:
    pass
  else:
   print('操作超时。请在相机连接后重新运行此命令。')

  if device:
   firmwareUpdateCommandInternal(None, device, file, offset, size, complete)

 else:
  print('正在写入固件')
  file.seek(offset)
  dev.writeFirmware(ProgressFile(file, size), size, complete)
  dev.complete()
  print('完成')


def guessFirmwareCommand(file, driverName=None):
 with importDriver(driverName) as driver:
  device = getDevice(driver)
  if device:
   if not isinstance(device, SonyExtCmdDevice):
    print('错误：无法在此模式下使用相机。')
    return

   print('正在获取设备信息')
   model = SonyExtCmdCamera(device).getCameraInfo().modelName
   print('型号名称：%s' % model)
   print('')

   dev = SonyUpdaterCamera(device)
   with zipfile.ZipFile(file) as zip:
    infos = zip.infolist()
    print('正在尝试 %d 个固件镜像' % len(infos))
    for info in infos:
     data = zip.read(info)
     try:
      dev.init()
      dev.checkGuard(io.BytesIO(data), len(data))
      break
     except Exception as e:
      if 'Invalid model' not in str(e):
       print(e)
       break
    else:
     print('失败：未找到匹配的文件')
     return
    print('成功：找到匹配的文件：%s' % info.filename)


def gpsUpdateCommand(file=None, driverName=None):
 with importDriver(driverName) as driver:
  device = getDevice(driver)
  if device:
   if not isinstance(device, SonyExtCmdDevice):
    print('错误：无法在此模式下使用相机。')
    return

   if not file:
    print('正在下载 GPS 数据')
    file = io.BytesIO(http.get('https://control.d-imaging.sony.co.jp/GPS/assistme.dat').raw_data)

   print('正在写入 GPS 数据')
   SonyExtCmdCamera(device).writeGpsData(file)
   print('完成')


def streamingCommand(write=None, file=None, driverName=None):
 """Read/Write Streaming information for the camera connected via usb"""
 with importDriver(driverName) as driver:
  device = getDevice(driver)
  if device:
   if not isinstance(device, SonyExtCmdDevice):
    print('错误：无法在此模式下使用相机。')
   else:
    dev = SonyExtCmdCamera(device)

    if write:
     incoming = json.load(write)

     # assemble Social (first 9 items in file)
     mydict = {}
     for key in incoming[:9]:
      if key[0] in ['twitterEnabled', 'facebookEnabled']:
       mydict[key[0]] = key[1] # Integer
      else:
       mydict[key[0]] = key[1].encode('ascii')

     data = SonyExtCmdCamera.LiveStreamingSNSInfo.pack(
      twitterEnabled = mydict['twitterEnabled'],
      twitterConsumerKey = mydict['twitterConsumerKey'].ljust(1025, b'\x00'),
      twitterConsumerSecret = mydict['twitterConsumerSecret'].ljust(1025, b'\x00'),
      twitterAccessToken1 = mydict['twitterAccessToken1'].ljust(1025, b'\x00'),
      twitterAccessTokenSecret = mydict['twitterAccessTokenSecret'].ljust(1025, b'\x00'),
      twitterMessage = mydict['twitterMessage'].ljust(401, b'\x00'),
      facebookEnabled = mydict['facebookEnabled'],
      facebookAccessToken = mydict['facebookAccessToken'].ljust(1025, b'\x00'),
      facebookMessage = mydict['facebookMessage'].ljust(401, b'\x00'),
     )
     dev.setLiveStreamingSocialInfo(data)

     # assemble Streaming, file may contain multiple sets (of 14 items)
     data = b'\x01\x00\x00\x00'
     data += struct.pack('<i', int((len(incoming)-9)/14))
     mydict = {}
     count = 1
     for key in incoming[9:]:
      if key[0] in ['service', 'enabled', 'videoFormat', 'videoFormat', 'unknown', \
        'enableRecordMode', 'channels', 'supportedFormats']:
       mydict[key[0]] = key[1]
      elif key[0] == 'macIssueTime':
       mydict[key[0]] = binascii.a2b_hex(key[1])
      else:
       mydict[key[0]] = key[1].encode('ascii')

      if count == 14:
       # reassemble Structs
       data += SonyExtCmdCamera.LiveStreamingServiceInfo1.pack(
        service = mydict['service'],
        enabled = mydict['enabled'],
        macId = mydict['macId'].ljust(41, b'\x00'),
        macSecret = mydict['macSecret'].ljust(41, b'\x00'),
        macIssueTime = mydict['macIssueTime'],
        unknown = 0, # mydict['unknown'],
       )

       data += struct.pack('<i', len(mydict['channels']))
       for j in range(len(mydict['channels'])):
        data += struct.pack('<i', mydict['channels'][j])

       data += SonyExtCmdCamera.LiveStreamingServiceInfo2.pack(
        shortURL = mydict['shortURL'].ljust(101, b'\x00'),
        videoFormat = mydict['videoFormat'],
       )

       data += struct.pack('<i', len(mydict['supportedFormats']))
       for j in range(len(mydict['supportedFormats'])):
        data += struct.pack('<i', mydict['supportedFormats'][j])

       data += SonyExtCmdCamera.LiveStreamingServiceInfo3.pack(
        enableRecordMode = mydict['enableRecordMode'],
        videoTitle = mydict['videoTitle'].ljust(401, b'\x00'),
        videoDescription = mydict['videoDescription'].ljust(401, b'\x00'),
        videoTag = mydict['videoTag'].ljust(401, b'\x00'),
       )
       count = 1
      else:
       count += 1

     dev.setLiveStreamingServiceInfo(data)
     return

    # Read settings from camera (do this first so we know channels/supportedFormats)
    settings = dev.getLiveStreamingServiceInfo()
    social = dev.getLiveStreamingSocialInfo()

    data = []
    # Social settings
    for key in (social._asdict()).items():
     if key[0] in ['twitterEnabled', 'facebookEnabled']:
      data.append([key[0], key[1]])
     else:
      data.append([key[0], key[1].decode('ascii').split('\x00')[0]])

    # Streaming settings, file may contain muliple sets of data
    try:
     for key in next(settings).items():
      if key[0] in ['service', 'enabled', 'videoFormat', 'enableRecordMode', \
        'unknown', 'channels', 'supportedFormats']:
       data.append([key[0], key[1]])
      elif key[0] == 'macIssueTime':
       data.append([key[0], binascii.b2a_hex(key[1]).decode('ascii')])
      else:
       data.append([key[0], key[1].decode('ascii').split('\x00')[0]])
    except StopIteration:
     pass

    if file:
     file.write(json.dumps(data, indent=4))
    else:
     for k, v in data:
      print('%-20s%s' % (k + ': ', v))


def wifiCommand(write=None, file=None, multi=False, driverName=None):
 """Read/Write WiFi information for the camera connected via usb"""
 with importDriver(driverName) as driver:
  device = getDevice(driver)
  if device:
   if not isinstance(device, SonyExtCmdDevice):
    print('错误：无法在此模式下使用相机。')
   else:
    dev = SonyExtCmdCamera(device)

    if write:
     incoming = json.load(write)
     data = struct.pack('<i', int(len(incoming)/3))

     mydict = {}
     count = 1
     for key in incoming:
      if key[0] == 'keyType':
       mydict[key[0]] = key[1] # Integer
      else:
       mydict[key[0]] = key[1].encode('ascii')

      if count == 3:
       # reassemble Struct
       apinfo = SonyExtCmdCamera.APInfo.pack(
        keyType = mydict['keyType'],
        sid = mydict['sid'].ljust(33, b'\x00'),
        key = mydict['key'].ljust(65, b'\x00'),
       )
       data += apinfo
       count = 1
      else:
       count += 1

     if multi:
      dev.setMultiWifiAPInfo(data)
     else:
      dev.setWifiAPInfo(data)
     return

    # Read settings from camera
    if multi:
     settings = dev.getMultiWifiAPInfo()
    else:
     settings = dev.getWifiAPInfo()

    data = []
    try:
     for key in next(settings)._asdict().items():
      if key[0] == 'keyType':
       data.append([key[0], key[1]]) # Integer
      else:
       data.append([key[0],key[1].decode('ascii').split('\x00')[0]])
    except StopIteration:
     pass

    if file:
     file.write(json.dumps(data, indent=4))
    else:
     for k, v in data:
      print('%-20s%s' % (k + ': ', v))


def senserShellCommand(driverName=None, complete=None):
 if driverName is None and sys.platform != 'win32':
  driverName = 'libusb'
 with importDriver(driverName) as driver:
  device = getDevice(driver)
  if device and isinstance(device, SonyMscExtCmdDevice):
   if not isinstance(device.driver, GenericUsbDriver):
    print('错误：切换到服务模式仅支持 libusb 驱动。')
    if sys.platform == 'win32':
     print('请使用 Zadig 为海量存储设备安装 libusb-win32 驱动。')
    return

   print('正在切换到服务模式')
   dev = SonySenserAuthDevice(device.driver)
   dev.start()
   dev.authenticate()

   device = None
   print('')
   print('等待相机切换...')
   for i in range(10):
    time.sleep(.5)
    try:
     devices = list(listDevices(driver, True))
     if len(devices) == 1 and isinstance(devices[0], SonySenserDevice):
      device = devices[0]
      break
    except:
     pass
   else:
    print('操作超时。请在相机连接后重新运行此命令。')

  if device and isinstance(device, SonySenserDevice):
   if not isinstance(device.driver, GenericUsbDriver):
    print('错误：服务模式仅支持 libusb 驱动。')
    if sys.platform == 'win32':
     print('请使用 Zadig 为服务模式设备安装 libusb-win32 驱动。')
    return

   print('正在认证')
   dev = SonySenserAuthDevice(device.driver)
   dev.start()
   dev.authenticate()
   try:
    if complete:
     complete(SonySenserCamera(device))
    else:
     print('正在启动服务 Shell...')
     print('')
     CameraShell(SenserPlatformBackend(SonySenserCamera(device))).run()
   finally:
    dev.stop()
   print('完成')
  elif device:
   print('错误：无法在此模式下使用相机。请切换到海量存储模式。')
