import os
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from tkinter.ttk import *
from tkinter import *
import threading
from simple_pid import PID
import xlrd
import time
import serial
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt  #for live plot? future work
from matplotlib.figure import Figure
import matplotlib.animation as animation   #for live plot
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg  # , NavigationToolbar2TkAgg
from matplotlib import style
from pandas import *
import pandas as pd
import csv
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

import random
from maq20 import MAQ20

LARGE_FONT = ("Verdana", 12)
REG_FONT = ("Verdana", 9)
style.use("ggplot")  # can use other styles as well

exit_case = False  # when set to true all threads will close properly
SHED1 = False  # to keep track of SHED status
SHED2 = False
SHED3 = False
SHED_ready = [0, 0, 0]  # 0 is not requested, 1 is requested but not ready 2 is requested and ready
ref_rate = 100  # refresh rate of value on GUI, might be updated via config file
loc = ("config/config.xlsx")  # Location of Config File
wb = xlrd.open_workbook(loc)
sheet = wb.sheet_by_index(0)
sheet2 = wb.sheet_by_index(1)

ref_rate = int(sheet.cell_value(2, 1))  # Update ref_rate from config file
XX = int(sheet.cell_value(3, 1))  # Update X value of screen size in pixels
YY = int(sheet.cell_value(4, 1))  # Update Y value of screen size in pixels
ppg = [0] * 8
for n in range(0, 8):
    ppg[n] = float(sheet.cell_value(6, n + 1))  # Update Pulses per gallon according to the Manufacturer's Specs
frequency=[0]*8
deadhead_protection = sheet.cell_value(22, 1)
valve_op_volt = sheet.cell_value(21, 1)  # operational valve voltage -> changed to 5 for testing on 5V system .
manual_mode_individual = [0] * 8
manual_mode_all = 0
##########################################################
#                  PID Setup values                      #
##########################################################
pid1 = 0
pid2 = 0
P1 = int(sheet.cell_value(8, 1))
I1 = int(sheet.cell_value(9, 1))
D1 = int(sheet.cell_value(10, 1))
P2 = int(sheet.cell_value(8, 2))
I2 = int(sheet.cell_value(9, 2))
D2 = int(sheet.cell_value(10, 2))

set_temp = [25, 25]
pid1 = PID(P1, I1, D1, set_temp[0])  # PID for SHED2
pid1.output_limits = (0, 10)
pid2 = PID(P2, I2, D2, set_temp[1])  # PID for SHED3
pid2.output_limits = (0, 10)
pid_vout = [0]*2

pid1_io = int(sheet.cell_value(9,5))    # PID SHED2  on/off setting from config file
pid2_io = int(sheet.cell_value(9,6))      # PID SHED2  on/off setting from config file

deadhead_io =  0
deadhead_io = int(sheet.cell_value(23,1))
alarm_io = 0
alarm_io = int(sheet.cell_value(57,1))


def function_io(variable):# switch function (as of 12/11/2020 is not working)
    """
    :param variable: global variable to switch
    :return: switch variable from 1->0 or 0->1 for on/off
    """
    variable = 1 - variable
    return variable

##################################################### #############################
###                 Temperature Sensor smoothing and calibration                ###
###################################################################################
smoothing_size = int(sheet.cell_value(17, 1))  # size of list used for smoothing average
smooth_t2 = 0
smooth_t3 = 0
T_shed2 = [20] * smoothing_size  # initiate list as size of smoothing_size with base
T_shed3 = [20] * smoothing_size
set_temp = [20] * 2

# Calibration Values for SHED temperature sensors
cal1 = sheet.cell_value(12, 1)
cal2 = sheet.cell_value(13, 1)
cal3 = sheet.cell_value(14, 1)
cal4 = sheet.cell_value(15, 1)

#######################################################################################################################
###                                             Important functional                                                ###
#######################################################################################################################
alarm_status = [0, 0, 0]
alarm_active = [0] * 3  # allows control of alarm system from config sheet
alarm_active[0] = int(sheet.cell_value(53, 1))
alarm_active[1] = int(sheet.cell_value(54, 1))
alarm_active[2] = int(sheet.cell_value(55, 1))
alarm_status_exhaust = 0
alarm_active_exhaust = int(sheet.cell_value(56, 1))
gas_analyzer_SHED2 = 0.1
gas_analyzer_SHED3 = 0.1
gas_analyzer_lower_SHED2 = int(sheet.cell_value(50, 1))
gas_analyzer_upper_SHED2 = int(sheet.cell_value(50, 2))
gas_analyzer_lower_SHED3 = int(sheet.cell_value(51, 1))
gas_analyzer_upper_SHED3 = int(sheet.cell_value(51, 2))



#######################################################################################################################
###                                             PLOT FUNTIONAL                                                      ###
#######################################################################################################################


priority = "main"  # for Savefile.csv
start_date_time = datetime.now().strftime("%d-%b-Y_H-%M-%S")
filename = "\DATALOGS\\main_LOGfile_03-Sep-2020_08-23-23.csv"
plot_length = 100

# Plot stuff and Liveplot
f = Figure(figsize=(7, 3), dpi=80)
a = f.add_subplot(111)
f2 = Figure(figsize=(7, 3), dpi=80)
a2 = f2.add_subplot(111)

xvals = 'Entry Time'
yvals = 'T3'

ylist = []
# a.xlabel('Time')
# a.ylabel('Temperature')
# a.title("SHED Temperature te")
#######################################################################################################################
###                                              GUI stuff                                                          ###
#######################################################################################################################
index = 0
flash_index = 0

circle_diam = 30  # diameter of Status light circles


def greenCircle(circleCanvas):
    circleCanvas.create_oval(1, 1, circle_diam - 1, circle_diam - 1, width=0, fill='black')
    circleCanvas.create_oval(3, 3, circle_diam - 3, circle_diam - 3, width=0, fill='green')


def redCircle(circleCanvas):
    circleCanvas.create_oval(1, 1, circle_diam - 1, circle_diam - 1, width=0, fill='black')
    circleCanvas.create_oval(3, 3, circle_diam - 3, circle_diam - 3, width=0, fill='red')


def yellowCircle(circleCanvas):
    circleCanvas.create_oval(1, 1, circle_diam - 1, circle_diam - 1, width=0, fill='black')
    circleCanvas.create_oval(3, 3, circle_diam - 3, circle_diam - 3, width=0, fill='yellow')


flow_width = 8
pump_width = 5
flow_temp_width = 8
valve_width = 10

counter = 0
prev_count = [0] * 8
prev_time = time.time()

flow_status = [0, 0,
               0]  # Flow status check for checking if there is backflow: 0 is off, 1 is good to go, 2 is backflow in cold loop, 3 is backflow in hot loop
temp_status = [False] * 8  # Temp Status Check to make sure flow temp is in operation range
SHED_temp_status = [False] * 2
SHED_lower_bound = [int(sheet.cell_value(46, 1)), int(sheet.cell_value(47, 1))]
SHED_upper_bound = [int(sheet.cell_value(46, 2)), int(sheet.cell_value(47, 2))]
flowrate_status = [False] * 8  # Flowrate Checkup
temp_lower_bound = [0] * 8
temp_higher_bound = [0] * 8
flow_lower_bound = [0] * 8
flow_higher_bound = [0] * 8
for i in range(0, len(temp_lower_bound)):
    temp_lower_bound[i] = int(sheet.cell_value(26 + i, 1))
    temp_higher_bound[i] = int(sheet.cell_value(26 + i, 2))
    flow_lower_bound[i] = int(sheet.cell_value(36 + i, 1))
    flow_higher_bound[i] = int(sheet.cell_value(36 + i, 2))


def flash__():  # flash function for GUI flashing
    global flash_index
    flash_index = 1 - flash_index


#######################################################################################################################
###                                   Input Variable Definition                                                     ###
#######################################################################################################################
demo = int(sheet.cell_value(2,5))
ip = sheet.cell_value(1, 1)
if demo == 0:
    maq20 = MAQ20(ip_address=ip, port=502)  # Set communication with MAQ20

    mod1_AI = maq20[1]  # Analog input module
    mod2_TTC = maq20[2]  # Thermocouple nput module.
    mod4_DIV20 = maq20[4]  # 20 digital discrete inputs
    mod5_DIOL = maq20[5]  # 5 Digital discrete inputs, 5 Digital outputs
    mod6_DIOL = maq20[6]  # 5 Digital discrete inputs, 5 Digital outputs
    mod7_DIOL = maq20[7]  # 5 Digital discrete inputs, 5 Digital outputs
    mod8_DIOL = maq20[8]  # 5 Digital discrete inputs, 5 Digital outputs
    mod3_AO = maq20.find("VO")  # alternative to calling maq20[3] which is the position of mod3_AO

    # Read input values from Modules
    DIOL_1 = (mod5_DIOL.read_data_counts(0, number_of_channels=mod5_DIOL.get_number_of_channels()))
    DIOL_2 = (mod6_DIOL.read_data_counts(0, number_of_channels=mod6_DIOL.get_number_of_channels()))
    DIOL_3 = (mod7_DIOL.read_data_counts(0, number_of_channels=mod7_DIOL.get_number_of_channels()))
    DIOL_4 = (mod8_DIOL.read_data_counts(0, number_of_channels=mod8_DIOL.get_number_of_channels()))
    Temp_water = (mod2_TTC.read_data(0, number_of_channels=mod2_TTC.get_number_of_channels()))
    AI = (mod1_AI.read_data(0, number_of_channels=mod1_AI.get_number_of_channels()))

    ser = serial.Serial(
        port='/dev/ttyS0',  # Replace ttyS0 with ttyAM0 for Pi1,Pi2,Pi0
        baudrate=9600,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        bytesize=serial.EIGHTBITS,
        timeout=1
    )
    print(mod1_AI)
    print("mod1_AI type: " + str(type(mod1_AI)))
    print(mod2_TTC)
    print("mod2_TTC type: " + str(type(mod2_TTC)))
    print(mod4_DIV20)
    print("mod4_DIV20 type: " + str(type(mod4_DIV20)))
    print(mod5_DIOL)
    print("mod5_DIOL type: " + str(type(mod5_DIOL)))
    print(mod3_AO)
    print("mod3_AO type: " + str(type(mod3_AO)))
    print("")
if demo == 1:
    mod1_AI = [float(0)] * 8  # Analog input module
    mod2_TTC = [float(0)] * 8  # Thermocouple input module.
    mod4_DIV20 = [float(0)] * 20  # 20 digital discrete inputs
    mod5_DIOL = [float(0)] * 10  # 5 Digital discrete inputs, 5 Digital outputs
    mod6_DIOL = [float(0)] * 10  # 5 Digital discrete inputs, 5 Digital outputs
    mod7_DIOL = [float(0)] * 10  # 5 Digital discrete inputs, 5 Digital outputs
    mod8_DIOL = [float(0)] * 10  # 5 Digital discrete inputs, 5 Digital outputs
    mod3_AO = [float(0)] * 10

    # Read input values from Modules
    DIOL_1 = [float(0)] * 10
    DIOL_2 = [float(0)] * 10
    DIOL_3 = [float(0)] * 10
    DIOL_4 = [float(0)] * 10
    Temp_water = [float(0)] * 8
    AI = [float(0)] * 8
    flowrate = [float(0)] * 8


def animate(i):  # function for animating the Plot.... Not working so far (10/08/2020)
    global ylist
    # df_csv = pd.read_csv(filename, header=0)
    # xlist.append(n+1) = list(range(1, plot_length + 1))
    # x_ticks = df_csv[str(xvals)].tolist()

    ylist.append(Temp_water[4])

    if len(ylist) > plot_length:
        ylist = ylist[-plot_length:]
    xlist = list(range(0, len(ylist)))
    print("is working")

    a.clear()

    # a.xticks(x_ticks, xlist)
    a.plot(xlist, ylist)


def read_serial():
    global frequency, flowrate_value, prev_count, prev_time
    current_time = time.time()
    sample_time = current_time - prev_time

    # while 1:  # not needed  if function is in while loop
    readchar = ser.readline().decode().rstrip("\n")  # Read Serial, decode, take off '\n' character at end of input
    # print("Decoded Input: " + readchar)
    split_char = readchar.split(',')  # split sting into list by commas
    fixed_str = [i.strip('"\x00#') for i in split_char]  # take off "\x00#" from anywhere in list
    #try:  # to prevent " ValueError: invalid literal for int() with base 10: ''"
    current_count = list(map(int, fixed_str))  # change string to integers for purpose of use in calculations
    # print (current_count)
    for n in range(0, 8):
        frequency[n] = (current_count[n] - prev_count[n]) * 60 / sample_time  # pulse per minute
        flowrate_value[n] = frequency[n] / ppg[n]  # Flowrate in Gallons/min
        print("Pump number " + str(n) + "\nFrequency is: " + str(frequency[n]) + " Pulses Per Minute!\nFlowrate is: " + str(flowrate_value[n]) + " GPM")

    prev_count = current_count
    prev_time = current_time

    #return flowrate_value
    #except:
    #    None
    print(fixed_str)
    # print( fixed_str[1], type(fixed_str[1]))
    # print(current_count, type(current_count))
    # print(fixed_int[1],type(fixed_int[1]))


# update functions to be used for demo or non-demo


def update_maq20():  # include function if connected to MAQ20
    global DIOL_1, DIOL_2, DIOL_3, DIOL_4, T, AI
    DIOL_1 = (mod5_DIOL.read_data(0, number_of_channels=mod5_DIOL.get_number_of_channels()))
    DIOL_2 = (mod6_DIOL.read_data(0, number_of_channels=mod6_DIOL.get_number_of_channels()))
    DIOL_3 = (mod7_DIOL.read_data_counts(0, number_of_channels=mod7_DIOL.get_number_of_channels()))
    DIOL_4 = (mod8_DIOL.read_data_counts(0, number_of_channels=mod8_DIOL.get_number_of_channels()))
    Temp_water = (mod2_TTC.read_data(0, number_of_channels=mod2_TTC.get_number_of_channels()))
    AI = (mod1_AI.read_data(0, number_of_channels=mod1_AI.get_number_of_channels()))
    read_serial()


def update_unhooked():  # update data with random integers to check functionality
    global DIOL_1, DIOL_2, DIOL_3, DIOL_4, T, AI
    for i in range(0, 5):
        DIOL_1[i] = random.randint(0, 1)
        DIOL_2[i] = random.randint(0, 1)
        DIOL_3[i] = random.randint(0, 1)
        DIOL_4[i] = random.randint(0, 1)
    for i in range(0, 8):
        Temp_water[i] = random.uniform(10, 65)
        AI[i] = random.uniform(0.5, .6)
        flowrate_value[i] = random.uniform(4.5, 5)


# RAW Values for IO to/from maq20
pump_io = [0] * 8  # pump request before deadhead protection   # output digital: p1 is 0 in list
pump_io_maq20 = [0] * 8  # Pump signal sent to maq20 after deadhead protection
pump_error = [0] * 8
flow_valve_pos = [0] * 8  # output analog
flow_pulse = [0] * 8  # input From Serial Port
# SHED_req_to_start = [False]*3   # 0: SHED1, 1:SHED2, 2:SHED3 |  | digital input: 0 for no request, 1 for request
# SHED_good_to_start = [False]*3  # 0: SHED2, 1: SHED2 |  | digital output: 0 for not ready, 1 for ready
door_seal = [0] * 2  # 0: SHED2, 1: SHED2 |  | digital output: 0 for open, 1 for seal
exhaustfan_request = 1  # Main Fan |  | digital output: 0 for no request, 1 for request
exhaustfan_feedback = 1  # Main Fan feedback |  | digital input: 0 for off, 1 for on
exhaust_damper = 1  # Main Fan Bypass |  | digital output: 0 for closed, 1 for open (closed for alarms)
SHED_exhaust_valve = [0] * 2  # 0:SHED2, 1:SHED3 |  | digital output: 0 for closed, 1 for open

# calculated values:
flowrate_value = [0.0] * 8  # Flowrate calculated from read_serial Function
SHED_temp_actual = [0.0] * 2  # 0: SHED2, 1: SHED3
SHED_pid = [0] * 8  # 0: SHED2, 1: SHED3 calculated pid value
SHED_T_in = [0] * 4


flowrate_text_tab1 = [''] * 8
pump_text_tab1 = [''] * 8
flow_temp_text_tab1 = [''] * 8
valve_text_tab1 = [''] * 8
flow_valve_text_tab1 = [''] * 8

flowrate_text_tabx = [''] * 8
pump_text_tabx = [''] * 8
flow_temp_text_tabx = [''] * 8
valve_text_tabx = [''] * 8
flow_valve_text_tabx = [''] * 8


def INPUT_maq20():
    # input
    global SHED_T_in, gas_analyzer_SHED2, gas_analyzer_SHED3, SHED1_start_request_IN, SHED2_start_request_IN, SHED3_start_request_IN, exhaustfan_feedback
    SHED_T_in = AI[0:3]

    gas_analyzer_SHED2 = AI[4]
    gas_analyzer_SHED3 = AI[5]
    SHED1_start_request_IN = DIOL_3[5]
    SHED2_start_request_IN = DIOL_3[6]
    SHED3_start_request_IN = DIOL_3[7]
    exhaustfan_feedback = DIOL_4[5]

def OUTPUT_maq20():
    # output
    mod5_DIOL[0] = pump_io[0]  # SHED3 Hot
    mod5_DIOL[1] = pump_io[1]  # SHED3 Cool
    mod5_DIOL[2] = pump_io[2]  # SHED2 Hot
    mod5_DIOL[3] = pump_io[3]  # SHED2 Cool
    mod5_DIOL[4] = pump_io[4]  # MAIN Hot
    mod6_DIOL[0] = pump_io[5]  # MAIN Cool
    mod6_DIOL[1] = pump_io[6]  # SHED1 Cool
    mod6_DIOL[2] = pump_io[7]  # SHED1 Hot
    mod6_DIOL[3] = door_seal[0]  # Door Seal SHED2
    mod6_DIOL[4] = SHED_exhaust_valve[0]  # Exhaust Valve SHED2
    good_to_start = [0] * 3
    for i in range(0, 3):
        if SHED_ready[i] == 2:
            good_to_start[i] = 1
        else:
            good_to_start[i] = 0
    mod7_DIOL[0] = good_to_start[0]  # Ready Signal output for SHED1
    mod7_DIOL[1] = good_to_start[1]  # Ready Signal output for SHED2
    mod7_DIOL[2] = good_to_start[2]  # Ready Signal output for SHED3
    mod7_DIOL[3] = door_seal[1]  # Door Seal SHED3
    mod7_DIOL[4] = SHED_exhaust_valve[1]  # Exhaust Valve SHED3
    mod8_DIOL[0] = exhaust_damper  # Exhaust Damper - Located on top of SHED 3. Closed when exhaust is needed.
    mod8_DIOL[1] = exhaustfan_request  # Exhaust Fan signal OUT
    mod8_DIOL[2] = 0
    mod8_DIOL[3] = 0
    mod8_DIOL[4] = 0
    mod3_AO[0] = flow_valve_pos[0]
    mod3_AO[1] = flow_valve_pos[1]
    mod3_AO[2] = flow_valve_pos[2]
    mod3_AO[3] = flow_valve_pos[3]
    mod3_AO[4] = flow_valve_pos[4]
    mod3_AO[5] = flow_valve_pos[5]
    mod3_AO[6] = flow_valve_pos[6]
    mod3_AO[7] = flow_valve_pos[7]


def calculated_values_update():
    global SHED_temp_actual, smooth_t2, smooth_t3
    if smooth_t2 == len(T_shed2):
        smooth_t2 = 0
    if smooth_t3 == len(T_shed3):
        smooth_t3 = 0

    # AI = (mod1_AI.read_data(0, number_of_channels=mod1_AI.get_number_of_channels()))
    # read data from 0-3 for analog input 1-4

    sum2 = ((AI[0]) * cal1 + (AI[1]) * cal2) / 2  # Calibration in Config file
    sum3 = ((AI[2]) * cal3 + (AI[3]) * cal4) / 2  # Calibration in config file

    if 100 > sum2 > 5:  # To filter outliers
        T_shed2[smooth_t2] = sum2
        smooth_t2 = smooth_t2 + 1

    if 100 > sum3 > 5:  # To filter outliers

        T_shed3[smooth_t3] = sum3
        smooth_t3 = smooth_t3 + 1
    else:
        None

    ave_T_shed2 = round(sum(T_shed2) / float(len(T_shed2)), 1)
    ave_T_shed3 = round(sum(T_shed3) / float(len(T_shed3)), 1)

    SHED_temp_actual = [ave_T_shed2, ave_T_shed3]
    print(sum2)
    print(sum3)
    print(SHED_temp_actual)


def valve_pid1():  # PID for SHED2
    global pid_vout
    if SHED2:
        pid1.setpoint = set_temp[0]
        pid_vout[0] = pid1(SHED_temp_actual[0])
        print("current temp SHED2: " + str(SHED_temp_actual[0]))
        print("set point SHED2: " + str(set_temp[0]))
        print("valve % SHED2: " + str(pid_vout[0] * 10))
        # sleep(1)
    else:
        pid_vout[0] = 0  # set valves closed by default


def valve_pid2():  # PID for SHED3
    global pid_vout
    if SHED3:
        pid2.setpoint = set_temp[1]
        pid_vout[1] = pid2(SHED_temp_actual[1])
        print("current temp SHED3: " + str(SHED_temp_actual[1]) + " deg C")
        print("set point SHED3: " + str(set_temp[1]) + " deg C")
        print("valve % SHED3: " + str(pid_vout[1] * 10))
        # sleep(1)
    else:
        pid_vout[1] = 0  # set valves closed by default]


def flow_check():  # Checks Flowrate for Back Flow, Also Checks Exhaust Flow
    global flow_status, temp_status, SHED_good_to_start, flowrate_status, SHED_temp_status, SHED_ready
    # ---------- Flow / Temperature Status --------- #
    # temperature Status
    if demo == 0:
        for i in range(0, len(temp_lower_bound)):
            if temp_lower_bound[i] < Temp_water[i] < temp_higher_bound[i]:
                temp_status[i] = True
            else:
                temp_status[i] = False
            if flow_lower_bound[i] < flowrate_value[i] < flow_higher_bound[i]:
                flowrate_status[i] = True
            else:
                flowrate_status[i] = False
        for i in range(0, 2):
            if (set_temp[i] + SHED_lower_bound[i]) < SHED_temp_actual[i] < (set_temp[i] + SHED_upper_bound[i]):
                SHED_temp_status[i] = True
            else:
                SHED_temp_status[i] = False

    if demo == 1:
        for i in range(0, 8):  # Change for test cases
            flowrate_status[i] = True
            temp_status[i] = True
        for i in range(0, 2):
            SHED_temp_status[i] = True
    # SHED 1 Flow Status
    if exhaustfan_request == 1:
        if SHED1 is True:
            if flowrate_value[5] >= flowrate_value[6]:
                flow_status[0] = 1  # Flow Rate Normal
            else:
                flow_status[0] = 2  # Back Flow in Cold Loop

            if (temp_status[5] is True) and (temp_status[6] is True) and (flowrate_status[5] is True) and (
                    flowrate_status[6] is True) and (flow_status[0] == 1):
                SHED_ready[0] = 2  # SHED 1 is ready
            else:
                SHED_ready[0] = 1  # SHED1 is requested, but not ready

        else:  # if SHED1 is False:
            flow_status[0] = 0  # SHED off - No Check needed
            SHED_ready[0] = 0  # to reset

        # SHED 2 Flow Status

        if SHED2 is True:
            if (flowrate_value[5] >= flowrate_value[3]) and flowrate_value[4] >= flowrate_value[2]:
                flow_status[0] = 1  # Flow Rate Normal
            else:
                if flowrate_value[5] < flowrate_value[3]:
                    flow_status[1] = 2  # Back Flow in cold loop
                elif flowrate_value[4] < flowrate_value[2]:
                    flow_status[1] = 3  # Back Flow in Hot loop
                else:
                    flow_status[1] = 4  # unknown Error

            if (temp_status[5] is True) and (temp_status[3] is True) and (temp_status[4] is True) and (
                    temp_status[2] is True) \
                    and (flowrate_status[5] is True) and (flowrate_status[3] is True) and (
                    flowrate_status[4] is True) and (flowrate_status[2] is True) and (flow_status[1] == 1) and \
                    SHED_temp_status[0] is True:
                SHED_ready[1] = 2  # SHED 2 is ready
            else:
                SHED_ready[1] = 1  # SHED2 is requested, but not ready

        else:  # if SHED2 is False:
            flow_status[1] = 0  # SHED off - No Check needed
            SHED_ready[1] = 0  # to reset

        # SHED3 Flow Status
        if SHED3 is True:
            if flowrate_value[4] >= flowrate_value[0]:
                flow_status[2] = 1  # Flow Rate Normal
            else:
                flow_status[2] = 2  # Back Flow in Cold Loop

            if (temp_status[4] is True) and (temp_status[0] is True) and (flowrate_status[4] is True) and (
                    flowrate_status[0] is True) and (flow_status[2] == 1) and SHED_temp_status[1] is True:
                SHED_ready[2] = 2  # SHED 1 is ready
                # print(SHED_temp_actual,SHED_temp_status)
            else:
                SHED_ready[2] = 1  # SHED1 is requested, but not ready

        else:  # if SHED3 is False:
            flow_status[2] = 0  # SHED off - No Check needed
            SHED_ready[2] = 0  # to reset


deadhead_switch = [0] * 8


def deadhead_protection_function():  # SHOULD BE RUN EVERY 5 seconds to avoid burning pump out
    global pump_io, deadhead_switch
    deadhead_protection = sheet.cell_value(22, 1)

    for i in range(0, 2):
        if flow_valve_pos[i] < deadhead_protection:
            if pump_io[i] == 1:
                deadhead_switch[i] = 1
                pump_io[i] = 0
            else:
                pass
        else:
            if pump_io[i] == 0 and deadhead_switch[i] == 1:
                pump_io[i] = 1
                deadhead_switch[i] = 0
        if flow_valve_pos[i + 2] < deadhead_protection:
            if pump_io[i + 2] == 1:
                deadhead_switch[i + 2] = 1
                pump_io[i + 2] = 0
            else:
                pass
        else:
            if pump_io[i + 2] == 0 and deadhead_switch[i + 2] == 1:
                pump_io[i + 2] = 1
                deadhead_switch[i + 2] = 0
        # SKIP pump 5 and 6 because main pumps!
        if flow_valve_pos[i + 6] < deadhead_protection:
            if pump_io[i + 6] == 1:
                deadhead_switch[i + 6] = 1
                pump_io[i + 6] = 0
            else:
                pass
        else:
            if pump_io[i + 6] == 0 and deadhead_switch[i + 6] == 1:
                pump_io[i + 6] = 1
                deadhead_switch[i + 6] = 0
    if flow_valve_pos[0] + flow_valve_pos[2] + flow_valve_pos[7] + flow_valve_pos[4] < deadhead_protection:
        if pump_io[4] == 1:
            deadhead_switch[4] = 1
            pump_io[4] = 0
        else:
            pass
    else:
        if pump_io[4] == 0 and deadhead_switch[4] == 1:
            pump_io[4] = 1
            deadhead_switch[4] = 0
    if flow_valve_pos[1] + flow_valve_pos[3] + flow_valve_pos[5] + flow_valve_pos[6] < deadhead_protection:
        if pump_io[5] == 1:
            deadhead_switch[5] = 1
            pump_io[5] = 0
        else:
            pass
    else:
        if pump_io[5] == 0 and deadhead_switch[5] == 1:
            pump_io[5] = 1
            deadhead_switch[5] = 0


SHED1_main_cold, SHED2_main_cold, SHED3_main_cold = 0, 0, 0
SHED1_main_hot, SHED2_main_hot, SHED3_main_hot = 0, 0, 0


def background__():
    global pump_io, SHED_exhaust_valve, exhaust_damper, exhaustfan_request

    if demo == 1:
        update_unhooked()
    if demo == 0:
        update_maq20()

    flow_check()

    if pid1_io == 1:
        valve_pid1()
    if pid2_io == 1:
        valve_pid2()
    calculated_values_update()
    AlarmFunction()
    pump_error_background()
    # valve_op_volt = sheet.cell_value(21,1) # Valve operation voltage, can be changed if new valves are put in

    if SHED1:
        manual_mode_individual[5] = 0
        manual_mode_individual[6] = 0
        pump_io[5] = sheet2.cell_value(7, 1)
        pump_io[6] = sheet2.cell_value(8, 1)
        flow_valve_pos[5] = sheet2.cell_value(15, 1)
        flow_valve_pos[6] = sheet2.cell_value(16, 1)
    else:
        manual_mode_individual[5] = 1
        manual_mode_individual[6] = 1

    if SHED2:
        manual_mode_individual[2] = 0
        manual_mode_individual[3] = 0
        manual_mode_individual[4] = 0
        manual_mode_individual[5] = 0
        pump_io[2] = sheet2.cell_value(4, 4)
        pump_io[3] = sheet2.cell_value(5, 4)
        pump_io[4] = sheet2.cell_value(6, 4)
        pump_io[5] = sheet2.cell_value(7, 4)

        flow_valve_pos[2] = sheet2.cell_value(12, 4)
        flow_valve_pos[3] = sheet2.cell_value(13, 4)
        flow_valve_pos[4] = sheet2.cell_value(14, 4)
        flow_valve_pos[5] = sheet2.cell_value(15, 4)
    else:
        manual_mode_individual[2] = 1
        manual_mode_individual[3] = 1
        manual_mode_individual[4] = 1
        manual_mode_individual[5] = 1
    if SHED3:
        manual_mode_individual[0] = 0
        manual_mode_individual[4] = 0
        pump_io[0] = sheet2.cell_value(2, 7)
        pump_io[4] = sheet2.cell_value(6, 7)
        flow_valve_pos[0] = pid_vout[1]
        flow_valve_pos[4] = sheet2.cell_value(14, 7)
    else:
        manual_mode_individual[0] = 1
        manual_mode_individual[4] = 1

    """ bypassauto allows for the main bypass to be automatically be activated if the all other valves are closed."""

    def bypass_auto():
        global flow_valve_pos
        hot_valves_total = flow_valve_pos[0] + flow_valve_pos[2] + flow_valve_pos[7]
        if hot_valves_total > 10:
            hot_valves_total = 10
        cold_valves_total = flow_valve_pos[1] + flow_valve_pos[3] + flow_valve_pos[6]
        if cold_valves_total > 10:
            cold_valves_total = 10
        flow_valve_pos[4] = 10 - hot_valves_total  # sets bypass valve according to position of other valves
        flow_valve_pos[5] = 10 - cold_valves_total
    if manual_mode_all == 0:
        bypass_auto() #
    deadhead_protection_function()


def flow_calculate(flow_text, n):
    def flow_update():
        txt = ''
        # for n in range(0,8):
        flow_text[n].configure(text="Flowrate \n" + str(round(flowrate_value[n], 2)) + " GPM")
        # print(flowrate[n])
        flow_text[n].after(ref_rate, flow_update)

    flow_update()


def pump_error_background():
    global pump_error
    for i in range(0, 8):
        if pump_io[i] == 1 and flowrate_value[i] < flow_lower_bound[i] and flow_valve_pos[i] > deadhead_protection:
            pump_error[i] = 1
        else:
            pump_error[i] = 0

"""
Pump Status is updated to include the status of the pump (on/off) and if there is an error which will flash.
"""
def pump_status(pump_text, i):
    def pump_text_update():
        x = 0
        txt = ""

        if pump_io[i] == 0:
            txt = "Pump" + str(i + 1) + "\nOFF"
            pump_text[i].configure(text=txt, bg="black", fg="white")  # Pump text 1 for ON 0 for Off

        elif pump_io[i] == 1:
            txt = "Pump" + str(i + 1) + "\nON"
            if pump_error[i] == 0:
                pump_text[i].configure(text=txt, bg="green", fg="black")  # Pump text 1 for ON 0 for Off

            if pump_error[i] == 1:
                bgflash = ("black", "red")
                pump_text[i].configure(bg=bgflash[flash_index])
        else:
            txt = "error"
        pump_text[i].configure(text=txt)  # Pump text 1 for ON 0 for Off
        pump_text[i].after(ref_rate, pump_text_update)

    pump_text_update()


def flow_temp_status(temp_text, n):
    def temp_text_update():
        txt = ""
        txt = "Temp." + str(n + 1) + "\n" + str(round(Temp_water[n], 2)) + u'\N{DEGREE SIGN}' + "C"
        temp_text[n].configure(text=txt, bg="black", fg="white")  # Pump text 1 for ON 0 for Off
        temp_text[n].after(ref_rate, temp_text_update)

    temp_text_update()


def valve_position(valve_text, n):
    def valve_text_update():
        txt = ""
        txt = "Valve Pos." + str(n + 1) + "\n" + str(round(100 * flow_valve_pos[n] / 10, 2)) + "%"
        valve_text[n].configure(text=txt)
        valve_text[n].after(ref_rate, valve_text_update)

    valve_text_update()


def FlowMonitor(app_window, item1, item2):
    """
    Flow Monitor is used to display all of the flow information including the pump status, flowrate, temperature,
    and valve position.
    -app window is the frame which it will be placed in
    -item1 and item2 are the variables to select the position in the pump, valve, flowmeter lists. item1 is for hot, item2 is for cold
    """
    hotLabel0 = Label(app_window, text="Hot", font=("Bold", 10), padx=9)
    coldLabel0 = Label(app_window, text="Cold", font=("Bold", 10), padx=9)
    hotLabel0.grid(row=2, column=0)
    coldLabel0.grid(row=3, column=0)
    flowrate_text_tab1[item1] = Label(app_window, padx=10, width=flow_width)
    flowrate_text_tab1[item2] = Label(app_window, padx=10, width=flow_width)
    flowrate_text_tab1[item1].grid(row=2, column=2)
    flowrate_text_tab1[item2].grid(row=3, column=2)
    pump_text_tab1[item1] = Label(app_window, padx=10, width=pump_width)
    pump_text_tab1[item2] = Label(app_window, padx=10, width=pump_width)
    pump_text_tab1[item1].grid(row=2, column=1)
    pump_text_tab1[item2].grid(row=3, column=1)
    flow_temp_text_tab1[item1] = Label(app_window, padx=10, width=flow_temp_width)
    flow_temp_text_tab1[item2] = Label(app_window, padx=10, width=flow_temp_width)
    flow_temp_text_tab1[item1].grid(row=2, column=3)
    flow_temp_text_tab1[item2].grid(row=3, column=3)
    flow_valve_text_tab1[item1] = Label(app_window, padx=10, width=valve_width)
    flow_valve_text_tab1[item2] = Label(app_window, padx=10, width=valve_width)
    flow_valve_text_tab1[item1].grid(row=2, column=4)
    flow_valve_text_tab1[item2].grid(row=3, column=4)

    lower = min(item1, item2)
    larger = max(item1, item2)
    for n in range(lower, larger + 1):
        pump_status(pump_text_tab1, n)
        flow_calculate(flowrate_text_tab1, n)
        flow_temp_status(flow_temp_text_tab1, n)
        valve_position(flow_valve_text_tab1, n)


def FlowMonitor_tabx(app_window, item1, item2):
    """
    the "tabx" flow meter is a variation of
    :param app_window:
    :param item1:
    :param item2:
    :return:
    """
    hotLabel0 = Label(app_window, text="Hot", font=("Bold", 10), padx=9)
    coldLabel0 = Label(app_window, text="Cold", font=("Bold", 10), padx=9)
    hotLabel0.grid(row=2, column=0)
    coldLabel0.grid(row=3, column=0)
    flowrate_text_tabx[item1] = Label(app_window, padx=10, width=flow_width)
    flowrate_text_tabx[item2] = Label(app_window, padx=10, width=flow_width)
    flowrate_text_tabx[item1].grid(row=2, column=2)
    flowrate_text_tabx[item2].grid(row=3, column=2)
    pump_text_tabx[item1] = Label(app_window, padx=10, width=pump_width)
    pump_text_tabx[item2] = Label(app_window, padx=10, width=pump_width)
    pump_text_tabx[item1].grid(row=2, column=1)
    pump_text_tabx[item2].grid(row=3, column=1)
    flow_temp_text_tabx[item1] = Label(app_window, padx=10, width=flow_temp_width)
    flow_temp_text_tabx[item2] = Label(app_window, padx=10, width=flow_temp_width)
    flow_temp_text_tabx[item1].grid(row=2, column=3)
    flow_temp_text_tabx[item2].grid(row=3, column=3)
    flow_valve_text_tabx[item1] = Label(app_window, padx=10, width=valve_width)
    flow_valve_text_tabx[item2] = Label(app_window, padx=10, width=valve_width)
    flow_valve_text_tabx[item1].grid(row=2, column=4)
    flow_valve_text_tabx[item2].grid(row=3, column=4)

    lowerx = min(item1, item2)
    largerx = max(item1, item2)
    for n in range(lowerx, largerx + 1):
        pump_status(pump_text_tabx, n)
        flow_calculate(flowrate_text_tabx, n)
        flow_temp_status(flow_temp_text_tabx, n)
        valve_position(flow_valve_text_tabx, n)


def exhaustfan_alarm_update(exhaust):
    def update():
        if exhaustfan_feedback == 1:
            exhaust.configure(text="Exhaust: OK!", bg='lime green', fg='black')
        if exhaustfan_feedback == 0:
            fgflash = ("black", "red")
            exhaust.configure(text="NO EXHAUST!", fg=fgflash[flash_index], bg=fgflash[1 - flash_index])
        exhaust.after(ref_rate, update)

    update()


def AlarmMonitor(app_window):
    exhaustfan_alarm_status = Button(app_window, text='',command = alarm_reset_exhaust)
    exhaustfan_alarm_status.grid(row=1, column=6, padx=1)
    SHEDalarm_label_status = [Button(app_window, text=''), Button(app_window, text=''), Button(app_window, text='')]
    SHEDalarm_label_status[0].configure(command=lambda: alarm_reset(1))
    SHEDalarm_label_status[1].configure(command=lambda: alarm_reset(2))
    SHEDalarm_label_status[2].configure(command=lambda: alarm_reset(3))

    for i in range(0, 3):
        SHEDalarm_label_status[i].grid(row=1, column=2 * i + 1, padx=1)


    def SHEDalarm_label1_update(label):
        def update():
            for i in range(0, 3):
                if alarm_status[i] == 0:

                    label[i].configure(text="SHED" + str(i + 1) + ": OK!", bg='lime green', fg='black')
                elif alarm_status[i] == 1:
                    label[i].configure(text="SHED" + str(i + 1) + ": ACTIVE", bg='black', fg='red')
                elif alarm_status[i] == 2:
                    fgflash = ("black", "red")
                    bgflash = ("red", "black")
                    label[i].configure(text="SHED" + str(i + 1) + ": Reset", fg=fgflash[1 - flash_index],
                                       bg=bgflash[1 - flash_index])
                else:
                    label[i].configure(text='CODE ERROR')

            label[0].after(ref_rate, update)

        update()

    SHEDalarm_label1_update(SHEDalarm_label_status)

    exhaustfan_alarm_update(exhaustfan_alarm_status)


def Alarm_acknowledge(SHEDn):
    global alarm_status
    MsgBox = tk.messagebox.askquestion("SHED" + str(SHEDn) + " LEL Alarm", "Do you want to reset the alarm?",
                                       icon='error')
    if MsgBox == 'yes':
        alarm_status[SHEDn - 1] = 0
    else:
        tk.messagebox.showinfo('Return', "LEL alarm is still active and can be reset from the 'Main Screen'")
        alarm_status[SHEDn - 1] = 2


def Alarm_acknowledge_exhaust():
    global alarm_status_exhaust
    MsgBox = tk.messagebox.askquestion("No Exhaust Flow Alarm", "Do you want to reset the alarm?",
                                       icon='error')
    if MsgBox == 'yes':
        alarm_status_exhaust = 0
    else:
        tk.messagebox.showinfo('Return', "Exhaust alarm is still active and can be reset from the 'Main Screen'")
        alarm_status_exhaust = 2


def Alarm_prompt():
    global alarm_status, alarm_status_exhaust

    if alarm_active[0] == 1:
        if alarm_status[0] == 1:
            messagebox.showerror("Warning", "Please acknowledge Alarm for SHED1", command=alarm_reset(1))
        if alarm_status[0] == 0:
            pass
        else:
            pass
    else:
        pass

    if alarm_active[1] == 1:
        if alarm_status[1] == 2:  # Alarm has been acknowledged, waiting to be reset from MAIN SCREEN
            pass
        else:
            if alarm_status[1] == 1:
                Alarm_acknowledge(2)
                # messagebox.showerror("Warning", "Please acknowledge Alarm for SHED2", command=alarm_reset(2))
            else:
                if gas_analyzer_lower_SHED2 < gas_analyzer_SHED2 < gas_analyzer_upper_SHED2:
                    alarm_status[1] = 0
                else:
                    alarm_status[1] = 1
                    Alarm_acknowledge(2)
                    # messagebox.showerror("Warning", "Please acknowledge Alarm for SHED2", command=alarm_reset(2))

    if alarm_active[2] == 1:
        if alarm_status[2] == 2:
            pass
        else:
            if alarm_status[2] == 1:
                Alarm_acknowledge(3)
            else:
                if gas_analyzer_lower_SHED3 < gas_analyzer_SHED3 < gas_analyzer_upper_SHED3:
                    alarm_status[2] = 0
                else:
                    alarm_status[2] = 1
                    Alarm_acknowledge(3)

    if alarm_active_exhaust == 1:
        if alarm_status_exhaust == 2:
            pass
        else:
            if exhaustfan_feedback == 1:
                alarm_status_exhaust = 0
            else:
                alarm_status_exhaust = 1
                Alarm_acknowledge_exhaust()
    else:
        alarm_status_exhaust = 0

"""
-Alarm Function is depentend on the Alarm prompt. Alarm prompt controls the alarm status either by automatic
control or manual control when prompted. This has to run separately so the AlarmFunction can run in the background
wile the alarm prompt is open

-If alarm_status is more than ZERO the alarm is to be active and the SHEDs are deemed to be UNSAFE to operate.

-If there is ZERO exhaust flow, NO SHED is safe to operate.
"""
def AlarmFunction():
    global SHED1, SHED2, SHED3, exhaustfan_request, exhaust_damper, SHED_exhaust_valve
    # NORMAL OPERATION
    if alarm_status[0] + alarm_status[1] + alarm_status[2] == 0:
        exhaustfan_request = 1
        exhaust_damper = 1
        SHED_exhaust_valve = [0, 0]
    else:
        exhaustfan_request = 1
        exhaust_damper = 0  # Close exhaust damper to allow for full vacuum

        # SHED 1 ALARM
        if alarm_status[0] > 0:
            SHED1 = False  # set SHED 1 to off
            SHED_ready[0] = 0
            # flow_valve_pos[6] = 0        # close valve for cold water flow into External chiller.
        else:
            pass
        # SHED2 ALARM
        if alarm_status[1] > 0:
            SHED_exhaust_valve[0] = 1  # Open Exhaust valve at rear of SHED2
            SHED2 = False
            SHED_ready[1] = 0
        else:
            SHED_exhaust_valve[0] = 0
        # SHED3 ALARM
        if alarm_status[2] > 0:
            SHED_exhaust_valve[1] = 1
            SHED3 = False
            SHED_ready[2] = 0
        else:
            SHED_exhaust_valve[1] = 0
        #Exhaust Alarm:
        if alarm_status_exhaust>0:
            SHED1=False
            SHED2=False
            SHED3=False
            SHED_ready=[0,0,0]



def damper_label1_update(exhaust_damper_label):
    def update():
        if exhaust_damper == 0:
            exhaust_damper_label.configure(text="CLOSED")
        else:
            exhaust_damper_label.configure(text="OPEN")
        exhaust_damper_label.after(ref_rate, update)

    update()


def ExhaustMonitor(app_window):
    damper_label1 = Label(app_window, text="Damper Position: ", font=("Bold", 10), justify=RIGHT)
    damper_label1.grid(row=0, column=0, sticky=E)
    damper_position_label1 = Label(app_window, text="test")
    damper_position_label1.grid(row=0, column=1)

    damper_label1_update(damper_position_label1)
    exhaustfan_label1 = Label(app_window, text="Exhaust fan: ", font=("Bold", 10))
    exhaustfan_label1.grid(row=1, column=0, sticky=E)
    exhaustfan_io_label1 = Label(app_window, text="test")
    exhaustfan_io_label1.grid(row=1, column=1)
    exhaustfan_feedback_label1 = Label(app_window, text="test2")
    exhaustfan_feedback_label1.grid(row=1, column=2)

    def extractor_status_update(extractor_fan_label, extractor_status_label):
        def update():
            if exhaustfan_request == 1:
                extractor_fan_label.configure(text="ON", fg='black')
                if exhaustfan_feedback == 0:
                    fgflash = ("black", "red")
                    extractor_status_label.configure(text="Zero Flow", fg=fgflash[flash_index])
                elif exhaustfan_feedback == 1:
                    extractor_status_label.configure(text="Confirmed")
                    extractor_status_label.configure(fg="black")
                else:
                    pass
            elif exhaustfan_request == 0:
                extractor_fan_label.configure(text="OFF", fg='black')
                if exhaustfan_feedback == 0:
                    extractor_status_label.configure(text="Zero Flow", fg="black")
                elif exhaustfan_feedback == 1:
                    extractor_status_label.configure(text="Confirmed")
                    extractor_status_label.configure(fg="black")

            extractor_fan_label.after(ref_rate, update)

        update()

    extractor_status_update(exhaustfan_io_label1, exhaustfan_feedback_label1)
    SHED2_label1 = Label(app_window, text="SHED2 Exhaust: ", font=("Bold", 10), justify=RIGHT, padx=10)
    SHED2_label1.grid(row=0, column=3, sticky=E)
    SHED2_valve_position_label1 = Label(app_window, text="test")
    SHED2_valve_position_label1.grid(row=0, column=4)
    SHED3_label1 = Label(app_window, text="SHED3 Exhaust: ", font=("Bold", 10), justify=RIGHT, padx=10)
    SHED3_label1.grid(row=1, column=3, sticky=E)
    SHED3_valve_position_label1 = Label(app_window, text="test")
    SHED3_valve_position_label1.grid(row=1, column=4)

    def SHED_valvetext_update(valve_label2, valve_label3):
        def update():
            if SHED_exhaust_valve[0] == 1:
                valve_label2.configure(text="OPEN")
            elif SHED_exhaust_valve[0] == 0:
                valve_label2.configure(text="CLOSED")
            else:
                valve_label2.configure(text='error')
            if SHED_exhaust_valve[1] == 1:
                valve_label3.configure(text="OPEN")
            elif SHED_exhaust_valve[1] == 0:
                valve_label3.configure(text="CLOSED")
            else:
                valve_label3.configure(text='error')

            valve_label3.after(ref_rate, update)

        update()

    SHED_valvetext_update(SHED2_valve_position_label1, SHED3_valve_position_label1)


def alarm_test(SHEDnum):
    global alarm_status
    alarm_status[SHEDnum - 1] = 1


def alarm_reset(SHEDnum):
    global alarm_status
    alarm_status[SHEDnum - 1] = 0
def alarm_reset_exhaust():
    global alarm_status_exhaust
    alarm_status_exhaust = 0


class MainApplication(tk.Tk):

    def __init__(self):
        tk.Tk.__init__(self)  # Was causing extra frame to pop up

        self.root = ttk.Frame()  # create instance of Tk
        self.root.pack()

        self.start_frame = ttk.Frame(self.root)
        self.start_frame.pack(pady=10)
        self.tabControl = ttk.Notebook(self.root)
        self.tab1 = ttk.Frame(self.tabControl)
        self.tab2 = ttk.Frame(self.tabControl)
        self.tab3 = ttk.Frame(self.tabControl)
        self.tab4 = ttk.Frame(self.tabControl)
        self.tabControl.add(self.tab1, text='Main Screen')
        self.tabControl.add(self.tab2, text="Graph Page - Not working")
        self.tabControl.add(self.tab3, text='Manual Control')
        self.tabControl.add(self.tab4, text='Permeation SHEDs')
        self.tabControl.pack(expand=True, fill='both')

        self.frame_tab1 = Tab1(self.tab1, self)
        self.frame_tab1.grid(row=0, column=0, sticky="nsew")

        self.frame_tab2 = Tab2(self.tab2, self)
        self.frame_tab2.grid(row=0, column=0, sticky="nsew")

        self.frame_tab3 = Tab3(self.tab3, self)
        self.frame_tab3.grid(row=0, column=0, sticky="nsew")

        self.frame_tab4 = Permeation_Tab(self.tab4, self)
        self.frame_tab4.grid(row=0, column=0, sticky="nsew")

        self.geometry(str(XX) + "x" + str(YY))
        self.protocol('WM_DELETE_WINDOW', stop_program)
        # self.root.mainloop()


def SHED_auto(self):
    global SHED1, SHED2, SHED3

    ##Circle canvas for display of status lights
    circle_canvas_1 = Canvas(self, width=circle_diam, height=circle_diam)
    circle_canvas_1.grid(column=1, row=1)
    redCircle(circle_canvas_1)
    circle_canvas_2 = Canvas(self, width=circle_diam, height=circle_diam)
    circle_canvas_2.grid(column=3, row=1)
    redCircle(circle_canvas_2)
    circle_canvas_3 = Canvas(self, width=circle_diam, height=circle_diam)
    circle_canvas_3.grid(column=5, row=1)
    redCircle(circle_canvas_3)

    def SHED1_status_indicator():
        if SHED_ready[0] == 0:
            circle_canvas_1.delete("all")
            redCircle(circle_canvas_1)  # clears canvas before replacing old circle with new one.
        elif SHED_ready[0] == 2:
            circle_canvas_1.delete("all")
            greenCircle(circle_canvas_1)
        else:
            circle_canvas_1.delete("all")
            yellowCircle(circle_canvas_1)
        circle_canvas_1.after(10, SHED1_status_indicator)

    SHED1_status_indicator()

    def SHED2_status_indicator():
        if SHED_ready[1] == 0:
            circle_canvas_2.delete("all")
            redCircle(circle_canvas_2)
        elif SHED_ready[1] == 2:
            circle_canvas_2.delete("all")
            greenCircle(circle_canvas_2)
        else:
            circle_canvas_2.delete("all")
            yellowCircle(circle_canvas_2)
        circle_canvas_2.after(10, SHED2_status_indicator)

    SHED2_status_indicator()

    def SHED3_status_indicator():
        if SHED_ready[2] == 0:
            circle_canvas_3.delete("all")
            redCircle(circle_canvas_3)
        elif SHED_ready[2] == 2:
            circle_canvas_3.delete("all")
            greenCircle(circle_canvas_3)
        else:
            circle_canvas_3.delete("all")
            yellowCircle(circle_canvas_3)
        circle_canvas_3.after(10, SHED3_status_indicator)

    SHED3_status_indicator()

    self.style = ttk.Style()
    bigfont = ('Helvetica', '15')
    self.style.configure('W.TCombobox', font=bigfont, arrowsize=25)

    def get_SHED1(event):
        global SHED1, manual_mode_all, manual_mode_individual, flow_valve_pos, pump_io, exhaustfan_request
        if SHED1_set.get() == "ON":
            SHED1 = True
            print(SHED1)
            manual_mode_individual[5] = 0
            manual_mode_individual[6] = 0
            pump_io[5] = sheet2.cell_value(7, 1)
            pump_io[6] = sheet2.cell_value(8, 1)
            flow_valve_pos[5] = sheet2.cell_value(15, 1)
            flow_valve_pos[6] = sheet2.cell_value(16, 1)
            exhaustfan_request = int(sheet2.cell_value(26, 1))
        else:
            pump_io[6] = sheet2.cell_value(8, 2)
            flow_valve_pos[6] = int(sheet2.cell_value(16, 2))
            manual_mode_individual[6] = 1
            SHED1 = False
            if SHED2 == False:
                manual_mode_individual[5] = 1
                pump_io[5] = sheet2.cell_value(7, 2)
                flow_valve_pos[5] = sheet2.cell_value(15, 2)
                if SHED3 == False:
                    exhaustfan_request = int(sheet2.cell_value(26, 2))

            SHED_ready[0] = 0
        # CHANGE PUMP AND VALVE VALUES ACCORDINGLY

    def get_SHED2(event):
        global SHED2, manual_mode_all, manual_mode_individual, flow_valve_pos, pump_io, exhaustfan_request
        if SHED2_set.get() == "ON":
            SHED2 = True
            print(SHED2)
            manual_mode_individual[2] = 0
            manual_mode_individual[3] = 0
            manual_mode_individual[4] = 0
            manual_mode_individual[5] = 0
            pump_io[2] = int(sheet2.cell_value(4, 4))
            pump_io[3] = int(sheet2.cell_value(5, 4))
            pump_io[4] = int(sheet2.cell_value(6, 4))
            pump_io[5] = int(sheet2.cell_value(7, 4))
            flow_valve_pos[2] = float(sheet2.cell_value(12, 4))
            flow_valve_pos[3] = float(sheet2.cell_value(13, 4))
            flow_valve_pos[4] = float(sheet2.cell_value(14, 4))
            flow_valve_pos[5] = float(sheet2.cell_value(15, 4))
            exhaustfan_request = int(sheet2.cell_value(26, 4))
        else:
            pump_io[2] = sheet2.cell_value(4, 5)
            pump_io[3] = sheet2.cell_value(5, 5)
            flow_valve_pos[2] = float(sheet2.cell_value(12, 5))
            flow_valve_pos[3] = float(sheet2.cell_value(13, 5))

            manual_mode_individual[2] = 1
            manual_mode_individual[3] = 1

            SHED2 = False
            if SHED1 == False:
                manual_mode_individual[5] = 1
                pump_io[5] = sheet2.cell_value(7, 5)
                flow_valve_pos[5] = float(sheet2.cell_value(15, 5))
                if SHED3 == False:
                    exhaustfan_request = int(sheet2.cell_value(26, 5))
            if SHED3 == False:
                manual_mode_individual[4] = 1
                pump_io[4] = sheet2.cell_value(6, 5)
                flow_valve_pos[4] = float(sheet2.cell_value(14, 5))

            SHED_ready[1] = 0

    def get_SHED3(event):
        global SHED3, manual_mode_all, manual_mode_individual, flow_valve_pos, pump_io, exhaustfan_request
        if SHED3_set.get() == "ON":
            SHED3 = True
            print(SHED1)
            manual_mode_individual[0] = 0
            manual_mode_individual[4] = 0
            pump_io[0] = int(sheet2.cell_value(2, 7))
            pump_io[4] = int(sheet2.cell_value(6, 7))
            flow_valve_pos[0] = float(sheet2.cell_value(10, 7))         # Sets starting point for flow_valve_pos, updated with PID control
            flow_valve_pos[4] = float(sheet2.cell_value(14, 7))
            exhaustfan_request = int(sheet2.cell_value(26, 7))
        else:
            pump_io[0] = int(sheet2.cell_value(2, 8))
            flow_valve_pos[0] = float(sheet2.cell_value(10, 8))
            manual_mode_individual[0] = 1
            SHED3 = False
            if SHED2 == False:
                manual_mode_individual[4] = 1
                pump_io[4] = int(sheet2.cell_value(6, 8))
                flow_valve_pos[4] = float(sheet2.cell_value(14, 8))
                if SHED1 == False:
                    exhaustfan_request = int(sheet2.cell_value(26, 8))

            SHED_ready[2] = 0

    SHED1_lbl = Label(self, text="SHED1:", font=bigfont)
    SHED2_lbl = Label(self, text="SHED2:", font=bigfont)
    SHED3_lbl = Label(self, text="SHED3:", font=bigfont)
    SHED1_lbl.grid(column=0, row=0, pady=10)
    SHED2_lbl.grid(column=2, row=0, pady=10)
    SHED3_lbl.grid(column=4, row=0, pady=10)
    SHED1_status_lbl = Label(self, text="Status: ")
    SHED2_status_lbl = Label(self, text="Status: ")
    SHED3_status_lbl = Label(self, text="Status: ")
    SHED1_status_lbl.grid(column=0, row=1)
    SHED2_status_lbl.grid(column=2, row=1)
    SHED3_status_lbl.grid(column=4, row=1)

    SHED1_set = Combobox(self, width=5, justify=CENTER, state="readonly", values=["OFF", "ON"], font=bigfont,
                         style='W.TCombobox')
    SHED2_set = Combobox(self, width=5, justify=CENTER, state="readonly", values=["OFF", "ON"], font=bigfont,
                         style='W.TCombobox')
    SHED3_set = Combobox(self, width=5, justify=CENTER, state="readonly", values=["OFF", "ON"], font=bigfont,
                         style='W.TCombobox')
    SHED1_set.current(0)
    SHED2_set.current(0)
    SHED3_set.current(0)
    SHED1_set.bind("<<ComboboxSelected>>", get_SHED1)
    SHED2_set.bind("<<ComboboxSelected>>", get_SHED2)
    SHED3_set.bind("<<ComboboxSelected>>", get_SHED3)

    SHED1_set.grid(column=1, row=0, padx=10, sticky='E')
    SHED2_set.grid(column=3, row=0, padx=10, sticky='E')
    SHED3_set.grid(column=5, row=0, padx=10, sticky='E')
    self.option_add('*TCombobox*Listbox.font', bigfont)

    print(SHED1_set.get())
    print(SHED1)


def PERM_SHED_control(self, SHEDnum, col_, row_):
    global SHED1, SHED2, SHED3
    # circle_diam = 30 #diameter of symbol on screen in pixels

    circle_canvas_1 = Canvas(self, width=circle_diam, height=circle_diam)
    circle_canvas_1.grid(column=col_, row=row_ + 1)
    redCircle(circle_canvas_1)

    def SHED_status_indicator():
        circle_canvas_1.delete("all")
        if SHED_ready[SHEDnum - 1] == 0:
            redCircle(circle_canvas_1)  # clears canvas before replacing old circle with new one.
        elif SHED_ready[SHEDnum - 1] == 2:
            greenCircle(circle_canvas_1)
        else:
            yellowCircle(circle_canvas_1)
        circle_canvas_1.after(10, SHED_status_indicator)

    SHED_status_indicator()

    self.style = ttk.Style()
    setfont = ('Helvetica', '10')
    self.style.configure('W.TCombobox', font=setfont, arrowsize=15)

    def get_set_temp2(event):
        global set_temp
        set_temp[0] = float(temp_set2.get())

    def get_set_temp3(event):
        global set_temp
        set_temp[1] = float(temp_set3.get())

    def get_SHED1(event):
        global SHED1, manual_mode_all, manual_mode_individual, flow_valve_pos, pump_io, exhaustfan_request
        if SHED_set.get() == "ON":
            SHED1 = True
            print(SHED1)
            manual_mode_individual[5] = 0
            manual_mode_individual[6] = 0
            pump_io[5] = sheet2.cell_value(7, 1)
            pump_io[6] = sheet2.cell_value(8, 1)
            flow_valve_pos[5] = sheet2.cell_value(15, 1)
            flow_valve_pos[6] = sheet2.cell_value(16, 1)
            exhaustfan_request = int(sheet2.cell_value(26, 1))
        else:
            pump_io[6] = sheet2.cell_value(8, 2)
            flow_valve_pos[6] = int(sheet2.cell_value(16, 2))
            manual_mode_individual[6] = 1
            SHED1 = False
            if SHED2 == False:
                manual_mode_individual[5] = 1
                pump_io[5] = sheet2.cell_value(7, 2)
                flow_valve_pos[5] = sheet2.cell_value(15, 2)
                if SHED3 == False:
                    exhaustfan_request = int(sheet2.cell_value(26, 2))

            SHED_ready[0] = 0
        # CHANGE PUMP AND VALVE VALUES ACCORDINGLY

    def get_SHED2(event):
        global SHED2, manual_mode_all, manual_mode_individual, flow_valve_pos, pump_io, exhaustfan_request
        if SHED_set.get() == "ON":
            SHED2 = True
            print(SHED2)
            manual_mode_individual[2] = 0
            manual_mode_individual[3] = 0
            manual_mode_individual[4] = 0
            manual_mode_individual[5] = 0
            pump_io[2] = int(sheet2.cell_value(4, 4))
            pump_io[3] = int(sheet2.cell_value(5, 4))
            pump_io[4] = int(sheet2.cell_value(6, 4))
            pump_io[5] = int(sheet2.cell_value(7, 4))
            flow_valve_pos[2] = float(sheet2.cell_value(12, 4))
            flow_valve_pos[3] = float(sheet2.cell_value(13, 4))
            flow_valve_pos[4] = float(sheet2.cell_value(14, 4))
            flow_valve_pos[5] = float(sheet2.cell_value(15, 4))
            exhaustfan_request = int(sheet2.cell_value(26, 4))
        else:
            pump_io[2] = sheet2.cell_value(4, 5)
            pump_io[3] = sheet2.cell_value(5, 5)
            flow_valve_pos[2] = float(sheet2.cell_value(12, 5))
            flow_valve_pos[3] = float(sheet2.cell_value(13, 5))

            manual_mode_individual[2] = 1
            manual_mode_individual[3] = 1

            SHED2 = False
            if SHED1 == False:
                manual_mode_individual[5] = 1
                pump_io[5] = sheet2.cell_value(7, 5)
                flow_valve_pos[5] = float(sheet2.cell_value(15, 5))
                if SHED3 == False:
                    exhaustfan_request = int(sheet2.cell_value(26, 5))
            if SHED3 == False:
                manual_mode_individual[4] = 1
                pump_io[4] = sheet2.cell_value(6, 5)
                flow_valve_pos[4] = float(sheet2.cell_value(14, 5))

            SHED_ready[1] = 0

    def get_SHED3(event):
        global SHED3, manual_mode_all, manual_mode_individual, flow_valve_pos, pump_io, exhaustfan_request
        if SHED_set.get() == "ON":
            SHED3 = True
            print(SHED1)
            manual_mode_individual[0] = 0
            manual_mode_individual[4] = 0
            pump_io[0] = int(sheet2.cell_value(2, 7))
            pump_io[4] = int(sheet2.cell_value(6, 7))
            flow_valve_pos[0] = float(sheet2.cell_value(10, 7))
            flow_valve_pos[4] = float(sheet2.cell_value(14, 7))
            exhaustfan_request = int(sheet2.cell_value(26, 7))
        else:
            pump_io[0] = int(sheet2.cell_value(2, 8))
            flow_valve_pos[0] = float(sheet2.cell_value(10, 8))
            manual_mode_individual[0] = 1
            SHED3 = False
            if SHED2 == False:
                manual_mode_individual[4] = 1
                pump_io[4] = int(sheet2.cell_value(6, 8))
                flow_valve_pos[4] = float(sheet2.cell_value(14, 8))
                if SHED1 == False:
                    exhaustfan_request = int(sheet2.cell_value(26, 8))

            SHED_ready[2] = 0

    SHED_set = Combobox(self, width=3, justify=CENTER, state="readonly", values=["OFF", "ON"], style='W.TCombobox')
    SHED_set.current(0)

    if SHEDnum == 1:
        SHED_set.bind("<<ComboboxSelected>>", get_SHED1)
    if SHEDnum == 2:
        SHED_set.bind("<<ComboboxSelected>>", get_SHED2)
    if SHEDnum == 3:
        SHED_set.bind("<<ComboboxSelected>>", get_SHED3)

    SHED_set.grid(column=col_, row=row_, padx=10, sticky='E')

    ## SHED SET POINT ###
    if SHEDnum == 2:
        temp_set2 = Combobox(self, width=5, justify=CENTER, state="readonly", values=[23, 43])
        temp_set2.current(1)
        temp_set2.bind("<<ComboboxSelected>>", get_set_temp2)
        temp_set2.grid(column=col_, row=row_ + 2)

    if SHEDnum == 3:
        temp_set3 = Combobox(self, width=5, justify=CENTER, state="readonly",
                             values=[23, 25, 26, 27, 28, 29, 30, 35, 40, 43])
        temp_set3.current(1)
        temp_set3.bind("<<ComboboxSelected>>", get_set_temp3)
        temp_set3.grid(column=col_, row=row_ + 2)
    self.option_add('*TCombobox*Listbox.font', setfont)


def SHED_Status(self):
    # shed_frame = ttk.LabelFrame(self, text="SHED status")
    # shed_frame.grid(column=0, row=1)
    SHED1_lbl = tk.Label(self, text='')
    SHED1_lbl.grid(column=0, row=1)

    def update_SHED_lbl(SHED_lbl):
        def update():
            txt = ['', '', '']
            for i in range(0, 3):
                if SHED_ready[i] == 0:
                    txt[i] = "OFF"
                elif SHED_ready[i] == 1:
                    txt[i] = "Req. Sent"
                elif SHED_ready[i] == 2:
                    txt[i] = "SHED" + str(i) + " Ready"
                else:
                    txt[i] = 'error'
            SHED_lbl.configure(text=txt[0] + '\n' + txt[1] + '\n' + txt[2])
            SHED_lbl.after(10, update)

        update()

    update_SHED_lbl(SHED1_lbl)

def options_manual(app_window):
    global alarm_io, deadhead_io, pid1_io, pid2_io

    deadhead_var = IntVar()
    alarm_var = IntVar()
    pid1_var = IntVar()
    pid2_var = IntVar()

    def deadhead_cb():
        global deadhead_io
        deadhead_io = deadhead_var.get()
        print("Deadhead setting is: " +str(deadhead_var.get()))

    def alarm_cb():
        global alarm_io
        alarm_io = alarm_var.get()
        print("Alarm setting is: " +str(alarm_var.get()))

    def pid1_cb():
        global pid1_io
        pid1_io = int(pid1_var.get())
        print("PID setting for SHED 2 is: "+ str(pid1_io))

    def pid2_cb():
        global pid2_io
        pid2_io = int(pid2_var.get())
        print("PID setting for SHED 3 is: "+ str(pid1_io))

    alarm_button = ttk.Checkbutton(app_window, text='Alarm Override', variable=alarm_var, command=alarm_cb)
    deadhead_button = ttk.Checkbutton(app_window, text='Deadhead Protection', variable=deadhead_var, command=deadhead_cb)
    pid2_button = ttk.Checkbutton(app_window, text='SHED2 PID', variable=pid1_var, command=pid1_cb())
    pid3_button = ttk.Checkbutton(app_window, text='SHED3 PID', variable=pid2_var, command=pid2_cb())
    alarm_button.grid(row=1, column=0)
    deadhead_button.grid(row=2, column=0)
    pid2_button.grid(row=1, column=1)
    pid3_button.grid(row=2, column=1)
    def check_button_refresh():
        if deadhead_io == 1:
            deadhead_button.state(['selected'])
        else:
            deadhead_button.state(['!selected'])
        if alarm_io == 1:
            alarm_button.state(['selected'])
        else:
            alarm_button.state(['!selected'])
        if pid1_io == 1:
            pid2_button.state(['selected'])
        else:
            pid2_button.state(['!selected'])
        if pid2_io == 1:
            pid3_button.state(['selected'])
        else:
            pid3_button.state(['!selected'])
        pid2_button.after(ref_rate,check_button_refresh)
    check_button_refresh()


def pumps_manual(app_window):
    global pump_io

    var1, var2, var3, var4, var5, var6, var7, var8 = IntVar(), IntVar(), IntVar(), IntVar(), IntVar(), IntVar(), IntVar(), IntVar()

    def cb1():
        print("Hello")
        print("variable is" + str(var1.get()))
        pump_io[0] = int(var1.get())

    def cb2():
        print("Hello")
        print("variable is" + str(var2.get()))
        pump_io[1] = int(var2.get())

    def cb3():
        print("Hello")
        print("variable is" + str(var3.get()))
        pump_io[2] = int(var3.get())

    def cb4():
        print("Hello")
        print("variable is" + str(var4.get()))
        pump_io[3] = int(var4.get())

    def cb5():
        print("Hello")
        print("variable is" + str(var5.get()))
        pump_io[4] = int(var5.get())

    def cb6():
        print("Hello")
        print("variable is" + str(var6.get()))
        pump_io[5] = int(var6.get())

    def cb7():
        print("Hello")
        print("variable is" + str(var7.get()))
        pump_io[6] = int(var7.get())

    def cb8():
        print("Hello")
        print("variable is" + str(var8.get()))
        pump_io[7] = int(var8.get())

    check_button1 = ttk.Checkbutton(app_window, text='Pump1\nSHED3 H', variable=var1, command=cb1)
    check_button2 = ttk.Checkbutton(app_window, text='Pump2\nSHED3 C', variable=var2, command=cb2)
    check_button3 = ttk.Checkbutton(app_window, text='Pump3\nSHED2 H', variable=var3, command=cb3)
    check_button4 = ttk.Checkbutton(app_window, text='Pump4\nSHED2 C', variable=var4, command=cb4)
    check_button5 = ttk.Checkbutton(app_window, text='Pump5\nMAIN H', variable=var5, command=cb5)
    check_button6 = ttk.Checkbutton(app_window, text='Pump6\nMAIN C', variable=var6, command=cb6)
    check_button7 = ttk.Checkbutton(app_window, text='Pump7\nSHED1 C', variable=var7, command=cb7)
    check_button8 = ttk.Checkbutton(app_window, text='Pump8\nSHED1 H', variable=var8, command=cb8)
    check_button1.grid(row=1, column=0)
    check_button2.grid(row=2, column=0)
    check_button3.grid(row=1, column=1)
    check_button4.grid(row=2, column=1)
    check_button5.grid(row=1, column=2)
    check_button6.grid(row=2, column=2)
    check_button7.grid(row=1, column=3)
    check_button8.grid(row=2, column=3)

    def checkbutton_refresh():
        if pump_io[0] == 1:
            check_button1.state(['selected'])
        else:
            check_button1.state(['!selected'])
        if pump_io[1] == 1:
            check_button2.state(['selected'])
        else:
            check_button2.state(['!selected'])
        if pump_io[2] == 1:
            check_button3.state(['selected'])
        else:
            check_button3.state(['!selected'])
        if pump_io[3] == 1:
            check_button4.state(['selected'])
        else:
            check_button4.state(['!selected'])
        if pump_io[4] == 1:
            check_button5.state(['selected'])
        else:
            check_button5.state(['!selected'])
        if pump_io[5] == 1:
            check_button6.state(['selected'])
        else:
            check_button6.state(['!selected'])
        if pump_io[6] == 1:
            check_button7.state(['selected'])
        else:
            check_button7.state(['!selected'])
        if pump_io[7] == 1:
            check_button8.state(['selected'])
        else:
            check_button8.state(['!selected'])
        check_button1.after(ref_rate, checkbutton_refresh)

    checkbutton_refresh()


def valves_manual(app_window):
    def valve_control1(value):
        if not SHED3:
            flow_valve_pos[0] = int(value) / 10
        elif manual_mode_individual[0] == 1:
            flow_valve_pos[0] = int(value) / 10
        elif manual_mode_all == 1:
            flow_valve_pos[0] = int(value) / 10
        else:
            pass

    def valve_control2(value):
        if not SHED3:
            flow_valve_pos[1] = int(value) / 10
        elif manual_mode_individual[1] == 1:
            flow_valve_pos[1] = int(value) / 10
        elif manual_mode_all == 1:
            flow_valve_pos[1] = int(value) / 10
        else:
            pass

    def valve_control3(value):
        if not SHED2:
            flow_valve_pos[2] = int(value) / 10
        elif manual_mode_individual[2] == 1:
            flow_valve_pos[2] = int(value) / 10
        elif manual_mode_all == 1:
            flow_valve_pos[2] = int(value) / 10
        else:
            pass

    def valve_control4(value):
        if not SHED2:
            flow_valve_pos[3] = int(value) / 10
        elif manual_mode_individual[3] == 1:
            flow_valve_pos[3] = int(value) / 10
        elif manual_mode_all == 1:
            flow_valve_pos[3] = int(value) / 10
        else:
            pass

    def valve_control5(value):
        if not SHED1 and not SHED2 and not SHED3:
            flow_valve_pos[4] = int(value) / 10
        elif manual_mode_individual[4] == 1:
            flow_valve_pos[4] = int(value) / 10
        elif manual_mode_all == 1:
            flow_valve_pos[4] = int(value) / 10
        else:
            pass

    def valve_control6(value):
        if not SHED1 and not SHED2 and not SHED3:
            flow_valve_pos[5] = int(value) / 10
        elif manual_mode_individual[5] == 1:
            flow_valve_pos[5] = int(value) / 10
        elif manual_mode_all == 1:
            flow_valve_pos[5] = int(value) / 10
        else:
            pass

    def valve_control7(value):
        if not SHED1:
            flow_valve_pos[6] = int(value) / 10
        elif manual_mode_individual[6] == 1:
            flow_valve_pos[6] = int(value) / 10
        elif manual_mode_all == 1:
            flow_valve_pos[6] = int(value) / 10
        else:
            pass

    def valve_control8(value):
        if not SHED1:
            flow_valve_pos[7] = int(value) / 10
        elif manual_mode_individual[7] == 1:
            flow_valve_pos[7] = int(value) / 10
        elif manual_mode_all == 1:
            flow_valve_pos[7] = int(value) / 10
        else:
            pass

    v_label = [''] * 8
    len_valve = 70
    v_scale_1 = Scale(app_window, from_=0, to=100, orient=HORIZONTAL, command=valve_control1, length=len_valve)
    v_scale_2 = Scale(app_window, from_=0, to=100, orient=HORIZONTAL, command=valve_control2, length=len_valve)
    v_scale_3 = Scale(app_window, from_=0, to=100, orient=HORIZONTAL, command=valve_control3, length=len_valve)
    v_scale_4 = Scale(app_window, from_=0, to=100, orient=HORIZONTAL, command=valve_control4, length=len_valve)
    v_scale_5 = Scale(app_window, from_=0, to=100, orient=HORIZONTAL, command=valve_control5, length=len_valve)
    v_scale_6 = Scale(app_window, from_=0, to=100, orient=HORIZONTAL, command=valve_control6, length=len_valve)
    v_scale_7 = Scale(app_window, from_=0, to=100, orient=HORIZONTAL, command=valve_control7, length=len_valve)
    v_scale_8 = Scale(app_window, from_=0, to=100, orient=HORIZONTAL, command=valve_control8, length=len_valve)

    v_label[0] = Label(app_window, text="Valve1: \nSHED3 H")
    v_label[1] = Label(app_window, text="Valve2: \nSHED3 C")
    v_label[2] = Label(app_window, text="Valve3: \nSHED2 H")
    v_label[3] = Label(app_window, text="Valve4: \nSHED2 C")
    v_label[4] = Label(app_window, text="Valve5: \nMAIN H")
    v_label[5] = Label(app_window, text="Valve6: \nMAIN C")
    v_label[6] = Label(app_window, text="Valve7: \nSHED1 C")
    v_label[7] = Label(app_window, text="Valve8: \nSHED1 H")

    for i in range(0, 2):
        v_label[i].grid(column=0, row=i)
        v_label[i + 2].grid(column=2, row=i)
        v_label[i + 4].grid(column=4, row=i)
        v_label[i + 6].grid(column=6, row=i)

    v_scale_1.grid(column=1, row=0)
    v_scale_2.grid(column=1, row=1)
    v_scale_3.grid(column=3, row=0)
    v_scale_4.grid(column=3, row=1)
    v_scale_5.grid(column=5, row=0)
    v_scale_6.grid(column=5, row=1)
    v_scale_7.grid(column=7, row=0)
    v_scale_8.grid(column=7, row=1)

    def scale_update():
        v_scale_1.set(flow_valve_pos[0] * 10)
        v_scale_2.set(flow_valve_pos[1] * 10)
        v_scale_3.set(flow_valve_pos[2] * 10)
        v_scale_4.set(flow_valve_pos[3] * 10)
        v_scale_5.set(flow_valve_pos[4] * 10)
        v_scale_6.set(flow_valve_pos[5] * 10)
        v_scale_7.set(flow_valve_pos[6] * 10)
        v_scale_8.set(flow_valve_pos[7] * 10)
        v_scale_1.after(ref_rate + 100, scale_update)

    scale_update()

    # tk.Radiobutton(app_window, text="ON", variable = variable_p[0], value = 0).grid(row=0,column=2)
    # tk.Radiobutton(app_window, text="OFF", variable=variable_p[0], value=1).grid(row=0, column=1)


def exhaust_manual(app_window):
    var_S2 = IntVar()
    var_S3 = IntVar()
    var_damper = IntVar()
    var_EF = IntVar()

    def cb_S2():
        SHED_exhaust_valve
        print("Manual SHED2 Exhaust. Value set to: " + str(var_S2.get()))
        SHED_exhaust_valve[0] = int(var_S2.get())

    def cb_S3():
        global SHED_exhaust_valve
        print("Manual SHED3 Exhaust. Value set to: " + str(var_S3.get()))
        SHED_exhaust_valve[1] = int(var_S3.get())

    def cb_damper():
        global exhaust_damper
        print("Main Damper Value set to: " + str(var_damper.get()))
        exhaust_damper = int(var_damper.get())

    def cb_Fan():
        global exhaustfan_request
        print("Main Fan Value set to: " + str(var_EF.get()))
        exhaustfan_request = int(var_EF.get())

    damper_switch = ttk.Checkbutton(app_window, text='Main Exhaust \nDamper Valve', variable=var_damper,
                                    command=cb_damper)  # Scale(app_window,from_=0, to=1,orient=HORIZONTAL, length = 50, highlightcolor ='green', label = "Damper")#,text = "Exhaust Damper")
    damper_switch.grid(column=0, row=0)
    exhaustfan_switch = ttk.Checkbutton(app_window, text='Main Exhaust\nFan', variable=var_EF, command=cb_Fan)
    exhaustfan_switch.grid(column=0, row=1)
    exhaust_valve_SHED2 = ttk.Checkbutton(app_window, text='SHED2 Evac.\nValve', variable=var_S2, command=cb_S2)
    exhaust_valve_SHED2.grid(column=1, row=0)
    exhaust_valve_SHED3 = ttk.Checkbutton(app_window, text='SHED3 Evac.\nValve', variable=var_S3, command=cb_S3)
    exhaust_valve_SHED3.grid(column=1, row=1)

    def checkbutton_refresh():
        if exhaust_damper == 1:
            damper_switch.state(['selected'])
        else:
            damper_switch.state(['!selected'])
        if exhaustfan_request == 1:
            exhaustfan_switch.state(['selected'])
        else:
            exhaustfan_switch.state(['!selected'])
        if SHED_exhaust_valve[0] == 1:
            exhaust_valve_SHED2.state(['selected'])
        else:
            exhaust_valve_SHED2.state(['!selected'])
        if SHED_exhaust_valve[1] == 1:
            exhaust_valve_SHED3.state(['selected'])
        else:
            exhaust_valve_SHED3.state(['!selected'])
        exhaust_valve_SHED2.after(ref_rate, checkbutton_refresh)

    checkbutton_refresh()


"""
/////////////////////////////////////////////////////////////////////////////////////////////////////////////
Tab 1 is is the main frame of the application. This means that all of the controls, automatic settings, and alarm status is included
Alarms and Flow Monitoring is on the left side
SHED control, exhaust stratus and manual controls are on the right side
////////////////////////////////////////////////////////////////////////////////////////////////////////////
THIS IS A CODE BREAK to allow for easy visibility when scanning through the file.
////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


class Tab1(tk.Frame):

    def __init__(self, parent, controller):
        s = ttk.Style()
        s.configure('Large.TLabelframe.Label',
                    font=('Helvetica', 15, 'bold'))  # configure font for main labels on labelframes
        s2 = ttk.Style()
        s2.configure('small.TLabelframe.Label',
                     font=("Helvetica", 10, 'bold'))  # configure font for sub labels on labelframes
        tk.Frame.__init__(self, parent)
        # left_frame = ttk.Frame(self)
        # right_frame = ttk.Frame(self)
        # left_frame.grid(column = 0, row = 0, padx = 5)
        # right_frame.grid(column=1, row=0, padx = 5)
        flow_frame = ttk.LabelFrame(self, text="Flow Monitoring", style="Large.TLabelframe")
        flow_frame.grid(column=0, row=1, padx=2, pady=2, rowspan=5)
        flow_main_frame = ttk.LabelFrame(flow_frame, text="Main Flow", style="small.TLabelframe")
        flow_main_frame.grid(column=0, row=0, pady=2)
        FlowMonitor(flow_main_frame, 4, 5)
        flow_shed1_frame = ttk.LabelFrame(flow_frame, text="SHED1 Flow", style="small.TLabelframe")
        flow_shed1_frame.grid(column=0, row=1, pady=2)
        FlowMonitor(flow_shed1_frame, 7, 6)
        flow_shed2_frame = ttk.LabelFrame(flow_frame, text="SHED2 Flow", style="small.TLabelframe")
        flow_shed2_frame.grid(column=0, row=2, pady=2)
        FlowMonitor(flow_shed2_frame, 2, 3)
        flow_shed3_frame = ttk.LabelFrame(flow_frame, text="SHED3 Flow", style="small.TLabelframe")
        flow_shed3_frame.grid(column=0, row=3, pady=2)
        FlowMonitor(flow_shed3_frame, 0, 1)

        shed_auto_frame = ttk.LabelFrame(self, text="AUTO SHED CONTROL", style="Large.TLabelframe")
        shed_auto_frame.grid(column=1, row=0, padx=0, pady=5, columnspan=10, rowspan=2)
        SHED_auto(shed_auto_frame)

        man_frame = ttk.LabelFrame(self, text="Manual Control", style="Large.TLabelframe")
        man_frame.grid(column=1, row=2, padx=0, pady=5, columnspan=10)
        Manual_Control__(man_frame)

        # ALARM FRAME
        alarm_frame_tab1 = ttk.LabelFrame(self, text="Alarm Status", style="Large.TLabelframe")
        alarm_frame_tab1.grid(column=0, row=0, padx=10, pady=2)
        AlarmMonitor(alarm_frame_tab1)

        # EXHAUST FRAME
        exhaust_frame_tab1 = ttk.LabelFrame(self, text="Exhaust  Status", style="Large.TLabelframe")
        exhaust_frame_tab1.grid(column=2, row=3, padx=10, pady=0, rowspan=1)
        ExhaustMonitor(exhaust_frame_tab1)

        exit_btn = Button(self, width=6, font=("Verdana", 12, 'bold'), text="EXIT", bg='tomato2', command=stop_program)
        exit_btn.grid(column=3, row=3, padx=1, rowspan=1)


def live_plot(frame):
    # xlist = [1,2,3,4,5,6,7,8,9]
    # ylist = [5,2,6,9,1,2,4,6,3]
    xvals = 'Entry Time'
    yvals = 'T3'
    filename = "DATALOGS/main_LOGfile_03-Sep-2020_08-23-23.csv"
    df_csv = pd.read_csv(filename, header=0)
    xlist = list(range(1, plot_length + 1))
    x_ticks = df_csv[str(xvals)].tolist()

    ylist = df_csv[str(yvals)].tolist()
    if len(ylist) > plot_length:
        ylist = ylist[-plot_length:]
    # a.plot(xlist, ylist)
    canvas = FigureCanvasTkAgg(f, frame)
    canvas.draw()
    canvas.get_tk_widget().grid(column=0, row=1)


def Manual_Control__(frame):
    pumps_frame = ttk.LabelFrame(frame, text="Pump Control")
    pumps_frame.grid(column=0, row=1, padx=10, pady=10)
    pumps_manual(pumps_frame)

    valves_frame = ttk.LabelFrame(frame, text="Valve Control")
    valves_frame.grid(column=0, row=2, columnspan=2)
    valves_manual(valves_frame)

    exhaust_frame_tab = ttk.LabelFrame(frame, text="Exhaust Control")
    exhaust_frame_tab.grid(column=1, row=1, padx=10, pady=10)
    exhaust_manual(exhaust_frame_tab)


class Tab2(tk.Frame):

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)

        lbl2 = tk.Label(self, text="Graph Page!")
        lbl2.grid(column=0, row=0)
        SHED_Status(self)
        # xlist = [1,2,3,4,5,6,7,8,9]
        # ylist = [5,2,6,9,1,2,4,6,3]
        xvals = 'Entry Time'
        yvals = 'T3'
        filename = "DATALOGS/main_LOGfile_03-Sep-2020_08-23-23.csv"
        df_csv = pd.read_csv(filename, header=0)
        xlist = list(range(1, plot_length + 1))
        x_ticks = df_csv[str(xvals)].tolist()

        ylist = df_csv[str(yvals)].tolist()
        if len(ylist) > plot_length:
            ylist = ylist[-plot_length:]
        a2.plot(xlist, ylist)
        canvas = FigureCanvasTkAgg(f2, self)
        canvas.draw()
        canvas.get_tk_widget().grid(column=0, row=1)


class Tab3(tk.Frame):

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        # pumps
        pumps_frame = ttk.LabelFrame(self, text="Pump Control")
        pumps_frame.grid(column=0, row=1, padx=10, pady=10)
        pumps_manual(pumps_frame)
        lbl3 = tk.Label(self, text="Tab3")
        lbl3.grid(column=0, row=0)

        valves_frame = ttk.LabelFrame(self, text="Valve Control")
        valves_frame.grid(column=0, row=2, columnspan=2)
        valves_manual(valves_frame)

        exhaust_frame_tab3 = ttk.LabelFrame(self, text="Exhaust Control")
        exhaust_frame_tab3.grid(column=1, row=1, padx=10, pady=10)
        exhaust_manual(exhaust_frame_tab3)

        alarm_test_frame = ttk.LabelFrame(self, text="Alarm Testing")
        alarm_test_frame.grid(column=0, row=3, columnspan=2, pady=10)
        test1_btn = Button(alarm_test_frame, text="SHED1 Alarm", command=lambda: alarm_test(1))
        test1_btn.grid(column=0, row=1, padx=5)
        test2_btn = Button(alarm_test_frame, text="SHED2 Alarm", command=lambda: alarm_test(2))
        test2_btn.grid(column=1, row=1, padx=5)
        test3_btn = Button(alarm_test_frame, text="SHED3 Alarm", command=lambda: alarm_test(3))
        test3_btn.grid(column=2, row=1, padx=5)

        exit_btn = Button(self, width=25, font=LARGE_FONT, text="EXIT PROGRAM", command=stop_program)
        exit_btn.grid(column=10, row=0, padx=100, rowspan=3)

        options_frame = ttk.LabelFrame(self, text='Options')
        options_frame.grid(column=0, row=4)
        options_manual(options_frame)

        def demo_switch():
            global demo
            demo = 1 - demo
            if demo == 1:
                demo_btn.configure(bg='green', text="DEMO switch: ACTIVE")
                print("Demo Mode is ACTIVE")
            else:
                demo_btn.configure(bg='red', text="DEMO switch: OFF")
                print("Demo Mode is OFF")

        # demo_btn = Button(self, width=25,font =LARGE_FONT, text = "DEMO switch", command=demo_switch)
        # demo_btn.grid(column = 10, row = 3, padx = 100, rowspan = 3)


def FlowMonitor_wide(app_window, item1, item2):
    hotLabel0 = Label(app_window, text="Cold", font=("Bold", 10), padx=9)
    coldLabel0 = Label(app_window, text="     Hot", font=("Bold", 10), padx=9)
    hotLabel0.grid(row=2, column=0)
    coldLabel0.grid(row=2, column=5)
    flowrate_text_tabx[item1] = Label(app_window, padx=10, width=flow_width)
    flowrate_text_tabx[item2] = Label(app_window, padx=10, width=flow_width)
    flowrate_text_tabx[item1].grid(row=2, column=2)
    flowrate_text_tabx[item2].grid(row=2, column=7)
    pump_text_tabx[item1] = Label(app_window, padx=10, width=pump_width)
    pump_text_tabx[item2] = Label(app_window, padx=10, width=pump_width)
    pump_text_tabx[item1].grid(row=2, column=1)
    pump_text_tabx[item2].grid(row=2, column=6)
    flow_temp_text_tabx[item1] = Label(app_window, padx=10, width=flow_temp_width)
    flow_temp_text_tabx[item2] = Label(app_window, padx=10, width=flow_temp_width)
    flow_temp_text_tabx[item1].grid(row=2, column=3)
    flow_temp_text_tabx[item2].grid(row=2, column=8)
    flow_valve_text_tabx[item1] = Label(app_window, padx=10, width=valve_width)
    flow_valve_text_tabx[item2] = Label(app_window, padx=10, width=valve_width)
    flow_valve_text_tabx[item1].grid(row=2, column=4)
    flow_valve_text_tabx[item2].grid(row=2, column=9)

    lowerx = min(item1, item2)
    largerx = max(item1, item2)
    for n in range(lowerx, largerx + 1):
        pump_status(pump_text_tabx, n)
        flow_calculate(flowrate_text_tabx, n)
        flow_temp_status(flow_temp_text_tabx, n)
        valve_position(flow_valve_text_tabx, n)


def PID_frame(app_window, p, i, d):
    def update_pid(p, i, d, pentry, ientry, dentry):
        print(p)
        print(i)
        print(d)
        p_ = int(pentry.get())
        i_ = ientry.get()
        d_ = dentry.get()

        print(p_)
        print(type(p_))
        print(i)
        print(d)

    p_ = IntVar(app_window, value=p)
    i_ = IntVar(app_window, value=i)
    d_ = IntVar(app_window, value=d)

    p_label = Label(app_window, text="P: ", font=("Bold", 10))
    p_label.grid(row=0, column=0, padx=10)
    i_label = Label(app_window, text="I: ", font=("Bold", 10))
    i_label.grid(row=0, column=2, padx=10)
    d_label = Label(app_window, text="D: ", font=("Bold", 10))
    d_label.grid(row=0, column=4, padx=10)
    p_entry = Entry(app_window, width=7, textvariable=str(p_))
    p_entry.grid(row=0, column=1, padx=10)
    i_entry = Entry(app_window, width=7, textvariable=str(i_))
    i_entry.grid(row=0, column=3, padx=10)
    d_entry = Entry(app_window, width=7, textvariable=str(d_))
    d_entry.grid(row=0, column=5, padx=10)
    update_btn = Button(app_window, text="update", command=(lambda: update_pid(p, i, d, p_entry, i_entry, d_entry)))
    update_btn.grid(row=0, column=6, padx=10)


class Permeation_Tab(tk.Frame):

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        top_frame = ttk.Frame(self)
        top_frame.grid(column=0, row=0, columnspan=10)
        main_flow_frame = ttk.LabelFrame(top_frame, text="MainFlow")
        main_flow_frame.grid(column=0, row=0, columnspan=1)
        FlowMonitor_wide(main_flow_frame, 5, 4)

        exhaust_lbl = Label(top_frame, text='')
        exhaust_lbl.grid(column=1, row=0, padx=10)
        exhaustfan_alarm_update(exhaust_lbl)

        SHED2_frame = tk.LabelFrame(self, text="SHED2", borderwidth=5)
        SHED2_frame.grid(column=0, row=1, padx=1, pady=10)
        SHED3_frame = tk.LabelFrame(self, text="SHED3", borderwidth=5)
        SHED3_frame.grid(column=1, row=1, padx=1, pady=10)

        PERM_SHED_control(SHED2_frame, 2, 0, 0)
        PERM_SHED_control(SHED3_frame, 3, 0, 0)
        flow_shed2_frame2 = ttk.LabelFrame(SHED2_frame, text="SHED2 Flow")
        flow_shed2_frame2.grid(column=1, row=0, pady=5, rowspan=3, columnspan=1)
        FlowMonitor_tabx(flow_shed2_frame2, 2, 3)
        pid_shed2_frame = ttk.LabelFrame(SHED2_frame, text="PID Values")
        pid_shed2_frame.grid(column=0, row=4, pady=5, columnspan=2)
        PID_frame(pid_shed2_frame, P1, I1, D1)

        SHED2_lbl = tk.Label(SHED2_frame, text=str(SHED_temp_actual[0]) + u'\N{DEGREE SIGN}' + "C", font=('bold', 100))
        SHED2_lbl.grid(column=0, row=5, columnspan=2)

        flow_shed3_frame = ttk.LabelFrame(SHED3_frame, text="SHED3 Flow")
        flow_shed3_frame.grid(column=1, row=0, pady=5, rowspan=3)
        FlowMonitor_tabx(flow_shed3_frame, 0, 1)

        pid_shed3_frame = ttk.LabelFrame(SHED3_frame, text="PID Values")
        pid_shed3_frame.grid(column=0, row=4, pady=5, columnspan=2)
        PID_frame(pid_shed3_frame, P2, I2, D2)

        SHED3_lbl = tk.Label(SHED3_frame, text=str(SHED_temp_actual[1]) + u'\N{DEGREE SIGN}' + "C", font=('bold', 100))
        SHED3_lbl.grid(column=0, row=5, columnspan=2)

        def update_temps():
            SHED2_lbl.configure(text=str(SHED_temp_actual[0]) + u'\N{DEGREE SIGN}' + "C")
            SHED3_lbl.configure(text=str(SHED_temp_actual[1]) + u'\N{DEGREE SIGN}' + "C")
            SHED2_lbl.after(ref_rate, update_temps)

        update_temps()


def plot_save():
    pass


def Dataset_save(func_filename):
    entry_time_raw = datetime.now()
    entry_time = datetime.now().strftime("%d/%b/%Y_%H:%M")
    Header = ["time_raw", "Entry Time", "SHED2 Set Temp.", "Shed2 Temp.", "PID SHED2", "SHED3 Set Temp.", "SHED3 Temp.",
              "PID SHED3",
              "P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "T1",
              "T2", "T3", "T4", "T5", "T6", "T7", "T8", "V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8",
              "Req. for Exhaust Fan", "Exhaust Fan Feedback"]
    saveline = [entry_time_raw, entry_time, set_temp[0], SHED_temp_actual[0], SHED_pid[0], set_temp[1],
                SHED_temp_actual[1], SHED_pid[1],
                pump_io[0], pump_io[1], pump_io[2], pump_io[3], pump_io[4], pump_io[5], pump_io[6], pump_io[7],
                flowrate_value[0],
                flowrate_value[1],
                flowrate_value[2], flowrate_value[3], flowrate_value[4], flowrate_value[5], flowrate_value[6],
                flowrate_value[7], Temp_water[0], Temp_water[1], Temp_water[2], Temp_water[3],
                Temp_water[4], Temp_water[5], Temp_water[6], Temp_water[7], flow_valve_pos[0], flow_valve_pos[1], flow_valve_pos[2],
                flow_valve_pos[3], flow_valve_pos[4], flow_valve_pos[5], flow_valve_pos[6], flow_valve_pos[7],
                exhaustfan_request, exhaustfan_feedback]
    entry = pd.DataFrame(data=[saveline], columns=Header)
    if os.path.isfile(func_filename):
        entry.to_csv(func_filename, header=False, mode='a', index=False)

    else:
        entry.to_csv(func_filename, header=True, mode='a', index=False)
        start_date_time_raw = datetime.now()


def stop_program():
    global exit_case, SHED1, SHED2, SHED3
    # if okay is selected, the program will terminate itself appropriately
    if messagebox.askokcancel("Quit", "Do you want to  quit?\nThis will terminate everything including data recording"):
        SHED1 = False
        SHED2 = False
        SHED3 = False
        exit_case = True
        sys.exit()


sched = BackgroundScheduler()
sched.start()

sched.add_job(background__, 'interval', seconds=2)  # , max_instances=2)
#sched.add_job(deadhead_protection_function, 'interval', seconds=1)
sched.add_job(Alarm_prompt, 'interval', seconds=2.5)
sched.add_job(flash__, 'interval', seconds=.5)
# ani = animation.FuncAnimation(f,animate, interval = 1000)
# sched.add_job(lambda:animate(1), 'interval', seconds = 1)

app = MainApplication()
# app.attributes('-fullscreen', True) # Edit out line when Fullscreen is not wanted

app.mainloop()
