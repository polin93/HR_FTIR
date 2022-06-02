# -*- coding: utf-8 -*-
"""
Created on Tue Jun 13 22:50:24 2017

@author: Polin
"""
import sys 
#sys.path.append(r'Z:\lab\meas\AndresForrer\Python\PythonProjects\THzPythonScripts')
sys.path.append(r'Z:\lab\meas\Paolo\Python\fancy_keithley')
sys.path.append(r'Z:\lab\meas\Paolo\Python\Analysis')
import numpy as np
import os

from measure_Spec_CW import measureSpecCW
# %%
# 1A
#Name        = 'G1_med_2256'
# 1B
name        = 'EV2244'
savingPath       = r'Z:\lab\meas\Paolo\EV2244-Rings\chip16\egg\Spec CW HR\20K\I scan'

length      = 2*np.pi                          #in mm
width       = 40                            # in um

I_V = 'I' #select 'I' to drive in current or 'V' to drive in voltage

X = np.linspace(0.5,0.5,1) #in A or V
                            
MaxVolt= 15 #V
maxCurr = 1000e-3 #A

delayCurrSpec = 0.1


#%%FTIR Settings

speed = 1.5 # in mm/s (standard: ~3mm/s)
startPoint = -330           # in mm   #-380 (20 is reserved for acc.)
endPoint = -250                # in mm   # max 390 (10 is reserved for acc.)


f_lim = [2,4]


# %%select  current source
CurrentSource_addr  = 'USB0::0x05E6::0x2636::1408928::INSTR'#GPIB0::23::INSTR'GPIB0::18::INSTR'
LakeShore_addr      = 'GPIB::11::INSTR'
HHPVoltmeter_addr   = 'GPIB0::19::INSTR'




#%% run experiment
#####################################################################################################################################
if __name__ == "__main__":
    
    laserWavelenght = 630e-9    # in m,  HeNe (630)/  (532) or 1550 
    fs              = 1e6       # samples per second (1 MSps is default)
    maxRecTime = 0
    DT = 8 #down sampling factor
    saveRaw = False
    runs = 1 

    
    from time import localtime, strftime
    h, t = os.path.split(savingPath)
    savingPath = os.path.join(h,strftime("%Y%m%d_%H%M_", localtime())+t)
    if not os.path.exists(savingPath):
        os.makedirs(savingPath)
        print('Path generated: ', savingPath)
        os.makedirs(savingPath+r'/Npy')


    x,I,f,If = measureSpecCW(savingPath, name, length, width,  I_V,
                X, saveRaw = saveRaw, runs = runs, speed = speed, 
                startPoint = startPoint,           
                endPoint = endPoint,               
                laserWavelenght = laserWavelenght,    
                fs              = fs,       
                maxRecTime = maxRecTime,
                DT = DT, #down sampling factor             
                maxVolt = MaxVolt,
                maxCurr = maxCurr, delayCurrPower=delayCurrSpec,
                currSource_addr = CurrentSource_addr,
                lakeShore_addr = LakeShore_addr,
                HHPVoltmeter_addr='',
                f_lim = f_lim
                    )
    
    ###############################################################################################################################