import time
import json
import Cargo
from emonhub_interfacer import EmonHubInterfacer

"""
[[Redis]]
    Type = EmonHubRedisInterfacer
    [[[init_settings]]]
        redis_host = localhost
        redis_port = 6379
        redis_db = 0
    [[[runtimesettings]]]
        subchannels = ToEmonCMS,
        prefix = "emonhub:"
"""

"""class EmonHubRedisInterfacer

Redis interfacer for use in development

"""

class EmonHubRedisInterfacer(EmonHubInterfacer):

    def __init__(self, name, redis_host='localhost', redis_port=6379, redis_db=0):
        """Initialize Interfacer

        """
        # Initialization
        super(EmonHubRedisInterfacer, self).__init__(name)
        self._settings.update(self._defaults)

        # Interfacer specific settings
        self._redis_settings = {'prefix': ''}
        
        # Only load module if it is installed        
        try: 
            import redis
            self.r = redis.Redis(redis_host,redis_port,redis_db)
        except ModuleNotFoundError as err:
            self._log.error(err)
            self.r = False

    def add(self, cargo):
        """set data in redis

        """
        if not self.r:
            return False
        
        nodeid = cargo.nodeid
        
        if len(cargo.names)<=len(cargo.realdata):
            for i in range(0,len(cargo.names)):
                name = cargo.names[i]
                value = cargo.realdata[i]
                
                name_parts = []
                if self._settings['prefix']!='': name_parts.append(self._settings['prefix'])
                name_parts.append(str(nodeid))
                name_parts.append(str(name))
                
                name = ":".join(name_parts)
                
                self._log.info("redis set "+name+" "+str(value))
                try:
                    self.r.set(name,value)
                except Exception as err:
                    self._log.error(err)
                    return False

    def set(self, **kwargs):
        for key, setting in self._redis_settings.items():
            # Decide which setting value to use
            if key in kwargs:
                setting = kwargs[key]
            else:
                setting = self._redis_settings[key]
            if key in self._settings and self._settings[key] == setting:
                continue
            elif key == 'prefix':
                self._log.info("Setting %s prefix: %s", self.name, setting)
                self._settings[key] = setting
                continue
            else:
                self._log.warning("'%s' is not valid for %s: %s", setting, self.name, key)

        # include kwargs from parent
        super().set(**kwargs)
