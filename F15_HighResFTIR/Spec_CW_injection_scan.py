# -*- coding: utf-8 -*-
"""
Created on Tue Jun 13 22:50:24 2017

@author: Polin
"""
import sys 
sys.path.append(r'Z:\lab\meas\AndresForrer\Python\PythonProjects\THzPythonScripts')
from DeviceControl.rohde_schwarz import smf100a

sys.path.append(r'Z:\lab\meas\Paolo\Python\fancy_keithley')
sys.path.append(r'Z:\lab\meas\Paolo\Python\Analysis')
from math_functions import append_vec
import numpy as np
import os
import pyvisa as visa
from measure_Spec_CW import measureSpecCW

from multiprocessing import Process
import threading


from PyQt5.QtWidgets import QApplication
from PLot_spec import  PlotSpec, PlotsRun

from time import localtime, strftime, sleep

# %%
# 1A
#Name        = 'G1_med_2256'
# 1B
name        = 'EV2244'
savingPath       = r'Z:\lab\meas\Paolo\Python\F15_HighResFTIR\test'

length      = 2*np.pi                          #in mm
width       = 40                            # in um

I_V = 'I' #select 'I' to drive in current or 'V' to drive in voltage

X = [0.001,0.002,0.003,0.004] #in A or V
                            
MaxVolt= 15 #V
maxCurr = 1000e-3 #A

delayCurrSpec = 0.1


#%%injection settings

LEVELS = [-20, -10,-5,0]
f0 = 15
span = 30
#repeat = np.array([2,3])
freqS = np.linspace(f0+span/2, f0-span/2, 9)



#%%FTIR Settings

speed = 5 # in mm/s (standard: ~3mm/s)
startPoint = -330           # in mm   #-380 (20 is reserved for acc.)
endPoint = -300                # in mm   # max 390 (10 is reserved for acc.)


f_lim = [2,4]


# %%select  current source
CurrentSource_addr  = 'USB0::0x05E6::0x2636::1408928::INSTR'#GPIB0::23::INSTR'GPIB0::18::INSTR'
LakeShore_addr      = 'GPIB::11::INSTR'
HHPVoltmeter_addr   = 'GPIB0::19::INSTR'




#%% run experiment
#####################################################################################################################################
if __name__ == "__main__":
    
    # rm = visa.ResourceManager()
    # RFgen = smf100a(rm.open_resource('USB0::0x0AAD::0x0054::180297::INSTR'))

    laserWavelenght = 630e-9    # in m,  HeNe (630)/  (532) or 1550 
    fs              = 1e6       # samples per second (1 MSps is default)
    maxRecTime = 0
    DT = 8 #down sampling factor
    saveRaw = False
    runs = 1 
    timer = 1
    # # app = QApplication(sys.argv)
    # # plots = PlotSpec(I_V, f_lim = f_lim, path = savingPath + '/Figures')
    # # plots.resize(1050,900)
    # # # plots.show()
    
    
    
    # # plots_proc  = Process(target=app.exec_())        
    # # plots_proc.start()
    
    # plots_app = Process(target =  QApplication(sys.argv), args = ())
    
    pg = PlotsRun(I_V, f_lim = f_lim, path = savingPath + '/Figures')
    # keepactive = Process(target =  pg.keep_active(timer = timer), args = ())
    # keepactive.start()
    # plots = PlotSpec(I_V, f_lim = f_lim, path = savingPath + '/Figures')
    # plots.resize(1050,900)
    # plots.show()
    # plots_app.exec_()

    for KKK in LEVELS:
        # RFgen.set_power(KKK)
        pg.update(  KKK, 'P' )
        
        for JJJ in freqS:
            # RFgen.set_freq(JJJ*1e9)
            pg.update( JJJ, 'f' )
                          
            SavingPath  = savingPath+ '\injected_%sdBm_amp_%3.4fGHz' %(KKK,JJJ)
            
            h, t = os.path.split(SavingPath)
            SavingPath = os.path.join(h,strftime("%Y%m%d_%H%M_", localtime())+t)
            if not os.path.exists(SavingPath):
                os.makedirs(SavingPath)
                print('Path generated: ', SavingPath)
                os.makedirs(SavingPath+r'/Npy')

            # x,I,f,If = measureSpecCW(SavingPath, name, length, width,  I_V,
            #             X, saveRaw = saveRaw, runs = runs, speed = speed, 
            #             startPoint = startPoint,           
            #             endPoint = endPoint,               
            #             laserWavelenght = laserWavelenght,    
            #             fs              = fs,       
            #             maxRecTime = maxRecTime,
            #             DT = DT, #down sampling factor             
            #             maxVolt = MaxVolt,
            #             maxCurr = maxCurr, delayCurrPower=delayCurrSpec,
            #             currSource_addr = CurrentSource_addr,
            #             lakeShore_addr = LakeShore_addr,
            #             HHPVoltmeter_addr='',
            #             f_lim = f_lim, plots = False
            #                 )
            # for i in range(4):
            #     print('prosciutto')
            #     sleep(1)
            x,I = np.array([]),np.array([])
            f,If = np.array([]),np.array([])

            for iii in range(len(X)):
                x,I = append_vec(x, np.linspace(1,200, 10000), iii), append_vec(I, np.sin( 2*np.pi/10*(np.linspace(1,200, 10000)+JJJ/2)), iii)
                f,If = append_vec(x, np.linspace(1,200, 10000), iii), append_vec(I, np.sin( 2*np.pi/10*(np.linspace(1,200, 10000)-JJJ/2)), iii)
                
            pg.update(  X, 'X',xnew = np.transpose(x), Inew=np.transpose(I),fnew= np.transpose(f),Ifnew =np.transpose(If) )
            
    # keepactive.join()
    pg.hold()        
    storepathparams = savingPath+'/INJ_Params'
    if not os.path.exists(storepathparams): os.makedirs(storepathparams)
    
    np.save(storepathparams+'/P_inj', [LEVELS])
    np.save(storepathparams+'/f_inj', [freqS])
    print('Saved: Injection paramters' )

    ###############################################################################################################################
    
    
    
    
    
    
    
# def update_global(i, x,I,f,If, x_tot, I_tot,f_tot,If_tot):
    
#     if i>0 and len(x) != len(x_tot[:,0]):
#         x,I = resample(x,I, len(x_tot[:,0]))
#         f,If = resample(f,If, len(f_tot[:,0]))
        
#     x_tot, I_tot = append_vec(x_tot, np.squeeze(x), i), append_vec(I_tot, np.squeeze(I), i)
#     f_tot, If_tot = append_vec(f_tot, np.squeeze(f), i), append_vec(If_tot, np.squeeze(If), i)
    
#     return x_tot, I_tot,f_tot,If_tot

    
    
# def update_plot(i, x, I, f, If, savingPath, I_V, X, f_lim)  :
    
#     if i  == 0:
#         X = [X]
#     storepathfig = savingPath+'/Figures'
#     if not os.path.exists(storepathfig): os.makedirs(storepathfig)

    
#     fig_slider_double(f*1e-12,If, x*1e3,I, param = X, xlabel1 = 'f (THz)',xlabel2 = 'delay (mm)',ylabel2= 'I (a.u.)', ylabel1= 'I (a.u.)',param_name=I_V,
#                       param_unit='(A)'*(I_V == 'I')+ '(V)'*(I_V == 'V'), points = '-', x1_lim = f_lim,
#                       size = [11,8], path = storepathfig, name = 'spectra', log1 = True, initial_pos = -1)
