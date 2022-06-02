import time
import sys
import numpy as np
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (QApplication, QCheckBox, QGridLayout, QGroupBox,
                             QMenu, QPushButton, QRadioButton, QVBoxLayout, QWidget, QSlider, QLabel, QDoubleSpinBox,QMainWindow)


from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas


from scipy.constants import e, hbar, h
sys.path.append(r'\\windata.ethz.ch\mesoqc\lab\meas\Paolo\Python\Analysis')
from my_plots import nice_colors
import os


class var():
    def __init__(self, label, v, fact = 1, unit = '', scale = 1):
        
        self.fact = fact
        self.unit = unit
        self.name = label
        self.v =v
        self.indx = len(self.v)-1
        
        self.update_step()
        
        self.val = self.v[self.indx]
        self.num_lbl =QLabel()
        self.num_lbl.setText('= %3.3f %s'%(self.val*self.fact, self.unit))
        self.lbl2save = ('%s_%3.3f_%s'%(self.name, self.val, self.unit)).replace(' ', '_').replace('.', 'p')
        
    def update_slider(self, x):
        
        self.val = self.v[x]
        self.indx = x
        self.num_lbl.setText('= %3.3f %s (%s)'%(self.val*self.fact, self.unit, self.name))

    def connect_slider(self, sld):
        self.slider = sld
    
    def update_slider_pos(self):
        self.slider.setValue(self.indx)
    
    def update_step(self):
        if len(self.v) >1:
            self.step= np.mean(np.diff(self.v))
        else:
            self.step=0

    def update_var(self, vec, update_slider = False):
        self.v= self.v[~np.isnan(self.v)]
        
        if  isinstance(vec, float) or isinstance(vec, int):
            if vec in self.v:
                self.indx =  int(np.argwhere(vec == self.v))
            else:  
                self.v = np.append(self.v, vec)
                self.slider.setMaximum(len(self.v)-1)
                self.indx =   len(self.v)-1
        else:
            self.v = vec
            self.slider.setMaximum(len(self.v)-1)
            self.indx = len(self.v)-1
            
        
        self.update_step()
        if len(self.v)==1:
            self.val = self.v[0]
        else:
            self.val =self.v[self.indx ]
        
        self.num_lbl.setText('= %3.3f %s (%s)'%(self.val*self.fact, self.unit, self.name))
        

        return 
 



class PlotSpec(QWidget):
    
    
    def __init__(self, I_V, f_lim, path, parent=None):
        super(PlotSpec, self).__init__(parent)
        self.init_var(I_V)
        

        outerLayout = QVBoxLayout()
        plotLayout = QVBoxLayout()
        button_layout = QVBoxLayout()


        grid_top = QGridLayout()
        
        self.path = path
        if self.path!=[]:
            
            self.button = QPushButton("Save")
            grid_top.addWidget(self.button, 0,0)
            self.button.clicked.connect(self.save)
        
        
        self.labelT = QLabel()
        grid_top.addWidget(self.labelT, 0,1)
       
        self.canvas = FigureCanvas(plt.Figure(figsize=(10, 10)))
        plotLayout.addWidget(self.canvas)
        
        self.init_plot(f_lim) 
        self.init_var(I_V) 
        
        
        grid = QGridLayout()
        grid.addWidget(self.slider([self.f_inj, self.P_inj, self.X], self.update_plot), 0, 0)
        
        

        self.timer = QTimer()   #start a timer to get process data
        self.timer.timeout.connect(self.measureT)
        #self.timer.setInterval(200)
        
        self.dataframe=0  #counter for number of data packets
        self.dataframeN=100
        self.LOST=0
        
        outerLayout.addLayout(grid_top)
        outerLayout.addLayout(button_layout)
        outerLayout.addLayout(plotLayout)
        outerLayout.addLayout(grid)
        
        self.dialogs = list()
        self.setLayout(outerLayout)
        
               
    def slider(self, var_list, action,  title = ''):
        
        groupBox = QGroupBox(title)
        vbox = QVBoxLayout()
        
        for var in var_list:
            sld = QSlider(Qt.Horizontal)
            sld.setFocusPolicy(Qt.StrongFocus)
            sld.setTickPosition(QSlider.TicksBothSides)
            sld.setTickInterval(1)
            sld.setSingleStep(1)
            sld.setValue(var.indx)

            sld.valueChanged[int].connect(var.update_slider)
            sld.valueChanged[int].connect(action)
            var.connect_slider(sld)
        
            label =QLabel()
            label.setText(var.name)
            Ggrid = QGridLayout()
            Ggrid.addWidget(var.num_lbl, 0,1)
            Ggrid.addWidget(label, 0,0)
            vbox.addLayout(Ggrid)
            vbox.addWidget(sld)

        vbox.addStretch(1)
        groupBox.setLayout(vbox)

        return groupBox
    

    
    
    def init_plot(self, f_lim):
        
        font = {
            'weight': 'normal',
            'size': 11
        }
        plt.rc('font', **font)
        
        self.ax = self.canvas.figure.subplots(nrows=2, ncols=1)
        
        self.ax[0].set_xlabel('delay (mm)')
        self.ax[0].set_ylabel('Intensity (a.u.)')
        self.line_ifg, = self.ax[0].plot([],[], color = 'tab:blue', label = 'IFG')

        
                
        self.ax[1].set_ylabel('Intensity (a.u.)')
        self.ax[1].set_xlabel('f (THz)')
        self.line_IF, = self.ax[1].plot([],[], label = '', color = 'tab:blue')
        self.f_lim = f_lim
        self.ax[1].set_xlim(self.f_lim)
                
    def update_plot(self):   
        
        # print('P: indx %d/%d, f: indx %d/%d, Cur: indx %d/%d'%(self.P_inj.indx+1,len(self.P_inj.v), self.f_inj.indx+1,len(self.f_inj.v),self.X.indx+1,len(self.X.v) ))
        # print('dimensions of x: %d,%d,%d'%(len(self.x), len(self.x[self.P_inj.indx]), len( self.x[self.P_inj.indx][self.f_inj.indx])) )

        # print('------------len checked--------------')
        x2plot= self.x[self.P_inj.indx][self.f_inj.indx][self.X.indx]
        I2plot= self.I[self.P_inj.indx][self.f_inj.indx][self.X.indx]
        f2plot= self.f[self.P_inj.indx][self.f_inj.indx][self.X.indx]
        If2plot= self.If[self.P_inj.indx][self.f_inj.indx][self.X.indx]
        
        self.line_ifg.set_data( x2plot ,  I2plot  )
        self.line_IF.set_data(  f2plot ,  If2plot  )
        self.ax[0].set_xlim([min(x2plot ), max(x2plot )])
        self.ax[0].set_ylim([min(I2plot ), max(I2plot )])
        self.ax[1].set_ylim([min(If2plot ), max(If2plot )])
        self.canvas.draw()
        plt.pause(0.01)


                        
    def init_var(self, I_V):
                
        self.x = []
        self.I = [] 
        self.f =  []   
        self.If = [] 
        
        unit_X = 'A'*(I_V == 'I')+ 'V'*(I_V == 'V')
        
        self.f_inj = var('f inj', np.array([np.nan]), unit = 'GHz', fact = 1)  #kHz      
        self.P_inj = var('P inj', np.array([np.nan]), unit = 'dBm', fact = 1)  #kHz      
        self.X = var(I_V, np.array([np.nan]), unit = unit_X, fact = 1)  #kHz      
        
        
    def  update_var(self,  param, key, xnew=[], Inew=[], fnew=[], Ifnew=[]):
        
        if key == 'P':
            self.P_inj.update_var(param)

            self.x.append([])
            self.I.append([])
            self.f.append([])     
            self.If.append([])

        elif key == 'f':
            self.f_inj.update_var(param)
            self.x[-1].append([])
            self.I[-1].append([])
            self.f[-1].append([])     
            self.If[-1].append([])

        elif key == 'I' or key =='V' or key == 'X':
            self.X.update_var(np.array(param))
            
            self.x[-1][-1]=list(xnew)
            self.I[-1][-1]=list(Inew)
            self.f[-1][-1]=list(fnew)
            self.If[-1][-1]=list(Ifnew)
            
            self.X.update_slider_pos()
            self.P_inj.update_slider_pos()
            self.f_inj.update_slider_pos()
            



        else:
            print('Unknown type of parameter!')
            return
            
                

            
    def save(self):
        if not os.path.exists(self.path):
                os.makedirs(self.path)
        plt.savefig(self.path + '/%s_%s_%s.pdf'%(self.f_inj.lbl2save, self.P_inj.lbl2save,self.X.lbl2save))
        
        
    def measureT():
        time.sleep(0.01)



class PlotsRun():
    
    def __init__(self, I_V, f_lim=[2,4], path=[]):

        self.app = QApplication(sys.argv)
        self.plotspec = PlotSpec(I_V, f_lim, path)
        self.plotspec.resize(1050,900)
        self.plotspec.show()
        self.app.processEvents()
        
        # self.app.exec_()    
        
    def update(self, param, key, xnew=[], Inew=[], fnew=[], Ifnew=[]):
        
        self.plotspec.update_var(param, key, xnew=xnew, Inew=Inew, fnew=fnew, Ifnew=Ifnew)
        self.app.processEvents()
        
    def hold(self):
        self.app.exec_()  
    
    def keep_active(self, timer = 0.001):
        while True:
            self.app.processEvents()
            time.sleep(timer)


        
        

if __name__ == '__main__':
    app = QApplication(sys.argv)
    myApp = PlotSpec('I', [2,4], [])
    myApp.resize(1050,900)
    myApp.show()
    sys.exit(app.exec_())