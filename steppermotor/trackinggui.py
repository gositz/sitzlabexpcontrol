## BOILERPLATE ##
import sys
from PySide import QtGui, QtCore
if QtCore.QCoreApplication.instance() is None:    
    app = QtGui.QApplication(sys.argv)
    import qt4reactor
    qt4reactor.install()
## BOILERPLATE ##
from goto import MIN, MAX, PRECISION, SLIDER, POI, GotoWidget
from config.steppermotor import PDL, KDP, BBO, SM_CONFIG, REMPI_POI
from qtutils.dictcombobox import DictComboBox
from qtutils.toggle import ToggleObject, ToggleWidget
from qtutils.label import LabelWidget
from qtutils.qled import LEDWidget
from steppermotorclient import StepperMotorClient
from twisted.internet.defer import inlineCallbacks
from functools import partial
from config.serverURLs import WAVELENGTH_SERVER, TEST_WAVELENGTH_SERVER, STEPPER_MOTOR_SERVER, TEST_STEPPER_MOTOR_SERVER
from sitz import compose

CRYSTALS = {
    id: SM_CONFIG[id]['name'] for id in (KDP,BBO)
}

class TrackingWidget(QtGui.QWidget):
    def __init__(self,wavelengthProtocol,stepperMotorProtocol):
        QtGui.QWidget.__init__(self)
        
        self.setLayout(QtGui.QVBoxLayout())

        ##########
        ## goto ##
        ##########
        
        gotoWidget = GotoWidget(
            {
                MIN:24100,
                MAX:24800,
                PRECISION:2,
                SLIDER:2.0,
                POI:REMPI_POI
            }
        )
        self.layout().addWidget(gotoWidget)

        # send command to tracking server when goto requested
        @inlineCallbacks
        def onGotoRequested(payload):
            position, deferred = payload
            yield wavelengthProtocol.sendCommand('set-wavelength',position)
            deferred.callback(None)
        gotoWidget.gotoRequested.connect(onGotoRequested)

        # handle update requests (should the position fall out of sync)
        def onUpdateReqested():
            wavelengthProtocol.sendCommand('get-wavelength').addCallback(gotoWidget.setPosition)
        gotoWidget.updateRequested.connect(onUpdateReqested)
        
        # send cancel request when goto widget requests
        gotoWidget.cancelRequested.connect(partial(wavelengthProtocol.sendCommand,'cancel-wavelength-set'))
        
        # set goto widget position on pdl position change
        StepperMotorClient(stepperMotorProtocol,PDL).addListener(
            StepperMotorClient.POSITION,
            lambda _:wavelengthProtocol.sendCommand('get-wavelength').addCallback(gotoWidget.setPosition)
        )
        
        # initialize position of goto widget
        wavelengthProtocol.sendCommand('get-wavelength').addCallback(gotoWidget.setPosition)    
        
        # this bit below is for a future hardware change where the pdl sm is on a relay
        # disable the goto widget until the pdl is enabled
        # gotoWidget.setEnabled(False)
        # def toggleGoto(status):
            # if status == 'enabled': 
                # gotoWidget.setEnabled(True)
            # elif status == 'disabled': 
                # gotoWidget.setEnabled(False)
        # StepperMotorClient(stepperMotorProtocol,PDL).addListener(StepperMotorClient.ENABLE,toggleGoto)
                
        #########################
        ## crystal calibration ##
        #########################

        tuningGB = QtGui.QGroupBox('tune crystal')
        tuningLayout = QtGui.QHBoxLayout()
        tuningGB.setLayout(tuningLayout)

        # button to tune calibration #
        
        def calibKDP():
            wavelengthProtocol.sendCommand('calibrate-crystal',KDP)
        tuningButtonKDP = QtGui.QPushButton('KDP tuned')
        tuningLayout.addWidget(tuningButtonKDP)
        tuningButtonKDP.clicked.connect(calibKDP)
        # tuningButtonKDP.setEnabled(False)
        # def toggleKDP(status):
            # if status == 'enabled': 
                # tuningButtonKDP.setEnabled(True)
            # elif status == 'disabled': 
                # tuningButtonKDP.setEnabled(False)
        # StepperMotorClient(stepperMotorProtocol,KDP).addListener(StepperMotorClient.ENABLE,toggleKDP)
        
        
        def calibBBO():
            wavelengthProtocol.sendCommand('calibrate-crystal',BBO)
        tuningButtonBBO = QtGui.QPushButton('BBO tuned')
        tuningLayout.addWidget(tuningButtonBBO)
        tuningButtonBBO.clicked.connect(calibBBO)
        # tuningButtonBBO.setEnabled(False)
        # def toggleBBO(status):
            # if status == 'enabled': 
                # tuningButtonBBO.setEnabled(True)
            # elif status == 'disabled': 
                # tuningButtonBBO.setEnabled(False)
        # StepperMotorClient(stepperMotorProtocol,BBO).addListener(StepperMotorClient.ENABLE,toggleBBO)
        

        
        self.layout().addWidget(LabelWidget('tuning',tuningLayout))

        #####################
        ## tracking toggle ##
        #####################

        toggleLayout = QtGui.QHBoxLayout()        

        toggle = ToggleObject()

        # toggle tracking server on toggle request
        toggle.toggleRequested.connect(
            partial(
                wavelengthProtocol.sendCommand,
                'toggle-tracking'
            )
        )

        # toggle widget upon receipt of tracking change server notification
        wavelengthProtocol.messageSubscribe(
            'tracking-changed',
            lambda _:toggle.toggle()
        )

        # create toggle widget
        toggleLayout.addWidget(ToggleWidget(toggle,('track','stop')),1)        

        # have pretty light
        led = LEDWidget()
        toggle.toggled.connect(led.toggle)

        toggleLayout.addWidget(led)

        self.layout().addWidget(LabelWidget('tracking',toggleLayout))

        # init tracking toggle
        def initTracking(tracking):
            if tracking: toggle.toggle()            
        wavelengthProtocol.sendCommand('is-tracking').addCallback(initTracking)
    
    def closeEvent(self, event):
        event.accept()
        quit()
        
@inlineCallbacks
def main():
    import sys
    from ab.abclient import getProtocol
    DEBUG = len(sys.argv) > 1 and sys.argv[1] == 'debug'
    wavelengthProtocol = yield getProtocol(
        TEST_WAVELENGTH_SERVER if DEBUG else WAVELENGTH_SERVER
    )
    stepperMotorProtocol = yield getProtocol(
        TEST_STEPPER_MOTOR_SERVER if DEBUG else STEPPER_MOTOR_SERVER
    )
    #memory management nonsense
    trackingWidget = TrackingWidget(wavelengthProtocol,stepperMotorProtocol)
    container.append(trackingWidget)
    container[0].show()
    trackingWidget.setWindowTitle('tracking client')

if __name__ == '__main__':
    from twisted.internet import reactor
    container = []
    main()
    reactor.run()
