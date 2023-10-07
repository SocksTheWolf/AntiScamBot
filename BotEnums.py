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