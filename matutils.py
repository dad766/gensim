#!/usr/bin/env python2.5
# -*- coding: utf-8 -*-
#
# author Radim Rehurek, radimrehurek@seznam.cz

"""
This module contains math helper functions.
"""

import logging



class MmWriter(object):
    """
    Store corpus in Matrix Market format.
    """
    
    def __init__(self, fname):
        self.fname = fname
        self.fout = open(self.fname, 'w')
        self.headersWritten = False
    
    @staticmethod
    def determineNnz(corpus):
        logging.info("calculating matrix shape and density")
        numDocs = len(corpus)
        numTerms = numNnz = 0
        for docNo, bow in enumerate(corpus):
            if docNo % 10000 == 0:
                logging.info("PROGRESS: at document %i/%i" % 
                             (docNo, len(corpus)))
            if len(bow) > 0:
                numTerms = max(numTerms, 1 + max(wordId for wordId, val in bow))
                numNnz += len(bow)
        
        logging.info("BOW of %ix%i matrix, density=%.3f%% (%i/%i)" % 
                     (numDocs, numTerms,
                      100.0 * numNnz / (numDocs * numTerms),
                      numNnz,
                      numDocs * numTerms))
        return numDocs, numTerms, numNnz
    

    def writeHeaders(self, numDocs, numTerms, numNnz):
        logging.info("saving sparse %sx%s matrix with %i non-zero entries to %s" %
                     (numDocs, numTerms, numNnz, self.fname))
        self.fout.write('%%matrixmarket matrix coordinate real general\n')
        self.fout.write('%i %i %i\n' % (numDocs, numTerms, numNnz))
        self.lastDocNo = -1
        self.headersWritten = True
    
    
    def __del__(self):
        """
        Automatic destructor which closes the underlying file. 
        
        There must be no circular references contained in the object for __del__
        to work! Closing the file explicitly via the close() method is preferred
        and safer.
        """
        self.close() # does nothing if called twice (on an already closed file), so no worries
    
    
    def close(self):
        logging.debug("closing %s" % self.fname)
        self.fout.close()
    
    
    def writeVector(self, docNo, vector):
        """
        Write a single sparse vector to the file.
        
        Sparse vector is any iterable yielding (field id, field value) pairs.
        """
        assert self.headersWritten, "must write MM file headers before writing data!"
        assert self.lastDocNo < docNo, "documents %i and %i not in sequential order!" % (self.lastDocNo, docNo)
        for termId, weight in sorted(vector): # write term ids in sorted order
            # to ensure len(doc) does what is expected, there must not be any zero elements in the sparse document
            assert weight != 0, "zero weights not allowed in sparse documents; check your document generator"
            self.fout.write("%i %i %f\n" % (docNo + 1, termId + 1, weight)) # +1 because MM format starts counting from 1
        self.lastDocNo = docNo

    @staticmethod
    def writeCorpus(fname, corpus):
        """
        Save bag-of-words representation of an entire corpus to disk.
        
        Note that the documents are processed one at a time, so the whole corpus 
        is allowed to be larger than the available RAM.
        """
        mw = MmWriter(fname)
        mw.writeHeaders(*MmWriter.determineNnz(corpus))
        for docNo, bow in enumerate(corpus):
            if docNo % 1000 == 0:
                logging.info("PROGRESS: saving document %i/%i" % 
                             (docNo, len(corpus)))
            mw.writeVector(docNo, bow)
        mw.close()
#endclass MmWriter


class MmReader(object):
    """
    Wrap a corpus represented as term-document matrix on disk in matrix-market 
    format, and present it as an object which supports iteration over documents. 
    A document = list of (word, weight) 2-tuples. This iterable format is used 
    internally in LDA inference.
    
    Note that the file is read into memory one document at a time, not whole 
    corpus at once. This allows for representing corpora which are larger than 
    available RAM.
    """
    def __init__(self, fname):
        """
        Initialize the corpus reader. The fname is a path to a file on local 
        filesystem, which is expected to be sparse (coordinate) matrix
        market format. Documents are assumed to be rows of the matrix -- if 
        documents are columns, save the matrix transposed.
        """
        logging.info("initializing corpus reader from %s" % fname)
        self.fname = fname
        fin = open(fname)
        header = fin.next()
        if not header.lower().startswith('%%matrixmarket matrix coordinate real general'):
            raise ValueError("File %s not in Matrix Market format with coordinate real general" % fname)
        self.noRows = self.noCols = self.noElements = 0
        for lineNo, line in enumerate(fin):
            if not line.startswith('%'):
                self.noRows, self.noCols, self.noElements = map(int, line.split())
                break
        logging.info("accepted corpus with %i documents, %i terms, %i non-zero entries" %
                     (self.noRows, self.noCols, self.noElements))
    
    def __len__(self):
        return self.noRows
        
    def __iter__(self):
        fin = open(self.fname)
        
        # skip headers
        for line in fin:
            if line.startswith('%'):
                continue
            break
        
        prevId = -1
        for line in fin:
            docId, termId, val = line.split()
            docId, termId, val = int(docId) - 1, int(termId) - 1, float(val) # -1 because matrix market indexes are 1-based => convert to 0-based
            if docId != prevId:
                # change of document: return the document read so far (its id is prevId)
                if prevId >= 0:
                    yield prevId, document
                                
                # return implicit (empty) documents between previous id and new id 
                # too, to keep consistent document numbering and corpus length
                for prevId in xrange(prevId + 1, docId):
                    yield prevId, []
                
                # from now on start adding fields to a new document, with a new id
                prevId = docId
                document = []
            
            document.append((termId, val,)) # add another field to the current document
        
        # handle the last document, as a special case
        if prevId >= 0:
            yield prevId, document
        for prevId in xrange(prevId + 1, self.noRows):
            yield prevId, []
#endclass MmReader
