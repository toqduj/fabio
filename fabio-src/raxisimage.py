#!/usr/bin/env python
#coding: utf8

# We hope it will be relatively easy to add new file formats to fabio in the future. The basic idea is the following:
#
# 8) Upload a testimage to the file release system and create a unittest testcase
#    which opens an example of your new format, confirming the image has actually
#    been read in successfully (eg check the mean, max, min and esd are all correct,
#    perhaps orientation too)
#
# 9) Run pylint on your code and then please go clean it up. Have a go at mine while you are at it.
#
#10) Bask in the warm glow of appreciation when someone unexpectedly learns they don't need to convert
#    their data into another format

# Get ready for python3:
from __future__ import with_statement, print_function
__doc__ = """

Authors: Brian R. Pauw
email:  brian@stack.nl

Written using information gleaned from the ReadRAXISImage program 
written by T. L. Hendrixson, made available by Rigaku Americas. 
Available at: http://www.rigaku.com/downloads/software/readimage.html


"""
__authors__ = ["Brian R. Pauw"]
__contact__ = "brian@stack.nl"
__license__ = "GPLv3+"
__copyright__ = ""
__version__ = "23 Nov 2013"

import numpy, logging, struct
from fabioimage import fabioimage
logger = logging.getLogger("templateimage")


class raxisimage(fabioimage):
    """
    FabIO image class to read Rigaku RAXIS image files. 
    Write functions are not planned as there are plenty of more suitable
    file formats available for storing detector data.
    In particular, the MSB used in Rigaku files is used in an uncommon way: 
    it is used as a *multiply-by* flag rather than a normal image value bit. 
    While it is said to multiply by the value specified in the header, there
    is at least one case where this is found not to hold, so YMMV and be careful.

    """
    def __init__(self, *arg, **kwargs):
        """
        Generic constructor
        """
        fabioimage.__init__(self, *arg, **kwargs)
        self.data = None
        self.header = {}
        self.dim1 = self.dim2 = 0
        self.m = self.maxval = self.stddev = self.minval = None
        self.header_keys = self.header.keys()
        self.bytecode = 'uint16' #same for all RAXIS images AFAICT
        self.endianness = '>' #this may be tested for.

    def swap_needed(self):
        """not sure if this function is needed"""
        endian=self.endianness
        #Decide if we need to byteswap
        if (endian == '<' and numpy.little_endian) or (endian == '>' and not numpy.little_endian):
            return False
        if (endian == '>' and numpy.little_endian) or (endian == '<' and not numpy.little_endian):
            return True


    def _readheader(self, infile):
        """
        Read and decode the header of a Rigaku RAXIS image. 
        The Rigaku format uses a block of (at least) 1400 bytes for storing
        information. The information has a fixed structure, but endianness
        can be flipped for non-char values. Header items which are not 
        capitalised form part of a non-standardized data block and may not
        be accurate. 
        
        TODO: It would be useful to have an automatic endianness test in here. 
        
        @param infile: Opened python file (can be stringIO or bipped file)  
        """
        endianness=self.endianness
        #list of header key to keep the order (when writing)
        RKey,orderList=self.rigakuKeys()
        self.header = {}
        self.header_keys = orderList

        #swapBool=False
        fs=endianness
        minHeaderLength=1400 #from rigaku's def
        #if (numpy.little_endian and endianness=='>'):
        #    swapBool=True
        #file should be open already
        #fh=open(filename,'rb')
        infile.seek(0) #hopefully seeking works.
        rawHead=infile.read(minHeaderLength)
        #fh.close() #don't like open files in case of intermediate crash

        self.header=dict()
        curByte=0
        for key in orderList:
            if isinstance(RKey[key],int):
                #read a number of bytes, convert to char. 
                #if -1, read remainder of header
                if RKey[key]==-1:
                    rByte=len(rawHead)-curByte
                    self.header[key]=struct.unpack(fs + str(rByte) + 's',
                            rawHead[curByte : curByte + rByte])[0]
                    curByte+=rByte
                    break

                rByte=RKey[key]
                self.header[key]=struct.unpack(fs + str(rByte) + 's',
                        rawHead[curByte : curByte + rByte])[0]
                curByte+=rByte
            elif RKey[key]=='float':
                #read a float, 4 bytes
                rByte=4
                self.header[key]=struct.unpack(fs + 'f',
                        rawHead[curByte : curByte + rByte])[0]
                curByte+=rByte
            elif RKey[key]=='long':
                #read a long, 4 bytes
                rByte=4
                self.header[key]=struct.unpack(fs + 'l',
                        rawHead[curByte : curByte + rByte])[0]
                curByte+=rByte
            else:
                logging.warn('special header data type {} not understood'
                        .format(Rkey[key]))
            if len(rawHead)==curByte:
                #"end reached"
                break

    def read(self, fname, frame=None):
        """
        try to read image 
        @param fname: name of the file
        @param frame: 
        """

        endianness=self.endianness
        self.resetvals()
        infile = self._open(fname,'rb')
        offset=-1 #read from EOF backward
        try:
            self._readheader(infile)
        except:
            raise

        #we read the required bytes from the end of file, using code
        #lifted from binaryimage
        #read the image data

        self.dim1 = self.header['X Pixels'] 
        self.dim2 = self.header['Y Pixels']
        self.bytecode = 'uint16'
        f = open(self.filename, "rb")
        dims = [self.dim2, self.dim1]
        bpp = len(numpy.array(0, self.bytecode).tostring())
        size = dims[0] * dims[1] * bpp

        if offset >= 0:
            f.seek(offset)
        else:
            try:
                f.seek(-size + offset + 1, 2) #seek from EOF backwards
            except IOError:
                logging.warn('expected datablock too large, please check bytecode settings: {}'.format(self.bytecode))
            except:
                logging.error('Uncommon error encountered when reading file')
        rawData = f.read(size)
        if  self.swap_needed():
            data = numpy.fromstring(rawData, self.bytecode).byteswap().reshape(tuple(dims))
        else:
            data = numpy.fromstring(rawData, self.bytecode).reshape(tuple(dims))

        #Now we do some fixing for Rigaku's refusal to adhere to standards:
        sf=self.header['Photomultiplier Ratio']
        #find indices for which we need to do the correction (for which
        #the 16th bit is set):
        di=(data>=2**15)
        #reduce by the last bit
        data[di]-=2**16
        #multiply by the ratio  defined in the header
        data[di]*=sf
        self.data = data
        return self

    def rigakuKeys(self):
        #returns dict of keys and keyLengths
        RKey={
                'InstrumentType':10,
                'Version':10,
                'Crystal Name':20,
                'Crystal System':12,
                'A':'float',
                'B':'float',
                'C':'float',
                'Alpha':'float',
                'Beta':'float',
                'Gamma':'float',
                'Space Group':12,
                'Mosaicity':'float',
                'Memo':80,
                'Date':12,
                'Reserved Space 1':84,
                'User':20,
                'Xray Target':4,
                'Wavelength':'float',
                'Monochromator':20,
                'Monochromator 2theta':'float',
                'Collimator':20,
                'Filter':4,
                'Crystal-to-detector Distance':'float',
                'Generator Voltage':'float',
                'Generator Current':'float',
                'Focus':12,
                'Xray Memo':80,
                'IP shape':'long', #1= cylindrical, 0=flat. A "long" is overkill.
                'Oscillation Type':'float', #1=weissenberg. else regular. "float"? really?
                'Reserved Space 2':56,
                'Crystal Mount (spindle axis)':4,
                'Crystal Mount (beam axis)':4,
                'Phi Datum':'float', #degrees
                'Phi Oscillation Start':'float', #deg
                'Phi Oscillation Stop':'float',  #deg
                'Frame Number':'long',  
                'Exposure Time':'float', #minutes
                'Direct beam X position':'float', #special, x,y
                'Direct beam Y position':'float', #special, x,y
                'Omega Angle':'float', #omega angle
                'Chi Angle':'float', #omega angle
                '2Theta Angle':'float', #omega angle
                'Mu Angle':'float', #omega angle
                'Image Template':204, #used for storing scan template..
                'X Pixels':'long',
                'Y Pixels':'long',
                'X Pixel Length':'float', #mm
                'Y Pixel Length':'float', #mm
                'Record Length':'long',
                'Total':'long',
                'Starting Line':'long',
                'IP Number':'long',
                'Photomultiplier Ratio':'float',
                'Fade Time (to start of read)':'float',
                'Fade Time (to end of read)':'float', #good that they thought of this, but is it applied?
                'Host Type/Endian':10,
                'IP Type':10,
                'Horizontal Scan':'long', #0=left->Right, 1=Rigth->Left
                'Vertical Scan':'long', #0=down->up, 1=up->down
                'Front/Back Scan':'long', #0=front, 1=back
                'Pixel Shift (RAXIS V)':'float',
                'Even/Odd Intensity Ratio (RAXIS V)':'float',
                'Magic number':'long', #'RAPID'-specific
                'Number of Axes':'long',
                'Goniometer Vector ax.1.1':'float',
                'Goniometer Vector ax.1.2':'float',
                'Goniometer Vector ax.1.3':'float',
                'Goniometer Vector ax.2.1':'float',
                'Goniometer Vector ax.2.2':'float',
                'Goniometer Vector ax.2.3':'float',
                'Goniometer Vector ax.3.1':'float',
                'Goniometer Vector ax.3.2':'float',
                'Goniometer Vector ax.3.3':'float',
                'Goniometer Vector ax.4.1':'float',
                'Goniometer Vector ax.4.2':'float',
                'Goniometer Vector ax.4.3':'float',
                'Goniometer Vector ax.5.1':'float',
                'Goniometer Vector ax.5.2':'float',
                'Goniometer Vector ax.5.3':'float',
                'Goniometer Start ax.1':'float',
                'Goniometer Start ax.2':'float',
                'Goniometer Start ax.3':'float',
                'Goniometer Start ax.4':'float',
                'Goniometer Start ax.5':'float',
                'Goniometer End ax.1':'float',
                'Goniometer End ax.2':'float',
                'Goniometer End ax.3':'float',
                'Goniometer End ax.4':'float',
                'Goniometer End ax.5':'float',
                'Goniometer Offset ax.1':'float',
                'Goniometer Offset ax.2':'float',
                'Goniometer Offset ax.3':'float',
                'Goniometer Offset ax.4':'float',
                'Goniometer Offset ax.5':'float',
                'Goniometer Scan Axis':'long',
                'Axes Names':40,
                'file':16,
                'cmnt':20,
                'smpl':20,
                'iext':'long',
                'reso':'long',
                'save':'long',
                'dint':'long',
                'byte':'long',
                'init':'long',
                'ipus':'long',
                'dexp':'long',
                'expn':'long',
                'posx':20,
                'posy':20,
                'xray':'long',
                #more values can be added here
                'Header Leftovers':-1,
                }

        #make a list with the items in the right order
        orderList=[
                'InstrumentType',
                'Version',
                'Crystal Name',
                'Crystal System',
                'A',
                'B',
                'C',
                'Alpha',
                'Beta',
                'Gamma',
                'Space Group',
                'Mosaicity',
                'Memo',
                'Date',
                'Reserved Space 1',
                'User',
                'Xray Target',
                'Wavelength',
                'Monochromator',
                'Monochromator 2theta',
                'Collimator',
                'Filter',
                'Crystal-to-detector Distance',
                'Generator Voltage',
                'Generator Current',
                'Focus',
                'Xray Memo',
                'IP shape',
                'Oscillation Type',
                'Reserved Space 2',
                'Crystal Mount (spindle axis)',
                'Crystal Mount (beam axis)',
                'Phi Datum',
                'Phi Oscillation Start',
                'Phi Oscillation Stop',
                'Frame Number',
                'Exposure Time',
                'Direct beam X position',
                'Direct beam Y position',
                'Omega Angle',
                'Chi Angle',
                '2Theta Angle',
                'Mu Angle',
                'Image Template',
                'X Pixels',
                'Y Pixels',
                'X Pixel Length',
                'Y Pixel Length',
                'Record Length',
                'Total',
                'Starting Line',
                'IP Number',
                'Photomultiplier Ratio',
                'Fade Time (to start of read)',
                'Fade Time (to end of read)',
                'Host Type/Endian',
                'IP Type',
                'Horizontal Scan',
                'Vertical Scan',
                'Front/Back Scan',
                'Pixel Shift (RAXIS V)',
                'Even/Odd Intensity Ratio (RAXIS V)',
                'Magic number',
                'Number of Axes',
                'Goniometer Vector ax.1.1',
                'Goniometer Vector ax.1.2',
                'Goniometer Vector ax.1.3',
                'Goniometer Vector ax.2.1',
                'Goniometer Vector ax.2.2',
                'Goniometer Vector ax.2.3',
                'Goniometer Vector ax.3.1',
                'Goniometer Vector ax.3.2',
                'Goniometer Vector ax.3.3',
                'Goniometer Vector ax.4.1',
                'Goniometer Vector ax.4.2',
                'Goniometer Vector ax.4.3',
                'Goniometer Vector ax.5.1',
                'Goniometer Vector ax.5.2',
                'Goniometer Vector ax.5.3',
                'Goniometer Start ax.1',
                'Goniometer Start ax.2',
                'Goniometer Start ax.3',
                'Goniometer Start ax.4',
                'Goniometer Start ax.5',
                'Goniometer End ax.1',
                'Goniometer End ax.2',
                'Goniometer End ax.3',
                'Goniometer End ax.4',
                'Goniometer End ax.5',
                'Goniometer Offset ax.1',
                'Goniometer Offset ax.2',
                'Goniometer Offset ax.3',
                'Goniometer Offset ax.4',
                'Goniometer Offset ax.5',
                'Goniometer Scan Axis',
                'Axes Names',
                'file',
                'cmnt',
                'smpl',
                'iext',
                'reso',
                'save',
                'dint',
                'byte',
                'init',
                'ipus',
                'dexp',
                'expn',
                'posx',
                'posy',
                'xray',
                'Header Leftovers'
                ]


        return RKey,orderList


