import logging

import pathlib2 as pathlib


def posix_to_uri(data, pos_key, uri_key, delete_pos=True):
    """
    pre_load option for supporting both posix and uri arg specification
    """
    if data.get(pos_key) is not None:
        if data.get(uri_key) is None:
            data[uri_key] = pathlib.Path(
                data[pos_key]).resolve().as_uri()
        else:
            logging.warning(
                "{} {} is defined, so "
                "input option {} "
                "{} is being ignored.".format(
                    uri_key, data[uri_key],
                    pos_key, data[pos_key]))
        try:
            del data[pos_key]
        except KeyError:
            return
