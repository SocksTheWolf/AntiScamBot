from enum import auto
from colorama import Fore, Style, init
from EnumWrapper import CompareEnum
import datetime
import time
import asyncio

__all__ = ["LogLevel", "Logger"]

class LogLevel(CompareEnum):
  Debug=auto()
  Verbose=auto()
  Log=auto()
  Warn=auto()
  Error=auto()
  Notice=auto()
  Silence=auto()

CurrentLoggingLevel = LogLevel.Verbose
CurrentNotificationLevel = LogLevel.Warn
HasInitialized = False
NotificationCallback = None

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
    global NotificationCallback
    
    if Level < CurrentLoggingLevel:
      return
    
    if CurrentLoggingLevel == LogLevel.Silence:
      return
    
    # Set up color logging
    ColorStr = ""
    MessageStr = f"ScamBot [{str(Level)}]: {Input}"
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

    print(Logger.PrintDate() + f"{ColorStr} {MessageStr}" + Style.RESET_ALL)
    
    if (NotificationCallback is not None and Level >= CurrentNotificationLevel):
      try:
        CurrentLoop = asyncio.get_running_loop()
      except RuntimeError:
        # If there is no currently running loop, then don't bother sending notification messages
        return
      
      # This will automatically get added to the task loop.
      CurrentLoop.create_task(NotificationCallback(MessageStr))
      
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
  
  @staticmethod
  def SetNotificationCallback(NewCallback):
    global NotificationCallback
    NotificationCallback = NewCallback

Logger.Start()