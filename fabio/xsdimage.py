#!/usr/bin/env python
# coding: utf8
"""
Authors: Jérôme Kieffer, ESRF 
         email:jerome.kieffer@esrf.fr

XSDimge are XML files containing numpy arrays 
"""
__author__ = "Jérôme Kieffer"
__contact__ = "jerome.kieffer@esrf.eu"
__license__ = "GPLv3+"
__copyright__ = "European Synchrotron Radiation Facility, Grenoble, France"

import os, logging, struct
import numpy as np
from fabioimage import fabioimage
import base64, hashlib
from lxml import etree

class xsdimage(fabioimage):
    """ 
    Read the XSDataImage XML File data format 
    """
    def __init__(self, data=None, header=None, fname=None):
        """
        Constructor of the class XSDataImage.

        @param _strFilename: the name of the file to open
        @type  _strFilename: string
        """
        fabioimage.__init__(self, data=data, header=header)
        self.dims = []
        self.coding = None
        if fname is not None:
            self.filename = fname
            self.read(fname)

    def read(self, fname):
        """
        """
        self.header = {}
        self.resetvals()
        self.filename = fname
        infile = self._open(fname, "rb")
        self._readheader(infile)

        try:
            self.dim1, self.dim2 = self.dims[:2]
        except:
            raise IOError("XSD file %s is corrupt, no dimensions in it" % fname)
        try:
            self.bytecode = np.dtype(self.dtype).type
            self.bpp = len(np.array(0, self.bytecode).tostring())
        except TypeError:
            self.bytecode = np.int32
            self.bpp = 32
            logging.warning("Defaulting type to int32")

        exp_size = 1
        for i in self.dims:
            exp_size *= i
        assert exp_size == self.size

        decData = None
        if self.coding == "base64":
            decData = base64.b64decode(self.rawData)
        elif self.coding == "base32":
            decData = base64.b32decode(self.rawData)
        elif self.coding == "base16":
            decData = base64.b16decode(self.rawData)
        else:
            logging.warning("Unable to recognize the encoding of the data !!! got %s, expected base64, base32 or base16, I assume it is base64 " % self.coding)
            decData = base64.b64decode(self.rawData)
        if self.md5:
            assert  hashlib.md5(decData).hexdigest() == self.md5


        self.data = np.fromstring(decData, dtype=self.bytecode).reshape(tuple(self.dims))
        if not np.little_endian: #by default little endian
            self.data.byteswap(inplace=True)
        self.resetvals()
#        # ensure the PIL image is reset
        self.pilimage = None
        return self

    def _readheader(self, infile):
        """
        Read all headers in a file and populate self.header
        data is not yet populated
        @type infile: file object open in read mode
        """
        xml = etree.parse(infile)
        self.dims = []
        for i in xml.xpath("//shape"):
            try:
                self.dims.append(int(i.text))
            except ValueError:
                logging.warning("Shape: Unable to convert %s to integer in %s" % (i.text, i))
        for i in xml.xpath("//size"):
            try:
                self.size = int(i.text)
            except:
                logging.warning("Size: Unable to convert %s to integer in %s" % (i.text, i))
        self.dtype = None
        for i in xml.xpath("//dtype"):
            self.dtype = i.text
        self.coding = None
        for i in xml.xpath("//coding"):
            for j in i.xpath("//value"):
                self.coding = j.text
        self.rawData = None
        for i in xml.xpath("//data"):
            self.rawData = i.text
        self.md5 = None
        for i in xml.xpath("//md5sum"):
            for j in i.xpath("//value"):
                self.md5 = j.text





