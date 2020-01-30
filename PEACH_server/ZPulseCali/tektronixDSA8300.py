# Copyright (C) 2010 Daniel Sank & Julian Kelly
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
### BEGIN NODE INFO
[info]
name = Tektronix TDS 5054B-NV Oscilloscope
version = 0.1
description = Talks to the Tektronix 5054B oscilloscope

[startup]
cmdline = %PYTHON% %FILE%
timeout = 20

[shutdown]
message = 987654321
timeout = 20
### END NODE INFO
"""



from labrad import types as T, util
from labrad.server import setting
from labrad.gpib import GPIBManagedServer, GPIBDeviceWrapper
from twisted.internet.defer import inlineCallbacks, returnValue
from labrad.types import Value
from struct import unpack, calcsize

import numpy, re

COUPLINGS = ['AC', 'DC', 'GND']
TRIG_CHANNELS = ['AUX','CH1','CH2','CH3','CH4','LINE']
VERT_DIVISIONS = 10.0
HORZ_DIVISIONS = 10.0
SCALES = []

class TektronixDPO72304DXWrapper(GPIBDeviceWrapper):
    pass

class Tektronix72304DXServer(GPIBManagedServer):
    name = 'sampling scope1'
    deviceName = 'TEKTRONIX DSA8300'
    deviceWrapper = TektronixDPO72304DXWrapper
        
    @setting(11, returns=[])
    def reset(self, c):
        dev = self.selectedDevice(c)
        yield dev.write('*RST')
        # TODO wait for reset to complete

    @setting(12, returns=[])
    def clear_buffers(self, c):
        dev = self.selectedDevice(c)
        yield dev.write('*CLS')

    #Channel settings
    @setting(21, channel = 'i', returns = '(vsvvssss)')
    def channel_info(self, c, channel):
        """channel(int channel)
        Get information on one of the scope channels.

        OUTPUT
        Tuple of (probeAtten, ?, scale, position, coupling, bwLimit, invert, units)
        """
        #NOTES
        #The scope's response to 'CH<x>?' is a string of format
        #'1.0E1;1.0E1;2.5E1;0.0E0;DC;OFF;OFF;"V"'
        #These strings represent respectively,
        #probeAttenuation;?;?;vertPosition;coupling;?;?;vertUnit

        dev = self.selectedDevice(c)
        resp = yield dev.query('CH%d?' %channel)
        probeAtten, iDontKnow, scale, position, coupling, bwLimit, invert, unit = resp.split(';')

        #Convert strings to numerical data when appropriate
        probeAtten = T.Value(float(probeAtten),'')
        #iDontKnow = None, I don't know what this is!
        scale = T.Value(float(scale),'')
        position = T.Value(float(position),'')
        coupling = coupling
        bwLimit = bwLimit
        invert = invert
        unit = unit[1:-1] #Get's rid of an extra set of quotation marks

        returnValue((probeAtten,iDontKnow,scale,position,coupling,bwLimit,invert,unit))

    @setting(22, channel = 'i', coupling = 's', returns=['s'])
    def coupling(self, c, channel, coupling = None):
        """Get or set the coupling of a specified channel
        Coupling can be "AC" or "DC"
        """
        dev = self.selectedDevice(c)
        if coupling is None:
            resp = yield dev.query('CH%d:COUP?' %channel)
        else:
            coupling = coupling.upper()
            if coupling not in COUPLINGS:
                raise Exception('Coupling must be "AC" or "DC"')
            else:
                yield dev.write(('CH%d:COUP '+coupling) %channel)
                resp = yield dev.query('CH%d:COUP?' %channel)
        returnValue(resp)

    @setting(23, channel = 'i', scale = 'v', returns = ['v'])
    def scale(self, c, channel, scale = None):
        """Get or set the vertical scale of a channel
        """
        dev = self.selectedDevice(c)
        if scale is None:
            resp = yield dev.query('CH%d:SCA?' %channel)
        else:
            scale = format(scale,'E')
            yield dev.write(('CH%d:SCA '+scale) %channel)
            resp = yield dev.query('CH%d:SCA?' %channel)
        scale = float(resp)
        returnValue(scale)

    @setting(24, channel = 'i', factor = 'i', returns = ['s'])
    def probe(self, c, channel, factor = None):
        """Get or set the probe attenuation factor.
        """
        probeFactors = [1,10,20,50,100,500,1000]
        dev = self.selectedDevice(c)
        chString = 'CH%d:' %channel
        if factor is None:
            resp = yield dev.query(chString+'PRO?')
        elif factor in probeFactors:
            yield dev.write(chString+'PRO %d' %factor)
            resp = yield dev.query(chString+'PRO?')
        else:
            raise Exception('Probe attenuation factor not in '+str(probeFactors))
        returnValue(resp)

    @setting(25, channel = 'i', state = '?', returns = '')
    def channelOnOff(self, c, channel, state):
        """Turn on or off a scope channel display
        """
        dev = self.selectedDevice(c)
        if isinstance(state, str):
            state = state.upper()
        if state not in [0,1,'ON','OFF']:
            raise Exception('state must be 0, 1, "ON", or "OFF"')
        if isinstance(state, int):
            state = str(state)
        yield dev.write(('SEL:CH%d '+state) %channel)            
        
    
    #Data acquisition settings
    @setting(201, channel = 'i', start = 'i', stop = 'i', returns='*v[ns] {time axis} *v[mV] {scope trace}')
    def get_trace(self, c, channel, start=1, stop=5000):
        """Get a trace from the scope.
        OUTPUT - (array voltage in volts, array time in seconds)
        """
##        DATA ENCODINGS
##        RIB - signed, MSB first
##        RPB - unsigned, MSB first
##        SRI - signed, LSB first
##        SRP - unsigned, LSB first
        wordLength = 4 #Hardcoding to set data transer word length to 2 bytes
        recordLength = stop-start+1
        
        dev = self.selectedDevice(c)
        #DAT:SOU - set waveform source channel
        yield dev.write('DAT:SOU CH%d' %channel)
        print '11111111'
        #DAT:ENC - data format (binary/ascii)
        yield dev.write('DAT:ENC RIB')
        #Set number of bytes per point
        yield dev.write('DAT:WID %d' %wordLength)
        print '222222'
        #Starting and stopping point
        yield dev.write('DAT:STAR %d' %start)
        yield dev.write('DAT:STOP %d' %stop)
        print '333333333'
        #Transfer waveform preamble
        
        position = yield dev.query('CH%d:POSITION?' %channel) # in units of divisions
        position = position.strip().split(' ')[0]
        #Transfer waveform data
        binary = yield dev.query('CURV?')
        
        #Parse waveform preamble
        # preamble = yield dev.query('WFMO?')
        # voltsPerDiv, secPerDiv, voltUnits, timeUnits = _parsePreambleWFMO(preamble)
        # print voltsPerDiv, secPerDiv, voltUnits, timeUnits
        
        voltsPerDiv = yield dev.query('CH%d:SCA?'%channel)
        voltsPerDiv = float(voltsPerDiv.strip()[voltsPerDiv.index('SCALE')+5:])
        secPerDiv = yield dev.query('HOR:MAI:SCA?')
        secPerDiv = float(secPerDiv.strip()[secPerDiv.index('SCALE')+5:])
        voltUnits = 'V'
        timeUnits = 's'
        
        voltUnitScaler = Value(1, voltUnits)['mV'] # converts the units out of the scope to mV
        timeUnitScaler = Value(1, timeUnits)['ns']
        #Parse binary
        # trace = _parseBinaryData(binary,wordLength = wordLength)
        print 'trace: ',trace[:20]
        trace = numpy.fromstring(binary[13:-1],dtype='<u4')
        #Convert from binary to volts
        traceVolts = (trace * (1/2.**31) * VERT_DIVISIONS/2 * voltsPerDiv - float(position) * voltsPerDiv) * voltUnitScaler
        time = numpy.linspace(0, HORZ_DIVISIONS * secPerDiv * timeUnitScaler,len(traceVolts))#recordLength)

        returnValue((time, traceVolts))

def _parsePreamble(preamble):
    ###TODO: parse the rest of the preamble and return the results as a useful dictionary
    preamble = preamble.split(';')
    vertInfo = preamble[5].split(',')
    
    def parseString(string): # use 'regular expressions' to parse the string
        number = re.sub(r'.*?([\d\.]+).*', r'\1', string)
        units = re.sub(r'.*?([a-zA-z]+)/.*', r'\1', string)
        return float(number), units
    
    voltsPerDiv, voltUnits = parseString(vertInfo[2])
    if voltUnits == 'VV':
        voltUnits ='W'
    if voltUnits == 'mVV':
        voltUnits = 'W'
    if voltUnits == 'uVV':
        voltUnits = 'W'
    if voltUnits == 'nVV':
        voltUnits = 'W'
    secPerDiv, timeUnits = parseString(vertInfo[3])
    return (voltsPerDiv, secPerDiv, voltUnits, timeUnits)
    
def _parsePreambleWFMO(preamble):
    ###TODO: parse the rest of the preamble and return the results as a useful dictionary
    preamble = preamble.split(';')
    vertInfo = preamble[-2].split(',')[1:3]
    yunits = ['mV','uV','nV','V']
    for idx, yuni in enumerate(yunits):
        if yuni in vertInfo[0]:
            voltsPerDiv = float(vertInfo[0][:vertInfo[0].index(yuni)])
            voltUnits = vertInfo[0][vertInfo[0].index(yuni):vertInfo[0].index('/div')]
            break
    xunits = ['ns','us','ms','s']
    for idx, xuni in enumerate(xunits):
        if xuni in vertInfo[1]:
            secPerDiv = float(vertInfo[1][:vertInfo[1].index(xuni)])
            timeUnits = vertInfo[1][vertInfo[1].index(xuni):vertInfo[1].index('/div')]
            break
    return (voltsPerDiv, secPerDiv, voltUnits, timeUnits)

def _parseBinaryData(data, wordLength):
    """Parse binary data packed as string of RIBinary
    """
    formatChars = {'1':'b','2':'h', '4':'f'}
    formatChar = formatChars[str(wordLength)]

    #Get rid of header crap
    #unpack binary data
    if wordLength == 1:
        dat = numpy.array(unpack(formatChar*(len(dat)/wordLength),dat))
    elif wordLength == 2:
        dat = data[(int(data[1])+2):]
        dat = dat[-calcsize('>' + formatChar*(len(dat)/wordLength)):]
        dat = numpy.array(unpack('>' + formatChar*(len(dat)/wordLength),dat))
    elif wordLength == 4:
        dat = data[(int(data[1])+2):]
        dat = dat[-calcsize('>' + formatChar*(len(dat)/wordLength)):]
        dat = numpy.array(unpack('>' + formatChar*(len(dat)/wordLength),dat))      
    return dat

__server__ = Tektronix72304DXServer()

if __name__ == '__main__':
    from labrad import util
    util.runServer(__server__)
