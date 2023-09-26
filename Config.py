import os
from dotenv import load_dotenv
from Logger import LogLevel, Logger
import json
import copy

load_dotenv()
CONFIGLOC=os.getenv("CONFIG_FILE")

class Config():
    def __init__(self):
        self.Load()

    def Load(self):
        Data = {}
        
        with open(CONFIGLOC, "r") as config_file:
            Data = json.load(config_file)
            
        self.__dict__ = Data
        Logger.Log(LogLevel.Notice, "Configuration Loaded!")
        
    def Save(self):
        StagingSave = copy.deepcopy(self.__dict__)
        with open(CONFIGLOC, "wt") as config_file:
            json.dump(StagingSave, config_file, indent=3)
            
    def __getitem__(self, item):
         return self.__dict__[item]
   
    def GetToken(self):
        return os.getenv("DISCORD_TOKEN")
    
    def Dump(self):
        print(self.__dict__)