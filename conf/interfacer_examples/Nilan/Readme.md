EmonHub Interfacer for Nilan exhaust air & heat recovery heat pumps https://nilanuk.com/nilan-compact-p-range/

Modbus Docs: https://nilan.fr/docs/nilandocs/residentiels/CTS602_w_HMI350T_Modbus.pdf 

```
[[Nilan]]
    Type = EmonHubMinimalModbusInterfacer
    [[[init_settings]]]
        device = /dev/ttyACM*
        baud = 19200
        parity = even
        datatype = int
    [[[runtimesettings]]]
        pubchannels = ToEmonCMS,
        # Increased to 30 seconds to allow time for ~55 Modbus sequential reads
        read_interval = 30
        nodename = Nilan
        [[[[meters]]]]

            # ---------------------------------------------------------
            # NODE 1: All Temperatures & Humidity (Input Registers, FC4)
            # ---------------------------------------------------------
            [[[[[CTS602_Temps]]]]]
                address = 30
                functioncodes = 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4
                registers = 200, 201, 202, 203, 204, 205, 206, 207, 208, 209, 210, 211, 212, 213, 214, 215, 216, 217, 218, 221
                names = T0_Controller, T1_Intake, T2_Inlet, T3_Exhaust, T4_Outlet, T5_Cond, T6_Evap, T7_Inlet, T8_Outdoor, T9_Heater, T10_Extern, T11_Top, T12_Bottom, T13_Return, T14_Supply, T15_Room, T16_AUX, T17_PreHeat, T18_PresPibe, Humidity
                # All values here are scaled by 100 in the device
                scales = 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01
                precision = 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2

            # ---------------------------------------------------------
            # NODE 2: System Status, Airflow & Pressures (Input Registers, FC4)
            # ---------------------------------------------------------
            [[[[[CTS602_Status]]]]]
                address = 30
                functioncodes = 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4
                registers = 100, 101, 106, 219, 220, 222, 1000, 1001, 1002, 1003, 1100, 1101, 1102, 1205, 1206, 2201, 2202, 2221, 2222
                names = UserFunc, FilterAlarm, AirFlowMon, pSuc_bar, pDis_bar, CO2_ppm, RunAct, ModeAct, StateDisplay, SecInState, VentSet, InletAct, ExhaustAct, CapSet, CapAct, AirFlow1_m3h, AirFlow2_m3h, Pressure1_Pa, Pressure2_Pa
                # CapSet and CapAct are scaled by 100, the rest are unscaled
                scales = 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0.01, 0.01, 1, 1, 1, 1
                precision = 0, 0, 0, 2, 2, 0, 0, 0, 0, 0, 0, 0, 0, 2, 2, 0, 0, 0, 0

            # ---------------------------------------------------------
            # NODE 3: Active Outputs & User Settings (Holding Registers, FC3)
            # ---------------------------------------------------------
            [[[[[CTS602_Outputs]]]]]
                address = 30
                functioncodes = 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3
                registers = 100, 102, 109, 114, 116, 127, 200, 201, 202, 204, 205, 206, 1001, 1002, 1003, 1004
                names = AirFlap, BypassOpen, Compressor, CondOpen, WaterHeat, PreHeat, ExhaustSpeed, InletSpeed, AirHeatCap, CprCap, PreHeatCap, RotorVeksler, RunSet_User, ModeSet_User, VentSet_User, TempSet_User
                # Speeds, capacities, and TempSet are scaled by 100
                scales = 1, 1, 1, 1, 1, 1, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 1, 1, 1, 0.01
                precision = 0, 0, 0, 0, 0, 0, 2, 2, 2, 2, 2, 2, 0, 0, 0, 2
```
