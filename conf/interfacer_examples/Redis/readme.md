### Redis

Writes latest sensor values (or emonhub cargo objects) to redis keys. Makes it easy to then pick up the values in a separate python script used for automation.

[[Redis]]
    Type = EmonHubRedisInterfacer
    [[[init_settings]]]
        redis_host = localhost
        redis_port = 6379
        redis_db = 0
    [[[runtimesettings]]]
        subchannels = ToEmonCMS,
        prefix = "emonhub:"
