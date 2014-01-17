from steppermotor import StepperMotor, FakeStepperMotor
from ab.abserver import BaseWAMP, command, runServer
from twisted.internet.defer  import Deferred, inlineCallbacks, returnValue
from twisted.internet  import reactor
from sitz import readConfigFile, STEPPER_MOTOR_SERVER, TEST_STEPPER_MOTOR_SERVER
from functools import partial
from ab.abbase import sleep
import sys
from os import path
from config.steppermotor import SM_CONFIG

DEBUG = len(sys.argv) > 1 and sys.argv[1] == 'debug'
    
class StepperMotorWAMP(BaseWAMP):
    
    UPDATE = .1 # duration between position notifications
    __wampname__ = 'stepper motor server'
    MESSAGES = {
        'position-changed':'notify when position changes',
        'step-rate-changed':'notify when stepping rate changes'
    }

    def initializeWAMP(self):
        config = self.config = SM_CONFIG
        ## construct a dictionary of steppermotor objects
        self.sms = {}
        for id, options in config.items():
            if DEBUG:
                self.sms[id] = FakeStepperMotor( 
                    options['pulse_channel'],
                    options['direction_channel'],
                    options['counter_channel'],
                    int(options['backlash'])
                )
            else:
                print id
                self.sms[id] = StepperMotor(
                    options['pulse_channel'],
                    options['direction_channel'],
                    options['counter_channel'],
                    int(options['backlash'])
                )
        '''
        self.sms = {
            id:(
                StepperMotor if not DEBUG else FakeStepperMotor
            )(
                *(
                    (
                        options['pulse_channel'],
                        options['counter_channel'],
                        options['direction_channel'],
                        options['step_rate'],
                        int(options['initial_position']),
                        int(options['backlash'])
                    ) if not DEBUG else tuple([])
                )
            ) for id, options in config.items()
        }
        '''
        ## complete initialization
        BaseWAMP.initializeWAMP(self)

    @command('get-position','query position of stepper motor')
    def getPosition(self,sm):
        return self.sms[sm].getPosition()

    @command('set-position','set position of stepper motor')
    @inlineCallbacks
    def setPosition(self,sm,position):
        ## initialize deferred that will fire at end of stepping journey
        d = Deferred()
        ## function that is called periodically to update listeners on journey progress
        done = False
        def loop(_):
            self.dispatch(
                'position-changed',
                (
                    sm,
                    self.getPosition(sm)
                )
            )
            if not done:
                sleep(self.UPDATE).addCallback(loop)
        ## start journey
        self.sms[sm].setPosition(position,partial(d.callback,None))
        ## start updates
        loop(None)
        ## wait until journey done
        yield d
        done = True
        ## return ending position
        returnValue(self.getPosition(sm))

    @command('set-step-rate')
    def setStepRate(self,sm,stepRate):
        self.sms[sm].setStepRate(stepRate)
        self.dispatch(
            'step-rate-changed',
            (
                sm,
                stepRate
            )
        )

    @command('get-step-rate')
    def getStepRate(self,sm):
        return self.sms[sm].getStepRate()

    @command('get-configuration','retrieve dictionary of sm server configuration')
    def getConfig(self):
        return self.config

def main():
    runServer(WAMP = StepperMotorWAMP, URL = STEPPER_MOTOR_SERVER if not DEBUG else TEST_STEPPER_MOTOR_SERVER,debug = False,outputToConsole=True)
if __name__ == '__main__':
    main()
    reactor.run()
