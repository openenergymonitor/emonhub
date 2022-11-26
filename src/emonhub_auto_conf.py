"""

  This code is released under the GNU Affero General Public License.

  OpenEnergyMonitor project:
  http://openenergymonitor.org

"""

import time
import logging
from configobj import ConfigObj
import emonhub_coder as ehc
"""class EmonHubAutoConf

"""

auto_conf_enabled = False

available = {}

def match_from_available(nodeid,realdata):
    if not nodeid.isnumeric():
        return False

    match = False
    # Find templates that match data length
    datalength_match = []
    for nodekey in available:
        if 'datalength' in available[nodekey]:
            if len(realdata)==available[nodekey]['datalength']:
                datalength_match.append(nodekey)
    # If we have a datalength match, attempt to match nodeid
    if len(datalength_match):
        for nodekey in datalength_match:
            if nodeid in available[nodekey]['nodeids']:
                match = nodekey
                break
        # if no nodeid match assume first datalength match
        if not match:
            match = datalength_match[0]
            
    return match


class EmonHubAutoConf:
    
    def __init__(self,settings):
        filename = "/opt/openenergymonitor/emonhub/conf/available.conf"
    
        # Initialize logger
        self._log = logging.getLogger("EmonHub")
        
        self.enabled = False
        
        if 'autoconf' in settings['hub']:
            if int(settings['hub']['autoconf'])==1:
                self.enabled = True
            else: 
                self.enabled = False
                
        if self.enabled:
            self._log.debug("Automatic configuration of nodes enabled")
        else:
            self._log.debug("Automatic configuration of nodes disabled")    
                   
        # Initialize attribute settings as a ConfigObj instance
        try:
            result = ConfigObj(filename, file_error=True)
            self.available = self.prepare_available(result['available'])
        except Exception as e:
            raise EmonHubAutoConfError(e)

    def prepare_available(self,nodes):
        for n in nodes:
            if 'nodeids' in nodes[n]:
                nodes[n]['nodeids'] = list(map(int,nodes[n]['nodeids']))
            if 'datacodes' in nodes[n]['rx']:  
                datasizes = []
                for code in nodes[n]['rx']['datacodes']:
                    datasizes.append(ehc.check_datacode(str(code)))
                nodes[n]['datalength'] = sum(datasizes)
            if 'scales' in nodes[n]['rx']:
                for i in range(0,len(nodes[n]['rx']['scales'])):
                    nodes[n]['rx']['scales'][i] = float(nodes[n]['rx']['scales'][i])
            if 'whitening' in nodes[n]['rx']:
                nodes[n]['rx']['whitening'] = int(nodes[n]['rx']['whitening'])
        return nodes

"""class EmonHubSetupInitError

Raise this when init fails.

"""
class EmonHubAutoConfError(Exception):
    pass
