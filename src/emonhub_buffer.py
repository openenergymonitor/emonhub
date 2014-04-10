"""

  This code is released under the GNU Affero General Public License.
  
  OpenEnergyMonitor project:
  http://openenergymonitor.org

"""

import logging
import MySQLdb

"""class AbstractBuffer

Represents the actual buffer being used.
"""
class AbstractBuffer():

    bufferMethodMap = {
                       'memory':'InMemoryBuffer',
                       'database':'MySQLBuffer' 
                      } 

    def storeItem(self,data): 
        raise NotImplementedError

    def retrieveItem(self): 
        raise NotImplementedError

    def discardLastRetrievedItem(self):
        raise NotImplementedError

    def hasItems(self): 
        raise NotImplementedError

"""
This implementation of the AbstractBuffer just uses an in-memory datastructure.
It's basically identical to the previous (inline) buffer.
"""
class InMemoryBuffer(AbstractBuffer):
  
    def __init__(self, bufferName, bufferSize=1000):
        self._bufferName = str(bufferName)
        self._maximumEntriesInBuffer = int(bufferSize)
        self._data_buffer = []
        self._log = logging.getLogger("EmonHub")

    def hasItems(self):
        return self.size() > 0

    def isFull(self):
        return self.size() >= self._maximumEntriesInBuffer

    def getMaxEntrySliceIndex(self):
        return max(0,
                   self.size() - self._maximumEntriesInBuffer - 1 );

    def discardOldestItems(self):
        self._data_buffer = self._data_buffer[ self.getMaxEntrySliceIndex() : ]

    def discardOldestItemsIfFull(self):
        if self.isFull():
            self._log.warning(
              "In-memory buffer (%s) reached limit of %d items, deleting oldest" 
              % (self._bufferName, self._maximumEntriesInBuffer))
        self.discardOldestItems()

    def storeItem(self,data):
        self.discardOldestItemsIfFull();
        self._data_buffer.append (data)

    def retrieveItem(self):
        return self._data_buffer[0]

    def discardLastRetrievedItem(self):
        del self._data_buffer[0]

    def size(self):
        return len(self._data_buffer)

"""
This implementation of the AbstractBuffer uses MySQL.
"""
class MySQLBuffer(AbstractBuffer):
    
    def __init__(self, bufferName, dbUser, dbPassword, dbHost, dbDatabase,
                 hardDelete=False, bufferSize=999999):

        self._bufferName = bufferName
        self._lastRetrievedItemId = -1
        self._maximumEntriesInBuffer = int(bufferSize)
        self._dbConfig = {
          'host' : dbHost,
          'user' : dbUser,
          'password' : dbPassword,
          'database' : dbDatabase,
          'hardDelete' : hardDelete,
        }

        self._log = logging.getLogger("EmonHub") 

    def openDbConnection(self):

        return MySQLdb.connect(
                 self._dbConfig['host'], 
                 self._dbConfig['user'],
                 self._dbConfig['password'],
                 self._dbConfig['database']
               )

    def handleMySQLdbError (self, e):

        try:
            self._log.error ("MySQL buffer (%s) Error [%d]: %s" 
                             % (self._bufferName, e.args[0], e.args[1]))
        except IndexError:
            self._log.error ("MySQL buffer (%s) Error: %s" 
                             % (self._bufferName, str(e)))
  
    def hasItems (self):
        return self.size() > 0

    def isFull(self):
        
        self._log.debug("MySQL buffer (%s): is full? %d > %d = %s" 
            % (self._bufferName, self.size(), 
               self._maximumEntriesInBuffer, 
               self.size() >= self._maximumEntriesInBuffer))

        return self.size() >= self._maximumEntriesInBuffer
  
    def discardOldestItemsIfFull(self):

        while self.isFull():
            self._log.warning(
                "MySQL buffer (%s) reached limit of %d items, deleting oldest (with hard = %s)"
                % (self._bufferName, 
                   self._maximumEntriesInBuffer, 
                   str(self._dbConfig['hardDelete'])))

        if (self._dbConfig['hardDelete'] is True):
            self.hardDeleteOldestItem()
        else:
            self.softDeleteOldestItem()

    def softDeleteOldestItem(self):

        self._log.warning(
            "MySQL buffer (%s): soft delete (max buffer size reached)" 
            % (self._bufferName,))

        try:   
            self._conn = self.openDbConnection();
            dbCursor = self._conn.cursor()
            dbCursor.execute ( 
                "UPDATE data SET processed = -1 WHERE processed = 0 AND buffer = '%s' ORDER BY ID ASC LIMIT 1" 
                % (self._bufferName))
            dbCursor.close()
            self._conn.commit()
            self._conn.close()

        except MySQLdb.Error as e:
            self.handleMySQLdbError (e)

    def hardDeleteOldestItem(self):

        self._log.warning(
            "MySQL buffer (%s): hard delete (max buffer size reached)" 
            % (self._bufferName))

        try:   
            self._conn = self.openDbConnection();
            dbCursor = self._conn.cursor()
            dbCursor.execute (
                "DELETE FROM data WHERE processed = 0 AND buffer = '%s' ORDER BY ID ASC LIMIT 1" 
                % (self._bufferName))
            dbCursor.close()
            self._conn.commit()
            self._conn.close()

        except MySQLdb.Error as e:
            self.handleMySQLdbError (e)

        def storeItem(self,data):

            self._log.debug(
                "MySQL buffer (%s): storing input from node %s (%s) at %s"
                % (self._bufferName,
                   data[1][0],
                   data[1][1:],
                   data[0]))

            self.discardOldestItemsIfFull();

            try:   
                self._conn = self.openDbConnection();
                dbCursor = self._conn.cursor()
                dbCursor.execute (
                    "INSERT INTO data (buffer,time,node,data) VALUES ('%s',%s, %s,'%s')" 
                    % (self._bufferName, 
                       data[0], 
                       data[1][0], 
                       ','.join(str(x) for x in data[1][1:])))
                dbCursor.close()
                self._conn.commit()
                self._conn.close()

            except MySQLdb.Error as e:
                self.handleMySQLdbError (e)

    def retrieveItem(self):

        try:   
            self._conn = self.openDbConnection();
            dbCursor = self._conn.cursor()
            dbCursor.execute (
                "SELECT id, time, node, data FROM data WHERE processed = 0 and buffer = '%s' ORDER BY ID ASC LIMIT 1" 
                % (self._bufferName))
            ID, time, node, data = dbCursor.fetchone()
            dbCursor.close()
            self._conn.close()

        except MySQLdb.Error as e:
            self.handleMySQLdbError (e)
            return [-1,""]

        else:
            self._log.debug(
                "MySQL buffer (%s): retrieved stored input #%s from node %s (%s) at %s"
                % (self._bufferName, ID, node, data, time))

            self._lastRetrievedItemId = ID
    
            return [time,[node]+data.split(',')]

    def discardLastRetrievedItem(self):

        self._log.debug("MySQL buffer (%s): marking %s as processed" 
            % (self._bufferName, self._lastRetrievedItemId))

        try:
            self._conn = self.openDbConnection();
            dbCursor = self._conn.cursor()
            dbCursor.execute (
                "UPDATE data SET processed = unix_timestamp() WHERE id = %s" 
                % (self._lastRetrievedItemId))
            dbCursor.close()
            self._conn.commit()
            self._conn.close()

        except MySQLdb.Error as e:
            self.handleMySQLdbError (e)

    def size(self):
        
        size = 0
        try:
            self._conn = self.openDbConnection();
            dbCursor = self._conn.cursor()
            dbCursor.execute (
                "SELECT count(*) from data where processed = 0 and buffer = '%s'"
                % (self._bufferName))
            size = dbCursor.fetchone()[0]
            dbCursor.close()
            self._conn.close()

        except MySQLdb.Error as e:
            self.handleMySQLdbError (e)

        finally:
            if (size != 0):
                self._log.debug(
                    "MySQL buffer (%s): %d unprocessed items" 
                    % (self._bufferName, size))

        return int(size)

