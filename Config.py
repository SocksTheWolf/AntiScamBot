import os
from dotenv import load_dotenv
from Logger import LogLevel, Logger
import json
import copy

load_dotenv()

class Config():
    def __init__(self):
        self.Load()

    def Load(self):
        Data = {}
        
        with open(self.GetConfigFile(), "r") as config_file:
            Data = json.load(config_file)
            
        self.__dict__ = Data
        Logger.Log(LogLevel.Notice, "Configuration Loaded!")
        
    def Save(self):
        StagingSave = copy.deepcopy(self.__dict__)
        with open(self.GetConfigFile(), "wt") as config_file:
            json.dump(StagingSave, config_file, indent=3)
            
    def __getitem__(self, item):
         return self.__dict__[item]
         
    def IsValid(self, Key:str, ExpectType) -> bool:
        try:
            EntryValue = self[Key]
            EntryValueType = type(EntryValue)
            if (EntryValueType != ExpectType):
                return False
            
            if (EntryValueType == int):
                if (EntryValue <= 0):
                    return False
                else:
                    return True
            elif (EntryValueType == str):
                if (len(EntryValue) == 0):
                    return False
                
                return True
            return False
        except(Exception):
            return False

    @staticmethod
    def GetToken():
        return os.getenv("DISCORD_TOKEN")

    @staticmethod    
    def GetDBFile():
        return os.getenv("DATABASE_FILE")
    
    @staticmethod
    def GetConfigFile():
        return os.getenv("CONFIG_FILE")
    
    def Dump(self):
        print(self.__dict__)