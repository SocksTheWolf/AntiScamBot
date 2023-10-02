from EnumWrapper import CompareEnum
from enum import auto

class BanLookup(CompareEnum):
  Good=auto()
  Banned=auto()
  Unbanned=auto()
  Duplicate=auto()
  NotExist=auto()
  DBError=auto()
  
class BanResult(CompareEnum):
  Processed=auto()
  NotBanned=auto()
  InvalidUser=auto()
  LostPermissions=auto()
  ServerOwner=auto()
  Error=auto()

class CommandPermission(CompareEnum):
  Anyone=auto()
  ControlServerUser=auto()
  Approver=auto()
  Maintainer=auto()
  Developer=auto()
  
  @staticmethod
  def CanUse(Level, InServer:bool, Approver:bool, Maintainer:bool, Developer:bool):
      if (Level == CommandPermission.Approver):
          return Approver
      elif (Level == CommandPermission.Maintainer):
          return Maintainer
      elif (Level == CommandPermission.ControlServerUser):
          return InServer
      elif (Level == CommandPermission.Developer):
          return Developer
      elif (Level == CommandPermission.Anyone):
          return True
      else:
          return False