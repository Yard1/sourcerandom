# By Antoni Baum (Yard1), 2018

from enum import Enum
import os.path
import random
import requests

class OnlineRandomnessSource(Enum):
    RANDOM_ORG = 1
    QRNG_ANU = 2

class SourceRandom(random.SystemRandom):
    """Alternate random number generator using sources provided
    by either TRNG online services (RANDOM.org and qrng.anu.edu.org),
    plaintext uint8 files (separated by whitespace) or collections of ints.
    """
    def __init__(self, source, cache_size=1024, preload=False, reuse=False):
        """Initialize an instance.
        source - define what source to use:
            - OnlineRandomnessSource.RANDOM_ORG for RANDOM.org
            - OnlineRandomnessSource.QRNG_ANU for qrng.anu.edu.org
            - file path as string for a plaintext file
            - collection for collection
        cache_size - how many bytes should be cached when requesting from
        online services or when loading from file (supports large files).
        RANDOM.org has a limit of 16384 bytes per request and qrng.anu.edu.org
        has a limit of 1024 bytes - cache_size larger than those limits when used
        with corresponding sources will raise a ValueError. Default - 1024.
        preload - whether to connect and download/read data on initialization,
        instead of waiting for a request to generate a number. Ignored if
        source is a collection. Default - False.
        reuse - whether to keep reusing bytes from the same file/collection,
        instead of raising an exception. Default - False.
        """
        self.cache_size = int(cache_size)
        if self.cache_size <= 0:
            raise ValueError('cache_size has to be bigger than 0!')
        if source == OnlineRandomnessSource.RANDOM_ORG:
            if cache_size <= 16384:
                self.source = self.random_org_generator(cache_size)
            else:
                raise ValueError('cache_size too big for RANDOM.org (max 16384)')
        elif source == OnlineRandomnessSource.QRNG_ANU:
            if cache_size <= 1024:
                self.source = self.qrng_anu_generator(cache_size)
            else:
                raise ValueError('cache_size too big for QRNG_ANU (max 1024)')
        elif os.path.isfile(str(source)):
            #print("File %s exists, using" % str(source))
            self.source = self.file_generator(cache_size, source, reuse)
        else:
            #test if iterable
            try:
                for _ in source:
                    break
            except:
                raise ValueError('Incorrect source')
            self.source = self.iterator_generator(source, reuse)
        if preload and (source == OnlineRandomnessSource.RANDOM_ORG or source == OnlineRandomnessSource.QRNG_ANU):
            next(self.source)
        #print("SourceRandom object initialized")

    # overwritten method - in SystemRandom, it gets bytes from the OS (/dev/urandom for Linux)
    def getrandbits(self, k):
        """getrandbits(k) -> x.  Generates an int with k random bits."""
        if k <= 0:
            raise ValueError('number of bits must be greater than zero')
        if k != int(k):
            raise TypeError('number of bits should be an integer')
        numbytes = (k + 7) // 8                       # bits / 8 and rounded up
        source = self.source
        bytes_list = []
        for _ in range(numbytes):
            bytes_list.append(next(source))
        x = int.from_bytes(bytes_list, 'big')
        return x >> (numbytes * 8 - k)                # trim excess bits

    def _get_random_org_online_data(self, count):
        """_get_random_org_online_data(count) -> x.  Fetches count bytes from RANDOM.org."""
        #print('_get_random_org_online_data %s' % count)
        quota = requests.get('https://www.random.org/quota/?format=plain', timeout=30).text
        quota = int(quota.strip())
        #print("RANDOM.ORG quota: %s (bytes: %s)" % (str(quota), str(quota // 8)))
        if quota < count:
            raise ConnectionError("Quota exhausted!")
        url = 'https://www.random.org/cgi-bin/randbyte?nbytes=%s&format=d' % count
        response = requests.get(url, timeout=30)
        if response.status_code != 200:
            raise ConnectionError('Response status not 200!')
        #print("Connection to https://www.random.org successful!")
        text = str(response.text).split()
        random_bytes = list(map(int, text))
        if not random_bytes or len(random_bytes) < 1:
            raise ValueError('Empty or null list')
        #print("Length: %s" % str(len(random_bytes)))
        return random_bytes

    def _get_qrng_anu_online_data(self, count):
        """_get_qrng_anu_online_data(count) -> x.  Fetches count bytes from qrng_anu.edu.au."""
        #print('_get_qrng_anu_online_data %s' % count)
        url = 'https://qrng.anu.edu.au/API/jsonI.php?length=%s&type=uint8' % count
        response = requests.get(url, timeout=30)
        if response.status_code != 200:
            raise ConnectionError('Response status not 200!')
        #print("Connection to https://qrng.anu.edu.au successful!")
        response = response.json()
        if not response['success']:
            raise ValueError('Server did not return success True')
        if response['length'] != count:
            raise ValueError('Server returned length != count')
        #print("Length: %s" % response['length'])
        return list(map(int, response['data']))

    def random_org_generator(self, cache_size):
        """Returns bytes from RANDOM.org. Caches numbers to avoid latency."""
        while True:
            for b in self._get_random_org_online_data(cache_size):
                yield b

    def qrng_anu_generator(self, cache_size):
        """Returns bytes from qrng.aun.edu.au Caches numbers to avoid latency."""
        while True:
            for b in self._get_qrng_anu_online_data(cache_size):
                yield b

    def file_generator(self, cache_size, file_name, reuse=False):
        """Returns bytes from a given plaintext file. Reads file in cache_size chunks.
        Caches numbers to avoid latency."""
        condition = True
        while condition:
            with open(file_name, "r") as f:
                while True:
                    chunk = f.read(cache_size)
                    if not chunk:
                        break
                    chunk = list(map(int, chunk.split()))
                    for b in chunk:
                        b = int(b)
                        if 0 <= b <= 255:
                            yield b
                        else:
                            raise ValueError('integer is not a byte (not between 0 - 255)')
            condition = reuse
        raise ValueError('All bytes from file %s have been used' % file_name)

    def iterator_generator(self, col, reuse=False):
        """Returns bytes from a given collection."""
        condition = True
        while condition:
            for b in col:
                b = int(b)
                if 0 <= b <= 255:
                    yield b
                else:
                    raise ValueError('integer is not a byte (not between 0 - 255)')
            condition = reuse
        raise ValueError('All bytes from collection have been used')
