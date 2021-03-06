'''
by stevens4. last mod: 2013/09/30

updated to allow for 'run all' command; config file now has a default delay 'delay'

updated to meet new configuration standard where ../config/delaygenerator.py has a
dictionary of all the required parameters

constructs a server to manage multiple delay generator objects. the objects are stored
in a dictionary with the key set to the NAME option under delayGeneratorServerConfig.ini.
each is an instance of a DelayGenerator object that handles the communication via USB to the
physical delay generator.

'''

from delaygenerator import DelayGenerator, FakeDelayGenerator

from functools import partial

from ab.abserver import BaseWAMP, command, runServer
from ab.abbase import getDigit, selectFromList, sleep

from twisted.internet.defer  import Deferred, inlineCallbacks, returnValue
from twisted.internet  import reactor
from twisted.internet.task import LoopingCall

import pprint

from config.delaygenerator import DG_CONFIG, DEBUG_DG_CONFIG
from config.serverURLs import DELAY_GENERATOR_SERVER, TEST_DELAY_GENERATOR_SERVER

from sitz import compose, printDict #, DELAY_GENERATOR_SERVER, TEST_DELAY_GENERATOR_SERVER

import os.path


dgDict = {}

import sys
print sys.argv
DEBUG = len(sys.argv) > 1 and 'debug' in sys.argv
AUTORUN = len(sys.argv) > 1 and 'auto' in sys.argv
LOCAL = len(sys.argv) > 1 and 'local' in sys.argv
print 'debug: %s' % DEBUG
print 'autorun: %s' % AUTORUN
print 'local: %s' % LOCAL



MIN = 0
MAX = 104857600 #(2^20)*100ns

'''
def addDelayGenerator(options):
    return DelayGenerator(options["usb_chan"])
    '''


class DelayGeneratorWAMP(BaseWAMP):
    __wampname__ = 'delay generator server'
    MESSAGES = {
        'delay-changed':'notify when delay changes',
        'delay-change-failed':'error flag thrown if delay failed'
    }

    def initializeWAMP(self):
        self.dgDict = dgDict
        self.dgOptions = DG_CONFIG if not DEBUG else DEBUG_DG_CONFIG
        BaseWAMP.initializeWAMP(self)
    
    @command('get-delay','query delay of SPECIFIC delay generator and return dict')
    def getDelay(self,name):
        return dgDict[name].getDelay()
    
    @command('get-delays','query delay of ALL delay generators and return dict')
    def getDelays(self):
        return {name:dg.getDelay() for name,dg in self.dgDict.items()}

    @command('set-delay','set delay of specified delay generator')
    def setDelay(self,dgName,delay):
        failError = ''
        success = True
        
        #test delay isn't outside bounds either <0 or >20bits
        if delay < MIN or delay > MAX: 
            success = False
            failError = 'delay out of bounds'
            self.dispatch('delay-change-failed',(dgName,failError))

        #test delay generator is actually running
        if dgName not in self.dgDict.keys():
            success = False
            failError = 'requested delay generator not running'
            self.dispatch('delay-change-failed',(dgName,failError))
        
        #if it passed these tests, try to set the delay
        if success: 
            success = self.dgDict[dgName].setDelay(delay)
        
        #if it actually worked, send a message and update config
        if success: 
            self.dispatch('delay-changed',(dgName,delay))
            self.updateConfig()
            
        #if setting the delay STILL failed, throw fail message
        if not success: 
            failError = "could not set delay: unknown error"
            self.dispatch('delay-change-failed',(dgName,failError))
        
        return success
        
    @command('enable-partner','set whether or not to partner delays')
    def enablePartner(self,dgName,isEnabled):
        self.dgDict[dgName].partneringEnabled = isEnabled
        # partnerName = self.dgOptions[dgName]['partner']
        # if partnerName is not None:
            # self.dgDict[partnerName].partneringEnabled = isEnabled

    @command('set-partnered-delay','set delay of a channel AND its partner')
    def setPartnerDelay(self,dgName,delay):
        if self.dgOptions[dgName]['partner'] is not None  \
            and self.dgDict[dgName].partneringEnabled is True:
                succeed = self.setDelay(dgName,delay)
                if not succeed: return
                #if didn't fail on first delay, try setting partner
                partnerName = self.dgOptions[dgName]['partner']
                relativeDelay = self.dgOptions[dgName]['rel_part_delay']
                delayForPartner = delay + relativeDelay
                succeed = self.setDelay(partnerName,int(delayForPartner))

        if self.dgOptions[dgName]['partner'] is None  \
            or  self.dgDict[dgName].partneringEnabled is False:
                print 'no partner exists for this channel! setting only requested delay'
                succeed = self.setDelay(dgName,delay)
        
        return succeed
        
    def updateConfig(self):
        #writes all delay generators' delays to a file in config/ for reference
        lastConfName=os.path.abspath('../config/lastDelayConfigDEBUG.txt') if DEBUG else os.path.abspath('../config/lastDelayConfig.txt')
        confFile = open(lastConfName,'w')
        for name, dg in self.dgDict.items():
            confFile.write(name+' '+str(dg.getDelay())+'\n')
        confFile.close()
        

def createDelayGenerator(name,dgOptions,dgDictionary):
    #if name == "Done" or name == "Run All":
    #   return dgDictionary
    if DEBUG:
        dgDictionary[name] = FakeDelayGenerator(dgOptions)
        print 'created: ' + name + ' with a delay of ' + str(dgOptions['delay']) + ' on fake com port\n\n'
    else:
        dgDictionary[name] = DelayGenerator(dgOptions)
        print 'created: ' + name + ' with a delay of ' + str(dgOptions['delay']) + ' on ' + str(dgDictionary[name].COMPort) +'\n\n'
    return dgDictionary
    
@inlineCallbacks
def main():
    url = DELAY_GENERATOR_SERVER if not LOCAL else TEST_DELAY_GENERATOR_SERVER
    dgOptions = DG_CONFIG if not DEBUG else DEBUG_DG_CONFIG
    print '\n\n\n'

    printDict(dgOptions)
    
    configList = dgOptions.keys()
    if type(configList) is not list: configList = [configList] #if it is only 1 element, convert to list
    configList += ["Run All"]
    configList += ["Done"]

    while True:
        print '\n\n\n'
        if AUTORUN:
            dgToAdd = "Run All"
        else:
            dgToAdd = yield selectFromList(configList,"Which delay generator to add?")
        
        if dgToAdd == "Done" or len(configList) <= 0: break
        if dgToAdd == "Run All":
            configList.remove("Done")
            configList.remove("Run All")
            for thisDG in configList:
                try:
                    if dgOptions[thisDG]['run_by_default']: 
                        dgDict.update(createDelayGenerator(thisDG,dgOptions[thisDG],dgDict))
                except:
                    print 'failed to create ' + thisDG
            break
        elif dgToAdd in configList:
            print dgToAdd
            print dgOptions[dgToAdd]
            dgDict.update(createDelayGenerator(dgToAdd,dgOptions[dgToAdd],dgDict))
            configList.remove(dgToAdd)

    #confirm config doesn't have a conflict in the partnered delays. safety concern for lasers!
    for dg in dgDict.keys():
        partnerName = dgOptions[dg]['partner']
        if partnerName is None: continue
        partnerDefault = dgOptions[partnerName]['delay']
        partnerRelative = dgOptions[dg]['delay'] + dgOptions[dg]['rel_part_delay']
        if partnerDefault != partnerRelative:
            print 'your config file has a conflict in the default delay and relative delay for ' +str(dg)+' and '+str(partnerName)
            print str(partnerDefault) + '   ' + str(partnerRelative)
            print 'get yo shit together \n\n\n'
            sys.exit()
    
    runServer(
        WAMP = DelayGeneratorWAMP,
        URL = url,
        debug = True,
        outputToConsole=True
    )
    
if __name__ == '__main__':
    main()
    reactor.run()
