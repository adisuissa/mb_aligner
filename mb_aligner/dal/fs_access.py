import os
from fs import open_fs
from urllib.parse import urlparse



class FSAccessRegistry(object):
    """
    A per-process (Singleton) filesystem access layer, that holds all the relevant file system access objects
    """

    MAX_TRIES = 3

    def __new__(cls):
        if not hasattr(cls, '__instance'):
            cls.__instance = super(FSAccessRegistry, cls).__new__(cls)
        return cls.__instance

    def __init__(self):
        self._registered_fs = {}

    def open_read(self, url, binary=True):
        parsed_url = urlparse(url)
        url_unique_id = "{}://{}".format(parsed_url.scheme, parsed_url.netloc)
        if url_unique_id not in self._registered_fs:
            fs = open_fs(url_unique_id)
            self._registered_fs[url_unique_id] = fs
        else:
            fs = self._registered_fs[url_unique_id]
        read_str = "rb" if binary else "rt"
        try_counter = 0
        while try_counter <= FSAccessRegistry.MAX_TRIES:
            try:
                res = fs.open(parsed_url.path, read_str)
                return res
            except:
                try_counter += 1
                if try_counter > FSAccessRegistry.MAX_TRIES:
                    raise
                print("Re-Reading path: {}".format(url))
        # should not reach here
        return None

class FSAccess(object):

    def __init__(self, _url, binary):
        self._url = _url
        self._binary = binary

    def __enter__(self):
        self._handle = FSAccessRegistry().open_read(self._url, self._binary)
        return self._handle

    def __exit__(self, type, value, traceback):
        return self._handle.__exit__(type, value, traceback)

