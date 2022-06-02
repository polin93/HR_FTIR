"""
Simple socket client thread sample.

Eli Bendersky (eliben@gmail.com)
This code is in the public domain
"""
import socket
import struct
import threading
import queue
import numpy as np
import time
import logging

import matplotlib as plt

class ClientCommand(object):
    """ A command to the client thread.
        Each command type has its associated data:

        CONNECT:    (host, port) tuple
        SEND:       Data string
        RECEIVE:    None
        CLOSE:      None
    """
    CONNECT, SEND, RECEIVE, CLOSE = range(4)

    def __init__(self, type, data=None):
        self.type = type
        self.data = data



class ClientReply(object):
    """ A reply from the client thread.
        Each reply type has its associated data:

        ERROR:      The error string
        DATA:    Depends on the command - for RECEIVE it's the received
                    data string, for others None.
        MESSAGE: Status message
    """
    ERROR, DATA, MESSAGE = range(3)

    def __init__(self, type, data=None):
        self.type = type
        self.data = data


class SocketClientThread(threading.Thread):
    """ Implements the threading.Thread interface (start, join, etc.) and
        can be controlled via the cmd_q queue attribute. Replies are placed in
        the reply_q queue attribute.
    """
    def __init__(self,QUEUE_DEPTH=100):
        super(SocketClientThread, self).__init__()
        cmd_q=queue.Queue()
        reply_q=queue.Queue(QUEUE_DEPTH)
        self.connected=0
        self.cmd_q = cmd_q
        self.reply_q = reply_q
        self.alive = threading.Event()
        self.alive.set()
        self.socket = None
        
        self.HEADER_SIZE=52  #default 52
        self.VERBOSE=0
        self.PLOT=0
        self.data_all_ch1=[]
        self.data_all_ch2=[]
        self.LOST=0
        self.tstart=time.time()
        self.NSAMP=1

        self.handlers = {
            ClientCommand.CONNECT: self._handle_CONNECT,
            ClientCommand.CLOSE: self._handle_CLOSE,
            ClientCommand.SEND: self._handle_SEND,
            ClientCommand.RECEIVE: self._handle_RECEIVE,
        }
        print("init")


    def run(self):   #part of threading; and gets run after start() is called
        while self.alive.isSet():
            if self.connected:
                #get data and put on reply_q
                self.handlers[ClientCommand(ClientCommand.RECEIVE).type](ClientCommand(ClientCommand.RECEIVE))
            else:
                time.sleep(0.1) ##if we're not connected, don't hog the CPU
            try:
                # queue.get with timeout to allow checking self.alive
                cmd = self.cmd_q.get(False)
                self.handlers[cmd.type](cmd) 
            except queue.Empty as e:
                continue

    def join(self, timeout=None):
        self.alive.clear()
        threading.Thread.join(self, timeout)

    def _handle_CONNECT(self, cmd):
        try:
            if self.connected==0:
                self.socket = socket.socket(
                    socket.AF_INET, socket.SOCK_STREAM)
                self.socket.connect((cmd.data[0], cmd.data[1]))
                self.reply_q.put(self._message_reply('Socket Connected'))
                print('handle_connect ### success')
                self.connected=1
            else:
                self.reply_q.put(self._message_reply('Socket Already Connected'))
                print('handle_connect socket already connected')
        except IOError as e:
            self.reply_q.put(self._error_reply(str(e)))
            self.connected=0

    def _handle_CLOSE(self, cmd):
        self.socket.close()
        reply = ClientReply(ClientReply.MESSAGE,'Socket Closed')
        self.connected=0

    def _handle_SEND(self, cmd):
        header = struct.pack('<L', len(cmd.data))
        try:
            self.socket.sendall(header + cmd.data)
            self.reply_q.put(self._message_reply())
        except IOError as e:
            self.reply_q.put(self._error_reply(str(e)))

    def _handle_RECEIVE(self, cmd):
        try:
            #alan
            bytes_data=[]
            tdataobj={}
            bytes_data = self._recvall(self.socket,self.HEADER_SIZE)
            if bytes_data!=b'':
                
                [header,index,lostrate,oscrate,buffsize,ch1_size,ch2_size,resolution]=struct.unpack('16sQQLLLLL',bytes_data[0:self.HEADER_SIZE])
#                print([header,index,lostrate,oscrate,buffsize,ch1_size,ch2_size,resolution])
                dt=np.dtype(np.int16) #int16
                
#                np.frombuffer(self._recvall(self.socket,8), dtype = dt)
                self._recvall(self.socket,8)
                
                bytes_data1=self._recvall(self.socket,ch1_size)
                
                if bytes_data1!=b'' and ch1_size != 0:  #recvall returns -1 when it fails
                    tdata = np.frombuffer(bytes_data1, dtype=dt) # from 16bit data to int16 
                    #print("I got data1... here's a taste:")
                    #print(tdata[:50])
                    tdataobj.update({'bytes_data1':tdata})
                    
                    bytes_data2=self._recvall(self.socket,ch2_size)
                    
                    
                    if bytes_data2!=b'':  #recvall returns -1 when it fails
                        tdata = np.frombuffer(bytes_data2, dtype=dt) # from 16bit data to int16 
                        tdataobj.update({'bytes_data2':tdata})
                        #print("I got data2... here's a taste:")
                        #print(tdata[:50])
                        
                        params={'header': header,'index':index,'lostrate':lostrate,
                        'oscrate':oscrate,'resolution':resolution,'ch1_size':ch1_size,
                        'ch2_size':ch2_size,'timestamp':time.time()}
                        tdataobj.update({'params':params})
                        
                        
                        self.reply_q.put(self._data_reply(tdataobj),block=True)
                        
                        return 0
                    else: #recvall of bytes_data2 has failed
                        print("recvall error buf 2")
                        self.reply_q.put(self._error_reply('Socket closed prematurely: recvall error buf 2'))
                else: #recvall of bytes_data1 has failed
#                    self._recvall(self.socket,8)
                    pass
                    #print("recvall error buf 1")
                    #self.reply_q.put(self._error_reply('Socket closed prematurely: recvall error buf 1'))
            else: #recvall of header has failed
                print("recvall error header")
                self.reply_q.put(self._error_reply('Socket closed prematurely: recvall error header'))
        except IOError as e:
            print("IOerror ")
            self.reply_q.put(self._error_reply("IOerror"))
            #/alan

    def _recvall(self,sock,n):
        # Helper function to recv n bytes or return None if EOF is hit
        tdata = bytearray()
        while len(tdata) < n:
            packet = sock.recv(n - len(tdata))
            if not packet:
                self.connected=0
                print("Exception:recvall sock error")
                self.reply_q.put(self._error_reply('Socket closed prematurely: recvall exception'))
                return -1
            tdata.extend(packet)
       
        return tdata
    
    def _recv_n_bytes(self, n):
        """ Convenience method for receiving exactly n bytes from self.socket
            (assuming it's open and connected).
        """
        data = ''
        while len(data) < n:
            chunk = self.socket.recv(n - len(data))
            if chunk == '':
                break
            data += chunk
        return data

    def _error_reply(self, errstr):
        return ClientReply(ClientReply.ERROR, errstr)

    def _message_reply(self, data=None):
        return ClientReply(ClientReply.MESSAGE, data)

    def _data_reply(self, data=None):
        return ClientReply(ClientReply.DATA, data)


#------------------------------------------------------------------------------
if __name__ == "__main__":
    import os, sys, time
    import queue
    import numpy as np
    from scipy.signal import detrend
    import matplotlib.pyplot as plt
    from rp_stream_threaded import SocketClientThread, ClientCommand, ClientReply

    #depth of message queue.  
    #~2**16*100=6.25MB which is 1 second at 1.56Msamp dual channel, 16bit
    QUEUE_DEPTH=1e1
    SERVER_ADDR = '169.254.248.16',8900
    NSAMP=10  #number of messages to use for data rate calcs
    LOST=0


    def rectest():
        global client
        print("Queue size is :",client.reply_q.qsize())
        client.cmd_q.put(ClientCommand(ClientCommand.RECEIVE))
    def pop(client):
        print("Queue size is :",client.reply_q.qsize())
        return client.reply_q.get()

    client = SocketClientThread(QUEUE_DEPTH)
    client.start()
    #CONNECT connects the socket, starts client.run(), and sets client.connected=1, which
    #run loop is continuous, and sends a constant stream of RECEIVE to fill up the buffer

    client.cmd_q.put(ClientCommand(ClientCommand.CONNECT, SERVER_ADDR))
        #    self.client.cmd_q.put(ClientCommand(ClientCommand.SEND, 'hello'))
        #    self.client.cmd_q.put(ClientCommand(ClientCommand.RECEIVE))
        #    self.client.cmd_q.put(ClientCommand(ClientCommand.CLOSE))
    time.sleep(0.1)
    tprev=0
    i=1
    jj=0
    
    running = False
    data = np.array([], dtype = np.dtype(np.int16))
    index = np.array([], dtype = np.dtype(np.int16))
    #handler loop
    sampling_rate = 1e6
    record_sec = 150 #sec
    recordlength = int(sampling_rate*record_sec/16384)
    traceLength = int(16384) #229366  16384
    
    data2 = np.ones(int(traceLength*recordlength), dtype = np.dtype(np.int16))
    data3 = np.ones(int(traceLength*recordlength), dtype = np.dtype(np.int16))
    print("theor. time: ", 1/1940000*traceLength*recordlength) #229366  16384
    t1 = time.time()
    while jj <recordlength:
        
#        print('outer loop queue size is ', client.reply_q.qsize(), ' i is ',i)
        a=client.reply_q.get()
        t=1
        if a.type==0:  #ERROR
            print(a.data)
            print("ERROR: qsize ",client.reply_q.qsize())

#            time.sleep(1)
            client.cmd_q.put(ClientCommand(ClientCommand.CONNECT, SERVER_ADDR))
        if a.type==1:   #DATA
            t=a.data['params']['timestamp']
            index = np.append(index, a.data['params']['index'])
#            data = np.append(data,a.data['bytes_data1'] )
            data2[(i-1)*traceLength:i*traceLength] = a.data['bytes_data1'] 
#            data2 = np.append(data2,a.data['bytes_data2'] )
#            if i==NSAMP:
#                print("qsize ",client.reply_q.qsize(),"data rate is ", NSAMP*2**16/(t-tprev)/1024/1024)  #MBytes/second
#                i=0
#                tprev=t
#                print(a.data['params'])

				#Handle Data HERE!!!!
        if a.type==2:  #MESSAGE
            print("MESSAGE: qsize ",client.reply_q.qsize())
#            print(a.data)
#        if i>50:  #error restart
        if running:
            data3[(i-1)*traceLength:i*traceLength] = a.data['bytes_data2'] 
            if np.mean(data2[(i-1)*traceLength:i*traceLength]) < 100:
                break
        if np.mean(data2[(i-1)*traceLength:i*traceLength]) > 100:
            running = True
            i=i+1
            jj=jj+1
            if i >recordlength:
                break
    rectest()
    print('time: ', time.time()-t1)
    client.cmd_q.put(ClientCommand(ClientCommand.CLOSE,SERVER_ADDR))
#            time.sleep(2)
#            client.cmd_q.put(ClientCommand(ClientCommand.CONNECT, SERVER_ADDR))
#            time.sleep(2)
#            i=0

    print(len(data)/(recordlength-1))
    print(np.mean(np.diff(index)) == 1)
    print(np.mean(np.diff(index)))
    #%%###########################################################################
    #GENERATE PATHS
    SavingPath =  r'Z:\lab\meas\AndresForrer\HiResFTIR\Test_Data/'
    from time import localtime, strftime
    h, t = os.path.split(SavingPath)
    SavingPath = os.path.join(h,strftime("%Y%m%d_%H%M_", localtime())+t)
    import os
    if not os.path.exists(SavingPath):
        os.makedirs(SavingPath)
        print('Path generated: ', SavingPath)

    np.save(SavingPath+r'/Ch1_HeNe.npy', data2[:jj*traceLength])
    np.save(SavingPath+r'/Ch2_THz.npy', data3[:jj*traceLength])
    freq = np.fft.rfftfreq((jj-4)*traceLength, 1/sampling_rate)
    plt.figure()
    plt.plot(freq, np.abs(np.fft.rfft(np.blackman(len(data2[(2)*traceLength:(jj-2)*traceLength]))*detrend(data2[(2)*traceLength:(jj-2)*traceLength]))))
    plt.semilogy(freq, np.abs(np.fft.rfft(np.blackman(len(data3[(2)*traceLength:(jj-2)*traceLength]))*detrend(data3[(2)*traceLength:(jj-2)*traceLength]))))
    plt.xlim(16e3, 23e3)
    plt.show()
#    plt.plot(np.abs(np.diff(index)))
#    plt.plot(data2)
#    plt.show()
    
    plt.figure()
    plt.plot(data2[:jj*traceLength])
    plt.plot(data3[:jj*traceLength])
    plt.show()