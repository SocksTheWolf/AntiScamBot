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
  
class RelayMessageType(CompareEnum):
  Hello=auto()
  BanUser=auto()
  UnbanUser=auto()
  LeaveServer=auto()
  ReprocessBans=auto()
  ReprocessInstance=auto()
  ProcessActivation=auto()
  ProcessDeactivation=auto()
  CloseApplication=auto()
  # TODO: In future to remove the number of writers
  AddedToServer=auto()
  RemovedFromServer=auto()
  ServerOwnerChanged=auto()