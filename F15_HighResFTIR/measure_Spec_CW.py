# -*- coding: utf-8 -*-
"""
Created on Tue Jun 13 16:56:03 2017

@author: Polin
"""
# import visa
import pyvisa as visa

import os
import sys
import numpy as np
import matplotlib.pyplot as plt
sys.path.append(r'Z:\lab\meas\AndresForrer\Python\PythonProjects\THzPythonScripts')
from time import sleep
import DeviceControl.lockin as loc
import DeviceControl.hpVoltMeter as hpM
import DeviceControl.lakeShore as laSh
import DeviceControl.QubeCL as qub
sys.path.append(r'Z:\lab\meas\Paolo\Python\fancy_keithley')
import fancy_keithley as ke
sys.path.append(r'Z:\lab\meas\Paolo\Python\Analysis')
from math_functions import append_vec, resample
from OPUS_sweep_analysis import fft_and_plot
from my_plots import fig_slider_double

from multiprocessing import Process, Queue
from RunMeas import*



def measureSpecCW(savingPath, name, length, width, I_V,
                 X,
                 maxVolt = 16, maxCurr = 1, delayCurrPower= 0.5,
                 currSource_addr = 'GPIB::18::INSTR',
                 lakeShore_addr = 'GPIB::5::INSTR',
                 lockin_addr = 'GPIB::8::INSTR',
                 HHPVoltmeter_addr = 'GPIB0::19::INSTR',
                 saveRaw = False, runs = 1, speed = 2, # in mm/s (standard: ~3mm/s)
                 startPoint = -380,           # in mm   #-380 (20 is reserved for acc.)
                 endPoint = 0,                # in mm   # max 390 (10 is reserved for acc.)
                 laserWavelenght = 630e-9,    # in m,  HeNe (630)/  (532) or 1550 
                 fs              = 1e6,       # samples per second (1 MSps is default)
                 maxRecTime = 0,
                 DT = 8, #down sampling factor
                 f_lim = [1.5,5],
                 dt_monitorT = 0.1,
                 plots = True
                 ):


#-----inner functions definition--------------------------------------
    def Path_gen( Current, Voltage, Temperature):
            
     
            if not os.path.exists(savingPath): os.makedirs(savingPath)
            
    
            temper = str(int(round(Temperature)))
    
            filename = (name+('_%3.2f'%length)+'mm_'+
                        str(width)+'um_'+temper+'K_'+('I_%3.3f_A_'%Current) + ('V_%3.3f_V_'%Voltage) )
    
    
            return filename
    
    # def monitorT():
        
    #     while True:
    #         Temp = ls.get_temp()[0]
    #         sleep(dt_monitorT)
    

    # connect devices
    rm = visa.ResourceManager()
    if currSource_addr == "ASRL3::INSTR":
        keit = qub.qubeCL(rm.open_resource('ASRL3::INSTR', baud_rate = 115200))
    else:
        keit = ke.keithley(currSource_addr)

    ls = laSh.lakeShore(rm.open_resource(lakeShore_addr))
    if lockin_addr != '':
        lock = loc.SR830(rm.open_resource(lockin_addr))
    if HHPVoltmeter_addr!= '':
        hp = hpM.hpVoltMeter(HHPVoltmeter_addr)



    # measures LIV----------------------------------------------------------------

    keit.set_on()
    keit.set_voltageProtect(maxVolt)
    keit.set_currentProtect(maxCurr)
    keit.set_voltage(X[0])

    sleep(delayCurrPower)
    
    Current, Voltage, Temperature = np.array([]), np.array([]), np.array([])
    del_tot, ifg_tot, f_tot, If_tot = np.array([]), np.array([]), np.array([]), np.array([])

    for ii in range(len(X)):
    
        if I_V == 'V':
            keit.set_voltage(X[ii])
        else:
            keit.set_current(X[ii])
            
        sleep(delayCurrPower)
        V, I = keit.get_V_I()
        Temp = ls.get_temp()[0]
        
        filename =  Path_gen(I, V, Temp)
        
        print('######################################################################################')
        print('##                             run measurement %d of %d                               ## '%(ii+1, len(X)))
        print('##                               %s set to %3.3f %s                                   ## '%(I_V, X[ii], 'A'*(I_V == 'I')+ 'V'*(I_V == 'V')))
        print('######################################################################################')
        delay, Ifg, f, If =  RunScan(savingPath, filename, saveRaw = saveRaw, runs = runs, speed = speed,
                    startPoint = startPoint , endPoint = endPoint, laserWavelenght = laserWavelenght,
                     fs  = fs, maxRecTime = maxRecTime, DT = DT  )
        
           
        print('done')
        print('\n\n')
        Current, Voltage, Temperature = np.append(Current, I), np.append(Voltage, V), np.append(Temperature, Temp)
        del_tot, ifg_tot, f_tot, If_tot = update_global(ii,delay, Ifg, f, If, del_tot, ifg_tot, f_tot, If_tot )
        
        if plots:    
            if ii > 0:
                plots.kill()
    
            plots  = Process(target=update_plot, args=(ii, del_tot, ifg_tot, f_tot, If_tot, savingPath, I_V, X[:ii+1], f_lim))        
            plots.start()
    
    
    
       
    saveParams(savingPath, Current, Voltage, Temperature, del_tot, ifg_tot, f_tot, If_tot)    
        
    keit.set_off()
    keit.close()
    ls.close()

    return  del_tot, ifg_tot, f_tot, If_tot







def saveParams(savingPath, Current, Voltage, Temperature, del_tot, ifg_tot, f_tot, If_tot):
    
    storepathparams = savingPath+'/Params'
    if not os.path.exists(storepathparams): os.makedirs(storepathparams)
    
    np.save(storepathparams+'/CurrVoltTemp', [Current, Voltage, Temperature])
    print('Saved: paramters' )
    
    storepathglobal = savingPath+'/Global'
    if not os.path.exists(storepathglobal): os.makedirs(storepathglobal)
    
    np.save(storepathglobal+'/xI.npy', [del_tot, ifg_tot])
    np.save(storepathglobal+'/f_If.npy', [f_tot, If_tot])
    print('Saved: Global Variables' )

    
    return


    
def update_global(i, x,I,f,If, x_tot, I_tot,f_tot,If_tot):
    
    if i>0 and len(x) != len(x_tot[:,0]):
        x,I = resample(x,I, len(x_tot[:,0]))
        f,If = resample(f,If, len(f_tot[:,0]))
        
    x_tot, I_tot = append_vec(x_tot, np.squeeze(x), i), append_vec(I_tot, np.squeeze(I), i)
    f_tot, If_tot = append_vec(f_tot, np.squeeze(f), i), append_vec(If_tot, np.squeeze(If), i)
    
    return x_tot, I_tot,f_tot,If_tot

    
    
def update_plot(i, x, I, f, If, savingPath, I_V, X, f_lim)  :
    
    if i  == 0:
        X = [X]
    storepathfig = savingPath+'/Figures'
    if not os.path.exists(storepathfig): os.makedirs(storepathfig)

    
    fig_slider_double(f*1e-12,If, x*1e3,I, param = X, xlabel1 = 'f (THz)',xlabel2 = 'delay (mm)',ylabel2= 'I (a.u.)', ylabel1= 'I (a.u.)',param_name=I_V,
                     param_unit='(A)'*(I_V == 'I')+ '(V)'*(I_V == 'V'), points = '-', x1_lim = f_lim,
                     size = [11,8], path = storepathfig, name = 'spectra', log1 = True, initial_pos = -1)
    















