from enum import IntEnum, auto

class CompareEnum(IntEnum):  
  def __lt__(self, other):
    if self.__class__ is other.__class__:
      return self.value < other.value
    return NotImplemented
      
  def ToString(self) -> str:
    return self.name