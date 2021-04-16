### Socket Interfacer

The EmonHub socket interfacer is particularly useful for inputing data from a range of sources. e.g a script monitoring server status where you wish to post the result to both a local instance of emoncms and a remote instance of emoncms alongside other data from other sources such as rfm node data.

As an example, the following python script will post a single line of data values on node 98 to an emonhub instance running locally and listening on port 8080:

```python
import socket, time
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(('localhost', 8080))
s.sendall('98 3.8 1.6 5.2 80.3\r\n')
```

The following emonhub.conf interfacer definition will listen on the choosen socket and forward the data on the ToEmonCMS channel:

```text
    [[mysocketlistener]]
            Type = EmonHubSocketInterfacer
            [[[init_settings]]]
                port_nb = 8080
            [[[runtimesettings]]]
                pubchannels = ToEmonCMS,
```

**Timestamped data**

To set a timestamp for the posted data add the timestamped property to the emonhub.conf runtimesettings section:

```text
        [[[runtimesettings]]]
            pubchannels = ToEmonCMS,
            timestamped = True
```

The python client example needs to include the timestamp e.g:

```python
s.sendall(str(time.time())+' 98 3.8 1.6 5.2 80.3\r\n')
```
