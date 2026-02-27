### econext-gateway

This interfacer polls an [econext-gateway](https://github.com/LeeNuss/econext-gateway) instance (RS-485 gateway for GM3-based ecoNET heat pump controllers) to retrieve heat pump telemetry and expose it to emonhub channels.

Example configuration:

    [[EconextGateway]]
        Type = EmonHubEconextInterfacer
        [[[init_settings]]]
            # Hostname or IP address of the econext-gateway
            host = localhost
            # Gateway API port
            port = 8000
        [[[runtimesettings]]]
            pubchannels = ToEmonCMS,
            # Poll interval in seconds
            pollinterval = 60
            nodeid = 30
            parameters = TempOutlet, TempReturn, ElectricPower, HeatingPower, Circuit1CalcTemp, Circuit1thermostat, flapValveStates
            # Full list of parameters: https://github.com/LeeNuss/econext-gateway/blob/main/docs/PARAMETERS.md

Default parameters fetched from the gateway:

| Gateway Name | Input Name | Description |
|---|---|---|
| TempWthr | OutdoorTemp | Outdoor temperature |
| Circuit2CalcTemp | Circuit2TargetTemp | Circuit 2 target temperature |
| HDWTSetPoint | DHWSetPoint | DHW set point |
| TempCWU | DHWTemp | DHW temperature |
| Circuit2thermostatTemp | RoomTemp | Room temperature |
| HeatSourceCalcPresetTemp | TargetTemp | Heat source target temperature |
| currentFlow | FlowRate | Flow rate |
| HPStatusFanRPM | FanSpeed | Fan speed |
| HPStatusComprHz | CompressorFreq | Compressor frequency |
| flapValveStates | DHWStatus / CHStatus | Computed: DHW and CH status booleans |

Additional parameters can be added or default names overridden via the `parameters` runtime setting. Each entry is `GatewayName` (uses the gateway name as-is) or `GatewayName:InputName` (renames the input):

Full list of parameters: https://github.com/LeeNuss/econext-gateway/blob/main/docs/PARAMETERS.md

    [[[runtimesettings]]]
        pubchannels = ToEmonCMS,
        pollinterval = 60
        nodeid = 30
        parameters = ReturnTemp, HPModulationPercent:Modulation
