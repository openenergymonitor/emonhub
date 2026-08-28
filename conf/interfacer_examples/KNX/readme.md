### KNX Reader to read value from knx group using a knx Gateway

KNX Reader is base on the use of the xknkx library:
https://pypi.org/project/xknx/

KNX is a international standard for home automation.
KNX is based on a bus, where each device can communicate using knx group.
A Knx group is address using a knx address group notation of the form x/y/z.

To configure this interfacers, you would need:

to fill the global init_settings, mainly:

- **gateway_ip** The ip address of your ip gateway device.
- **port** The port of the gateway device (3671 is the default).
- **local_ip** If your server have multiple ip interface, indicate the ip of the interface link to the gateway device.

In runtimeseetings, you will have to list the group you want to read.
You can make some grouping by indicating a devicename under the meters section

Each device can contains single or many group read section of the form:
 [[[[[[groupName]]]]]]
        group=10/0/1
        eis=DPT-14

- **groupName:** Will indicate the name of the group, indicate what you want, it will be the name of the input in emoncms inputs.
- **group:** The address of the group
- **eis:** The KNX type use for this group (please refer to KNX official documentation for the list).


```text
[[KNX]]
    Type = EmonHubKNXInterfacer
    [[[init_settings]]]
        gateway_ip = 192.168.254.1
        port = 3671
    [[[runtimesettings]]]
        pubchannels = ToEmonCMS,
        read_interval = 5
        validate_checksum = False
        nodeid=1
        nodename = KNX
        [[[[meters]]]]
            [[[[[compteur]]]]]
                  [[[[[[voltage]]]]]]
                      group=10/0/1
                      eis=DPT-14
                  [[[[[[intensite]]]]]]
                      group=10/1/1
                      eis=DPT-14
                  [[[[[[puissance]]]]]]
                      group=10/2/1
                      eis=DPT-14
                  [[[[[[consommation]]]]]]
                      group=10/3/1
                      eis=DPT-12
                  [[[[[[consommationWh]]]]]]
                      group=10/5/1
                      eis=DPT-12
             [[[[[compteurNew]]]]]
                  [[[[[[voltage]]]]]]
                      group=10/0/2
                      eis=DPT-14
                  [[[[[[intensite]]]]]]
                      group=10/1/2
                      eis=DPT-14



