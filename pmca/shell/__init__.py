import abc
from collections import OrderedDict

from .parser import *

class BaseCommand(abc.ABC):
 @abc.abstractmethod
 def help(self):
  pass

 @abc.abstractmethod
 def run(self, parser):
  pass


class SubCommand(BaseCommand):
 def __init__(self):
  self._commands = OrderedDict()

 def addCommand(self, name, cmd):
  self._commands[name] = cmd

 def help(self, path=''):
  return '\n'.join(cmd.help('%s %s' % (path, name)) for name, cmd in self._commands.items())

 def run(self, parser):
  name = parser.consumeRequiredArg()
  if name not in self._commands:
   raise Exception('未知命令')
  self._commands[name].run(parser)


class Command(BaseCommand):
 def __init__(self, func, args, help, argHelp=''):
  self._func = func
  self._args = args
  self._help = help
  self._argHelp = argHelp

 def help(self, path):
  return '%-24s %s' % ('%s %s' % (path, self._argHelp), self._help)

 def run(self, parser):
  self._func(*parser.consumeArgs(*self._args))


class ResidueCommand(Command):
 def run(self, parser):
  self._func(*[parser.consumeRequiredArg() for i in range(self._args)], parser.getResidue())


class Shell:
 def __init__(self, name):
  self.name = name
  self.running = False
  self.commands = SubCommand()

  self.addCommand('help', Command(self.help, (), '打印此帮助信息'))
  self.addCommand('exit', Command(self.exit, (), '退出'))

 def addCommand(self, name, cmd):
  self.commands.addCommand(name, cmd)

 def run(self):
  print('欢迎使用 %s。' % self.name)
  print('输入 `help` 查看支持的命令列表。')
  print('输入 `exit` 退出。')

  self.running = True
  while self.running:
   try:
    cmd = input('>').strip()
   except KeyboardInterrupt:
    print('')
    continue

   try:
    parser = ArgParser(cmd)
    if not parser.available():
     continue
    self.commands.run(parser)
   except Exception as e:
    print('错误：%s' % e)

 def help(self):
  print('支持的命令列表：')
  print(self.commands.help())

 def exit(self):
  self.running = False
