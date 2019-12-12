from uri_handler.utils._compat import urllib

from uri_handler.utils.uri_utils import (
     uri_join,
     get_prefix_path,
     uri_prefix)

from uri_handler.uri_functions import (
    uri_readbytes,
    uri_writebytes)


# FIXME this should be in uri_handler!
def uri_basename(uri, delimiter='/'):
    p = urllib.parse.urlparse(uri).path
    return p.split(delimiter)[-1]


__all__ = [
    "uri_join", "uri_prefix", "uri_readbytes", "uri_writebytes"]
