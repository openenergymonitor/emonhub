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
        self._full_warning_issued = False
        self._log = logging.getLogger("EmonHub")

    def hasItems(self):
        return self.size() > 0

    def isFull(self):
        return self.size() >= self._maximumEntriesInBuffer

    def getMaxEntrySliceIndex(self):
        # Number of oldest items to drop to leave room for one more without
        # going over the limit.
        return max(0,
                   self.size() - self._maximumEntriesInBuffer + 1)

    def discardOldestItems(self):
        # Only re-slice when something actually needs dropping. Slicing copies
        # the whole list, so doing it on every store made the cost of queuing a
        # frame grow with the size of the backlog.
        index = self.getMaxEntrySliceIndex()
        if index:
            del self._data_buffer[:index]

    def discardOldestItemsIfFull(self):
        if self.isFull():
            # Warn once on the way in rather than for every item stored. A full
            # buffer means a long outage, and a warning per frame would rotate
            # away the log needed to diagnose it.
            if not self._full_warning_issued:
                self._full_warning_issued = True
                self._log.warning(
                    "In-memory buffer (%s) reached limit of %d items, deleting oldest",
                    self._bufferName, self._maximumEntriesInBuffer)
            self.discardOldestItems()
        elif self._full_warning_issued:
            self._full_warning_issued = False
            self._log.warning(
                "In-memory buffer (%s) no longer full, %d items queued",
                self._bufferName, self.size())

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
        # del rather than re-slicing: this runs after every successful post, and
        # re-slicing copies the list and touches every item left in the backlog.
        del self._data_buffer[:number]

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
