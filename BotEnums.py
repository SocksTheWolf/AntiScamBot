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
  BansExceeded=auto()
  ServerOwner=auto()
  Error=auto()
  
class RelayMessageType(CompareEnum):
  Hello=auto()
  BanUser=auto()
  UnbanUser=auto()
  LeaveServer=auto()
  ReprocessBans=auto()
  ReprocessInstance=auto()
  # This activates all servers that an user is a mod in
  ProcessActivation=auto()
  # This activates specifically for one server
  ProcessServerActivation=auto()
  ProcessDeactivation=auto()
  Ping=auto()
  # TODO: In future to remove the number of writers
  AddedToServer=auto()
  RemovedFromServer=auto()
  ServerOwnerChanged=auto()
  # TODO: Add enqueue messages to fix issue #64