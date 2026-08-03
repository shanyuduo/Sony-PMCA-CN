#!/usr/bin/env python3
"""A command line application to install apps on Android-enabled Sony cameras"""
import argparse

from pmca.commands.backup import *
from pmca.commands.market import *
from pmca.commands.usb import *
from pmca import spk

if getattr(sys, 'frozen', False):
 from frozenversion import version
else:
 version = None

def main():
 """Command line main"""
 parser = argparse.ArgumentParser()
 if version:
  parser.add_argument('--version', action='version', version=version)
 drivers = ['native', 'libusb', 'qemu']
 subparsers = parser.add_subparsers(dest='command', title='commands')
 info = subparsers.add_parser('info', description='显示通过 USB 连接的相机信息')
 info.add_argument('-d', dest='driver', choices=drivers, help='指定驱动程序')
 install = subparsers.add_parser('install', description='在通过 USB 连接的相机上安装 APK 文件。不指定文件时可测试连接。')
 install.add_argument('-d', dest='driver', choices=drivers, help='指定驱动程序')
 install.add_argument('-o', dest='outFile', type=argparse.FileType('w'), help='将输出写入此文件')
 installMode = install.add_mutually_exclusive_group()
 installMode.add_argument('-f', dest='apkFile', type=argparse.FileType('rb'), help='安装 APK 文件')
 installMode.add_argument('-a', dest='appPackage', help='应用列表中应用的包名')
 installMode.add_argument('-i', dest='appInteractive', action='store_true', help='交互式从应用列表中选择应用')
 market = subparsers.add_parser('market', description='从索尼官方应用商店下载应用')
 market.add_argument('-t', dest='token', required=True, help='指定认证令牌')
 apk2spk = subparsers.add_parser('apk2spk', description='将 APK 转换为 SPK')
 apk2spk.add_argument('inFile', metavar='app.apk', type=argparse.FileType('rb'), help='要转换的 APK 文件')
 apk2spk.add_argument('outFile', metavar='app' + spk.constants.extension, type=argparse.FileType('wb'), help='输出的 SPK 文件')
 spk2apk = subparsers.add_parser('spk2apk', description='将 SPK 转换为 APK')
 spk2apk.add_argument('inFile', metavar='app' + spk.constants.extension, type=argparse.FileType('rb'), help='要转换的 SPK 文件')
 spk2apk.add_argument('outFile', metavar='app.apk', type=argparse.FileType('wb'), help='输出的 APK 文件')
 firmware = subparsers.add_parser('firmware', description='更新固件')
 firmware.add_argument('-f', dest='datFile', type=argparse.FileType('rb'), required=True, help='固件文件')
 firmware.add_argument('-d', dest='driver', choices=drivers, help='指定驱动程序')
 updaterShell = subparsers.add_parser('updatershell', description='启动固件更新调试 Shell')
 updaterShell.add_argument('-d', dest='driver', choices=drivers, help='指定驱动程序')
 updaterShellMode = updaterShell.add_mutually_exclusive_group()
 updaterShellMode.add_argument('-f', dest='fdatFile', type=argparse.FileType('rb'), help='固件文件')
 updaterShellMode.add_argument('-m', dest='model', help='型号名称')
 serviceShell = subparsers.add_parser('serviceshell', description='启动服务模式 Shell')
 guessFirmware = subparsers.add_parser('guess_firmware', description='猜测适用的固件文件')
 guessFirmware.add_argument('-d', dest='driver', choices=drivers, help='指定驱动程序')
 guessFirmware.add_argument('-f', dest='file', type=argparse.FileType('rb'), required=True, help='输入文件')
 gps = subparsers.add_parser('gps', description='更新 GPS 辅助数据')
 gps.add_argument('-d', dest='driver', choices=drivers, help='指定驱动程序')
 gps.add_argument('-f', dest='file', type=argparse.FileType('rb'), help='assistme.dat 文件')
 stream = subparsers.add_parser('stream', description='更新直播流配置')
 stream.add_argument('-d', dest='driver', choices=drivers, help='指定驱动程序')
 stream.add_argument('-f', dest='file', type=argparse.FileType('w'), help='将当前设置保存到文件')
 stream.add_argument('-w', dest='write', type=argparse.FileType('r'), help='从文件写入相机设置')
 wifi = subparsers.add_parser('wifi', description='更新 WiFi 配置')
 wifi.add_argument('-d', dest='driver', choices=drivers, help='指定驱动程序')
 wifi.add_argument('-m', dest='multi', action='store_true', help='读取/写入"多 WiFi"设置')
 wifi.add_argument('-f', dest='file', type=argparse.FileType('w'), help='将当前设置保存到文件')
 wifi.add_argument('-w', dest='write', type=argparse.FileType('r'), help='从文件写入相机设置')
 printBackup = subparsers.add_parser('print_backup', description='打印 Backup.bin 文件的内容')
 printBackup.add_argument('backupFile', metavar='Backup.bin', type=argparse.FileType('rb'), help='备份文件')

 args = parser.parse_args()
 if args.command == 'info':
  infoCommand(args.driver)
 elif args.command == 'install':
  if args.appInteractive:
   pkg = appSelectionCommand()
   if not pkg:
    return
  else:
   pkg = args.appPackage
  installCommand(args.driver, args.apkFile, pkg, args.outFile)
 elif args.command == 'market':
  marketCommand(args.token)
 elif args.command == 'apk2spk':
  args.outFile.write(spk.dump(args.inFile.read()))
 elif args.command == 'spk2apk':
  args.outFile.write(spk.parse(args.inFile.read()))
 elif args.command == 'firmware':
  firmwareUpdateCommand(args.datFile, args.driver)
 elif args.command == 'updatershell':
  updaterShellCommand(args.model, args.fdatFile, args.driver)
 elif args.command == 'serviceshell':
  senserShellCommand()
 elif args.command == 'guess_firmware':
  guessFirmwareCommand(args.file, args.driver)
 elif args.command == 'gps':
  gpsUpdateCommand(args.file, args.driver)
 elif args.command == 'stream':
  streamingCommand(args.write, args.file, args.driver)
 elif args.command == 'wifi':
  wifiCommand(args.write, args.file, args.multi, args.driver)
 elif args.command == 'print_backup':
  printBackupCommand(args.backupFile)
 else:
  parser.print_usage()


if __name__ == '__main__':
 main()
