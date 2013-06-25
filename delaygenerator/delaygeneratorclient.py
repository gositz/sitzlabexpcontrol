from twisted.internet.defer import inlineCallbacks
from ab.abbase import getFloat
class DelayGeneratorClient:
    def __init__(self,protocol):        
        self.protocol = protocol

    def getDelays(self):
        return self.protocol.sendCommand('get-delays')
        
    def setDelay(self,dgName,delay):
        return self.protocol.sendCommand('set-delay',dgName,delay)

    def setDelayListener(self,listener):
        self.protocol.messageSubscribe('delay-changed',listener)

    def removePositionListener(self,listener = None):
        self.protocol.messageUnsubscribe('delay-changed',listener)

@inlineCallbacks
def main():
    from ab.abclient import getProtocol    
    from delaygeneratorserver import getConfig
    from ab.abbase import selectFromList
    serverConf, delayConf = getConfig()
    serverURL = serverConf["url"]
    protocol = yield getProtocol(serverURL)
    client = DelayGeneratorClient(protocol)
    
    delay = yield client.getDelays()
    dgNameList = delay.keys()
    dgNameList.append('Done')
    
    while True:
        delay = yield client.getDelays()
        print 'current settings:'
        for key,val in delay.items():
            print '\t %s: %s' % (key,val)
        
        dgToMod = yield selectFromList(dgNameList,"Which delay generator to adjust?")
        if dgToMod == "Done": break
        delayVal = yield getFloat(prompt="Enter a new delay (in ns):")
        client.setDelay(dgToMod,delayVal)

    print 'shutting down'
    reactor.stop()

if __name__ == '__main__':
    from twisted.internet import reactor
    main()
    reactor.run()