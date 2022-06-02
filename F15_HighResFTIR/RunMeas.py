
# -*- coding: utf-8 -*-
"""
Created on Thu Dec 16 13:36:27 2021

@author: Polin
"""
import numpy as np
import matplotlib.pyplot as plt
import sys
from time import time, sleep
from time import localtime, strftime
sys.path.append(r'C:\\Users\\F15_HiResFTIR\\Documents\\Python')
from newportxps import NewportXPS
from newportxps import XPS_C8_drivers
from multiprocessing import Process, Queue
import threading
sys.path.append(r'Z:\lab\meas\AndresForrer\HiResFTIR\red_pitaya_streaming_client_python-master')
from rp_stream_threaded_Andres import SocketClientThread, ClientCommand, ClientReply
from scipy.interpolate import interp1d
import os

#%%
"""
note: CH1 HeNe    CH2 THz detector
"""

#%% DO NOT CHANGE BELOW HERE!!!!!!!!!

def RunScan(savingPath, name, saveRaw = False, runs = 1, speed = 2, # in mm/s (standard: ~3mm/s)
            startPoint = -380,           # in mm   #-380 (20 is reserved for acc.)
            endPoint = 0,                # in mm   # max 390 (10 is reserved for acc.)
            laserWavelenght = 630e-9,    # in m,  HeNe (630)/  (532) or 1550 
            fs              = 1e6,       # samples per second (1 MSps is default)
            maxRecTime = 0,
            DT = 8 #down sampling factor
            ):
    
    

    
    if maxRecTime ==0:
        maxRecTime      = np.abs(startPoint-endPoint)/speed*1.2 # sec (default 180s)
    

        
    #stream in different process to ensure speed
    q = 10
    p           = Process(target=runStream, args=(q,fs,laserWavelenght, speed, savingPath, saveRaw, name, maxRecTime, DT ))
        
    p.start()
    sleep(2)
    for jj in range(runs):
        runStage(startPoint, endPoint, speed)
        
        DELAY   = np.load(savingPath+r'/Npy/'+name+ r'run_ifg_delay.npy')
        IFG     = np.load(savingPath+r'/Npy/'+name+ r'run_ifg_sig.npy')
        
        zff         = 4
        FRE         = np.fft.rfftfreq(int(2**(np.log2(len(DELAY))//1+zff)), laserWavelenght/2/299792458*DT)
        FFT         = np.abs(np.fft.rfft(np.blackman(len(IFG))*IFG, int(2**(np.log2(len(IFG))//1+zff))))/np.sum(np.blackman(len(IFG)))

    return DELAY, IFG,  FRE, FFT 
        
        
#%%Queue printer
def queuePrinter(queue, maxRecTime):
    queueMsg = True
    tt = time()
    while queueMsg and abs(time()-tt) <maxRecTime:
        temp = queue.get()
        if temp == 'off':
            queueMsg = False
            break
        else:
            print(temp)
#%% data acquisiton - Red Pitaya - settings on server
def runStream(queue, fs, RefLasWaveLen, stageSpeed,
              savingPath, saveRaw, name, 
              maxSec, DT ):
    """
    get raw data and resample!
    """
    #stream raw data to PC
    def rectest():
        global client
        print("Queue size is :",client.reply_q.qsize())
        client.cmd_q.put(ClientCommand(ClientCommand.RECEIVE))
    #depth of message queue.  
    #~2**16*100=6.25MB which is 1 second at 1.56Msamp dual channel, 16bit
    QUEUE_DEPTH=1e1
    SERVER_ADDR = '169.254.248.16',8900
    
    client = SocketClientThread(QUEUE_DEPTH)
    client.start()
    client.cmd_q.put(ClientCommand(ClientCommand.CONNECT, SERVER_ADDR))
    sleep(0.1)
    i=1
    jj=0
    
    running = False
    #handler loop
    sampling_rate = fs
    record_sec = maxSec #sec
    recordlength = int(sampling_rate*record_sec/16384)
    traceLength = int(16384) #229366  16384
    
    #predefine max. array
    index = np.ones(int(recordlength), dtype = np.dtype(np.int16))
    dataCH1 = np.ones(int(traceLength*recordlength), dtype = np.dtype(np.int16))
    dataCH2 = np.ones(int(traceLength*recordlength), dtype = np.dtype(np.int16))
    t1 = time()
    while jj <recordlength:
#        print('outer loop queue size is ', client.reply_q.qsize(), ' i is ',i)
        a=client.reply_q.get()
        if a.type==0:  #ERROR
            print(a.data)
            print("ERROR: qsize ",client.reply_q.qsize())

            client.cmd_q.put(ClientCommand(ClientCommand.CONNECT, SERVER_ADDR))
        if a.type==1:   #DATA
#            t=a.data['params']['timestamp']
            index[i] = a.data['params']['index']
            dataCH1[(i-1)*traceLength:i*traceLength] = a.data['bytes_data1'] 
        if a.type==2:  #MESSAGE
            print("MESSAGE: qsize ",client.reply_q.qsize())
        if running:
            dataCH2[(i-1)*traceLength:i*traceLength] = a.data['bytes_data2'] 
            if np.mean(dataCH1[(i-1)*traceLength:i*traceLength]) < 100:
                break
        if np.mean(dataCH1[(i-1)*traceLength:i*traceLength]) > 100:
            running = True
            i=i+1
            jj=jj+1
            if i >recordlength:
                break
    # rectest()
    print('time: ', time()-t1)
    client.cmd_q.put(ClientCommand(ClientCommand.CLOSE,SERVER_ADDR))
    
    if saveRaw:
        np.save(savingPath+r'/Npy/'+name+ r'Ch1_HeNe_raw.npy', dataCH1[:jj*traceLength])
        np.save(savingPath+r'/Npy/'+name+ r'Ch2_THz_raw.npy', dataCH2[:jj*traceLength])
        
    #resample zero corssing
    freq_hene = 2*stageSpeed*1e-3/RefLasWaveLen
    freq_0p3THZ = 2*stageSpeed*1e-3/1e-3    # 2*v/lambda
    freq_20THZ = 2*stageSpeed*1e-3/1.5e-5   # 2*v/lambda
    HeNefilter = butter_bandpass_filter(dataCH1[:jj*traceLength], freq_hene-freq_hene/5, freq_hene+freq_hene/5, fs)
    THzfilter = butter_bandpass_filter(dataCH2[:jj*traceLength], freq_0p3THZ, freq_20THZ, fs)
    
    #get zero crossings
    dd = 1
    ZC = ZeroCross(np.arange(0,dd*len(HeNefilter[::dd]), dd),HeNefilter)
    
    #interpolate THz signal
    dd = len(HeNefilter)//len(ZC)
    THzfunc = interp1d(np.arange(0,dd*len(THzfilter[::dd]), dd), THzfilter[::dd], kind = 'cubic')

    delay, ifg = np.linspace(0,len(ZC[2*dd:-2*dd:DT])*RefLasWaveLen/2*DT, len(ZC[2*dd:-2*dd:DT])), THzfunc(ZC[2*dd:-2*dd:DT])
    np.save(savingPath+r'/Npy/'+name+ r'run_ifg_delay.npy', delay)
    np.save(savingPath+r'/Npy/'+name+ r'run_ifg_sig.npy', ifg)
    print('proc finished')
    
#    queue.put('off')
#%% stage controll 
def runStage(startPoint, endPoint, speed):
    myxps       = XPS_C8_drivers.XPS()
    socketId    = myxps.TCP_ConnectToServer('192.168.254.254', 5001, 20)
    group       = 'Group1'
    positioner  = group + '.Pos'
    
    myxps.GroupInitialize(socketId,group)
    myxps.GroupHomeSearch(socketId,group)
    
    #go to start position
    myxps.GroupMoveAbort (socketId, 'Group1')
    myxps.PositionerSGammaParametersSet(socketId, positioner, 10, 80, 0.04, 0.04)
    myxps.GroupMoveAbsolute(socketId,positioner, [startPoint-20])
    print('Stage: reached starting point')
    
    #set FTIR speed settings
    myxps.PositionerSGammaParametersSet(socketId, positioner, speed, 20, 0.04, 0.04)
    
    #enable Trigger Output
    myxps.PositionerPositionCompareSet(socketId, positioner, startPoint, endPoint, 5)
    myxps.PositionerPositionCompareEnable(socketId, positioner)
    sleep(0.5)
    
    #move stage
    #myxps.PositionerPositionCompareDisable(socketId, positioner)
    print('Stage: start scanning')
    myxps.GroupMoveAbsolute(socketId,positioner, [endPoint+10]) 
    print('Stage: end scanning')
    
    myxps.PositionerPositionCompareDisable(socketId, positioner)
    sleep(0.5)
    
    #reset stage to initial position
    myxps.PositionerSGammaParametersSet(socketId, positioner, 10, 80, 0.04, 0.04)
    myxps.GroupMoveAbsolute(socketId,positioner, [startPoint-20])  
    print('Stage: back to starting position')
    myxps.TCP_CloseSocket(socketId)
    
    
#%% define resampling to Ref. Laser
from numba import jit
from scipy.signal import sosfiltfilt, cheby2

#define zero phase filter
def butter_lowpass(cutoff, fs, order=5):
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
    sos = cheby2(order, 20, normal_cutoff, btype='low', analog=False, output= 'sos')
    return sos
def butter_lowpass_filter(data, cutoff, fs, order=5):
    sos = butter_lowpass(cutoff, fs, order=order)
    y = sosfiltfilt(sos, data)
    return y

def butter_bandpass(lowcut, highcut, fs, order=5):
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    sos = cheby2(order, 20, [low, high], btype='band', output= 'sos')
    return sos
def butter_bandpass_filter(data, lowcut, highcut, fs, order=5):
    sos = butter_bandpass(lowcut, highcut, fs, order=order)
    y = sosfiltfilt(sos, data)
    return y
#%% find zero crossing NUMBA
@jit(nopython=True)
def ZeroCross(X, Y):
    ZZ = []
    ind = []
    kk = 5  # skipp 5 points after you found one zero corssing to be sure to not count twice
    for ii in range(len(Y)-1):
        if np.sign(Y[ii]) == 0 and kk >4:
            kk = 0
            ind.append(ii)
            zz = X[ii]
            ZZ.append(zz)
        elif  np.sign(Y[ii]) != np.sign(Y[ii+1]) and np.sign(Y[ii+1]) != 0 and kk >4:
            kk = 0
            ind.append(ii)
            zz = X[ii]-Y[ii]/(Y[ii+1]-Y[ii])*(X[ii+1]-X[ii])
            ZZ.append(zz)
        kk += 1
    return ZZ

        # DELAY   = np.load(savingPath+r'/Npy/'+name+ r'run_ifg_delay.npy')
        # IFG     = np.load(savingPath+r'/Npy/'+name+ r'run_ifg_sig.npy')
        
        # plt.figure('interferogram', figsize = (10,5))
        # plt.plot(DELAY*100, IFG)
        # plt.ylabel('Intensity (a.u.)')
        # plt.xlabel('Delay (cm)')
        # plt.savefig(savingPath+name+r"Summary_Interferogram.pdf", bbox_inches='tight')
    
        
        
        # zff         = 4
        # FRE         = np.fft.rfftfreq(int(2**(np.log2(len(DELAY))//1+zff)), laserWavelenght/2/299792458*DT)
        # FFT         = np.abs(np.fft.rfft(np.blackman(len(IFG))*IFG, int(2**(np.log2(len(IFG))//1+zff))))/np.sum(np.blackman(len(IFG)))
        # plt.figure('spectrum', figsize = (10,5))
        # plt.semilogy(FRE/1e12, FFT)
        # plt.xlim(1.5,4.5)
        # plt.ylim(1e-5*max(FFT), max(FFT)*1.2)
        # plt.ylabel('Intensity Spectrum (a.u.)')
        # plt.xlabel('Frequency (THz)')
        # plt.savefig(savingPath+name+r"Summary_Spectra_Log.pdf", bbox_inches='tight')
        # plt.show()
        
        # if p.is_alive():
        #     print("I'm alive!!!! do not kill me!!!!")
        #     p.kill()
        #     print('You are dead!!!')
        # if not p.is_alive():
        #     print('thread killed')

