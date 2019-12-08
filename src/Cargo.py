import time

class EmonHubCargo:
    uri = 0

    # The class "constructor" - It's actually an initializer
    def __init__(self, timestamp, target, nodeid, nodename, names, realdata, rssi, rawdata):
        EmonHubCargo.uri += 1
        self.uri = EmonHubCargo.uri
        self.timestamp = float(timestamp)
        self.target = int(target)
        self.nodeid = int(nodeid)
        self.nodename = nodename
        self.names = names
        self.realdata = realdata
        self.rssi = int(rssi)

        # self.datacodes = []
        # self.datacode = ""
        # self.scale = 0
        # self.scales = []
        self.rawdata = rawdata
        self.encoded = {}
        # self.realdatacodes = []

def new_cargo(rawdata="", nodename=False, names=[], realdata=[], nodeid=0, timestamp=0.0, target=0, rssi=0.0):
    return EmonHubCargo(timestamp or time.time(), target, nodeid, nodename, names, realdata, rssi, rawdata)
