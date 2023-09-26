from enum import IntEnum, auto
from colorama import Fore, Style, init
import datetime
import time

__all__ = ["LogLevel", "Logger"]

class LogLevel(IntEnum):
  Debug=auto()
  Verbose=auto()
  Log=auto()
  Warn=auto()
  Error=auto()
  Notice=auto()
  Silence=auto()
  
  def __lt__(self, other):
    if self.__class__ is other.__class__:
      return self.value < other.value
    return NotImplemented
      
  def ToString(self):
    return self.name

CurrentLoggingLevel = LogLevel.Verbose
HasInitialized = False

class Logger():
  @staticmethod
  def Start():
    global HasInitialized
    if (not HasInitialized):
      init()
      HasInitialized = True

  @staticmethod
  def GetTimestamp():
    return time.time()
    
  @staticmethod
  def PrintDate():
    NowTime = str(datetime.datetime.now())
    return f"[{NowTime}] "

  @staticmethod
  def Log(Level:LogLevel, Input:str):
    
    if Level < CurrentLoggingLevel:
      return
    
    # Set up color logging for lightbot
    ColorStr = ""
    if Level == LogLevel.Error:
      ColorStr = Fore.RED + Style.BRIGHT
    elif Level == LogLevel.Warn:
      ColorStr = Fore.YELLOW + Style.BRIGHT
    elif Level == LogLevel.Verbose:
      ColorStr = Style.DIM
    elif Level == LogLevel.Debug:
      ColorStr = Style.BRIGHT + Fore.BLACK
    elif Level == LogLevel.Notice:
      ColorStr = Fore.GREEN + Style.BRIGHT
      
    print(Logger.PrintDate() + f"ScamBot:{ColorStr} {Input}" + Style.RESET_ALL)
      
  @staticmethod
  def SetLogLevel(NewLevel: LogLevel):
    global CurrentLoggingLevel
    
    CurrentLoggingLevel = NewLevel
    
  @staticmethod
  def GetLogLevel():
    return CurrentLoggingLevel
    
  @staticmethod
  def GetLogLevelName():
    return CurrentLoggingLevel.name

Logger.Start()