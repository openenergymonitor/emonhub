# Graphite interfacer

Graphite is an enterprise-ready timeseries database capable of collecting millions of metrics per minute.
It has a powerful API and function set for querying and manipulating the data.
For details on graphite see <https://graphiteapp.org/>

It is frequently paired with [Grafana](http://grafana.org/) for dashboards and visualizations


## Usage and configuration
Simply configure interface with host, port and interval of your graphite installation.
Metrics get sent to a path similar to the nodevar format as MQTT interface.

Ex: `<prefix>.emonPi.power1`

### Parameters

* `pubchannels` and `subchannels`

  Same usage as other interfacers

* `graphite_host`

  Host or IP of your graphite server

* `graphite_port`

  Graphite tcp metrics port. (Default: 2003)

* `senddata`

  Set to 0 to disable sending metrics. (Default: 1)

* `sendinterval`

  Frequency, in seconds, to send metrics. (Default: 30)
  (Should be set the same in your graphite storage scheme)

* `prefix`

  Prefix for graphite storage path. (Default: emonpi)

### Sample interfacer config within emonhub.conf

```
    [[Graphite]]
        Type = EmonHubGraphiteInterfacer
        [[[init_settings]]]
        [[[runtimesettings]]]
            pubchannels = ToRFM12,
            subchannels = ToEmonCMS,
            graphite_host = graphite.example.com,
            graphite_port = 2003,
            senddata = 1,
            sendinterval = 30,
            prefix = emonpi
```

With this config in place now you simply need to restart emonhub on your emonpi by ssh'ing into it and typing 

      $> sudo service emonhub restart

If there are any problems you can debug by looking inside /var/emonhub/emonhub.log
