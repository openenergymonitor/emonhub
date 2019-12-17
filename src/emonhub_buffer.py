"""

  This code is released under the GNU Affero General Public License.

  OpenEnergyMonitor project:
  http://openenergymonitor.org

"""

import logging

"""class AbstractBuffer

Represents the actual buffer being used.
"""


class AbstractBuffer:

    def storeItem(self, data):
        raise NotImplementedError

    def retrieveItems(self, number):
        raise NotImplementedError

    def retrieveItem(self):
        raise NotImplementedError

    def discardLastRetrievedItem(self):
        raise NotImplementedError

    def discardLastRetrievedItems(self, number):
        raise NotImplementedError

    def hasItems(self):
        raise NotImplementedError

"""
This implementation of the AbstractBuffer just uses an in-memory data structure.
It's basically identical to the previous (inline) buffer.
"""


class InMemoryBuffer(AbstractBuffer):

    def __init__(self, bufferName, buffer_size):
        self._bufferName = str(bufferName)
        self._buffer_type = "memory"
        self._maximumEntriesInBuffer = int(buffer_size)
        self._data_buffer = []
        self._log = logging.getLogger("EmonHub")

    def hasItems(self):
        return self.size() > 0

    def isFull(self):
        return self.size() >= self._maximumEntriesInBuffer

    def getMaxEntrySliceIndex(self):
        return max(0,
                   self.size() - self._maximumEntriesInBuffer - 1)

    def discardOldestItems(self):
        self._data_buffer = self._data_buffer[self.getMaxEntrySliceIndex():]

    def discardOldestItemsIfFull(self):
        if self.isFull():
            self._log.warning(
                "In-memory buffer (%s) reached limit of %d items, deleting oldest"
                % (self._bufferName, self._maximumEntriesInBuffer))
        self.discardOldestItems()

    def storeItem(self, data):
        self.discardOldestItemsIfFull()
        self._data_buffer.append(data)

    def retrieveItem(self):
        return self._data_buffer[0]

    def retrieveItems(self, number):
        blen = len(self._data_buffer)
        if number > blen:
            number = blen
        return self._data_buffer[:number]

    def discardLastRetrievedItem(self):
        del self._data_buffer[0]

    def discardLastRetrievedItems(self, number):
        blen = len(self._data_buffer)
        if number > blen:
            number = blen
        self._data_buffer = self._data_buffer[number:]

    def size(self):
        return len(self._data_buffer)


"""
The getBuffer function returns the buffer class corresponding to a
buffering method passed as argument.
"""
bufferMethodMap = {
                   'memory': InMemoryBuffer
                  }


def getBuffer(method):
    """Returns the buffer class corresponding to the method

    method (string): buffering method

    """
    return bufferMethodMap[method]
