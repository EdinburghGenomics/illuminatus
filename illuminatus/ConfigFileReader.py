#!/usr/bin/env python3

import configparser , sys , os

class ConfigFileReader:
    """Uses the configparser to parse a given .ini file. Information can be accessed via get_value() function.
    """
    def __init__( self , config_file ):
        if os.path.exists( config_file ):
            self.Config = configparser.ConfigParser()
            self.Config.read(config_file)
        else:
           self.Config = None

    def get_value( self , section , option ):
        ## return None if value is not in the settings file
        try:
            return self.Config.get(section, option)
        except Exception:
            return None

    def get_all_options( self , section ):
        ## return empty list if nothing was found
        try:
            return self.Config.options(section)
        except Exception:
            return []


if __name__ == '__main__':
    ini_file = sys.argv[1]
    section = sys.argv[2]
    option = sys.argv[3]

    conf = ConfigFileReader(ini_file)
    print ( conf.get_value( section , option ) )


