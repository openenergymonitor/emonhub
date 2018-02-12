"""class EmonHubGraphiteInterfacer
"""
import time
import socket
from emonhub_interfacer import EmonHubInterfacer

class EmonHubGraphiteInterfacer(EmonHubInterfacer):

    def __init__(self, name):
        # Initialization
        super(EmonHubGraphiteInterfacer, self).__init__(name)

        self._defaults.update({'batchsize': 100,'interval': 30})
        self._settings.update(self._defaults)

        # interfacer specific settings        
        self._graphite_settings = {
            'graphite_host': 'localhost',
            'graphite_port': '2003',
            'prefix': 'emonpi'
        }

        self.lastsent = time.time()
        self.lastsentstatus = time.time()
        
        # set an absolute upper limit for number of items to process per post
        self._item_limit = 250

    def _process_post(self, cargodatabuffer):
    
        metrics = []
        for c in range(0,len(cargodatabuffer)):
            cargo = cargodatabuffer[c]
            nodestr = str(cargo.nodeid)
            if cargo.nodename!=False: nodestr = str(cargo.nodename)
            
            varid = 1
            for value in cargo.realdata:
                # Variable id or variable name if given
                varstr = str(varid)
                if (varid-1)<len(cargo.names):
                    varstr = str(cargo.names[varid-1])
                    # Construct path
                path = self._settings['prefix']+'.'+nodestr+"."+varstr
                payload = str(value)
                
                timestamp = int(float(cargo.timestamp))

                metrics.append(path+" "+payload+" "+str(timestamp))
                varid += 1
                
        return self._send_metrics(metrics)

    def _send_metrics(self, metrics=[]):
        """

        :param post_url:
        :param post_body:
        :return: the received reply if request is successful
        """
        """Send data to server.

        metrics (list): metric path and values (eg: '["path.node1 val1 time","path.node2 val2 time",...]')

        return True if data sent correctly

        """

        host = str(self._settings['graphite_host']).strip('[\'\']')
        port = int(str(self._settings['graphite_port']).strip('[\'\']'))
        self._log.debug("Graphite target: {}:{}".format(host, port))
        message = '\n'.join(metrics)+'\n'
        self._log.debug("Sending metrics:\n"+message)

        try:
            sock = socket.socket()
            sock.connect((host, port))
            sock.sendall(message)
            sock.close()
        except socket.error as e:
            self._log.error(e)
            return False
            
        return True
    
    def set(self, **kwargs):
        super (EmonHubGraphiteInterfacer, self).set(**kwargs)
        for key,setting in self._graphite_settings.iteritems():
            if key in kwargs.keys():
                # replace default
                self._settings[key] = kwargs[key]

    """
    def set(self, **kwargs):
        super (EmonHubGraphiteInterfacer, self).set(**kwargs)
        for key, setting in self._graphite_settings.iteritems():
            #valid = False
            if not key in kwargs.keys():
                setting = self._graphite_settings[key]
            else:
                setting = kwargs[key]
            if key in self._settings and self._settings[key] == setting:
                continue
            elif key == 'graphite_host':
                self._log.info("Setting " + self.name + " graphite_host: " + setting)
                self._settings[key] = setting
                continue
            elif key == 'graphite_port':
                self._log.info("Setting " + self.name + " graphite_port: " + setting)
                self._settings[key] = setting
                continue
            elif key == 'prefix':
                self._log.info("Setting " + self.name + " prefix: " + setting)
                self._settings[key] = setting
                continue
            else:     
                self._log.warning("'%s' is not valid for %s: %s" % (setting, self.name, key))          
    """
