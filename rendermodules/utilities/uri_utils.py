import errno
import os

from six.moves import urllib
# FIXME make uri_handler
# import uri_handler  # noqa


def join_paths(paths, delimiter='/'):
    """join paths with a delimiter"""
    return delimiter.join([p.rstrip(delimiter) for p in paths])


def uri_join(uri, *args, **kwargs):
    """os.path.join-style function for appending path strings
    to a fully qualified uri.
    """
    parsed_uri = urllib.parse.urlparse(uri)

    # py2.7 workaround for kw-only argument delimiter
    delimiter = kwargs.get('delimiter', '/')
    new_pr = urllib.parse.ParseResult(
        parsed_uri.scheme,
        parsed_uri.netloc,
        join_paths([parsed_uri.path] + list(args), delimiter),
        parsed_uri.params,
        parsed_uri.query,
        parsed_uri.fragment)
    return urllib.parse.urlunparse(new_pr)


def get_prefix_path(path, delimiter='/'):
    """get dirname-equivalent path prefix for a given delimiter"""
    split_path = path.split(delimiter)
    if len(split_path) == 1:
        return delimiter
    else:
        return delimiter.join(split_path)


def uri_prefix(uri, delimiter='/'):
    """get new uri with path that is one delimiter up from the input uri"""
    parsed_uri = urllib.parse.urlparse(uri)
    new_pr = urllib.parse.ParseResult(
        parsed_uri.scheme,
        parsed_uri.netloc,
        get_prefix_path(parsed_uri.path, delimiter),
        parsed_uri.params,
        parsed_uri.query,
        parsed_uri.fragment)
    return urllib.parse.urlunparse(new_pr)


def uri_readbytes(uri, **kwargs):
    """read bytes from uri"""
    # FIXME filesystem implementation only
    parsed_uri = urllib.parse.urlparse(uri)
    if parsed_uri.scheme != "file":
        raise Exception("unsupported scheme {} from uri {}".format(
            parsed_uri.scheme, uri))
    fpath = urllib.parse.unquote(parsed_uri.path)
    with open(fpath, 'rb') as f:
        b = f.read()
    return b
    # uh = uri_handler.get_uri_handler()
    # return uh.readbytes(uri, **kwargs)


def uri_writebytes(uri, b, **kwargs):
    """write bytes to uri"""
    # FIXME filesystem implementation only
    parsed_uri = urllib.parse.urlparse(uri)
    if parsed_uri.scheme != "file":
        raise Exception("unsupported scheme {} from uri {}".format(
            parsed_uri.scheme, uri))
    fpath = urllib.parse.unquote(parsed_uri.path)
    try:
        os.makedirs(os.path.dirname(fpath))
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise
    with open(fpath, 'wb') as f:
        b = f.write(b)
    # uh = uri_handler.get_uri_handler()
    # return uh.writebytes(uri, b, **kwargs)
