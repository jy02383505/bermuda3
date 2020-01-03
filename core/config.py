import configparser

config = configparser.RawConfigParser()
config.read('/Application/bermuda3/conf/bermuda.conf')

def initConfig():
    config = configparser.RawConfigParser()
    config.read('/Application/bermuda3/conf/bermuda.conf')
    return config