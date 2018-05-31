import os
import re
import json
import datetime
import pytz
import argschema
from marshmallow import ValidationError


def set_dict_values(metadata,list_key,list_val):
    for elements in range(0,len(list_key)) :
        key = list_key[elements]
        value = list_val[elements]
        metadata[key] = value
    return metadata

def get_img_and_metafiles(sessiondir, metadata):
    matchstr = ".*\.tif"
    imgfiles = []
    for chan in metadata:
        channame = chan['channel']
        d = os.path.join(sessiondir,channame)
        imgfiles.extend([os.path.join(d, f) for f in os.listdir(d) if os.path.isfile(os.path.join(d, f)) and re.match(matchstr, f) ])

    metafiles = [ w.replace('.tif', '_metadata.txt') for w in imgfiles]
    imgfiles = [ w.replace(sessiondir+'/', '') for w in imgfiles]

    return imgfiles, metafiles

def get_session_number(sessiondir):
    tokens = sessiondir.split("session")
    return int(tokens[1])

def create_metafile(sessiondir):

    metadata = {}

    #acquisition_data - need to figure out how to populate the following:
    acq = {
        'microscope_type': 'Leica',
        'microscope': 'Igor',
        'camera': {
            'camera_id': '49600128',
            'model': 'Leica X'
        },
        'acquisition_time': '2018-03-08T03:07:19+00:00',
        'overlap': 0.12
    }

    with open(os.path.join(sessiondir,'session_metadata.txt')) as f:
        lines = f.readlines()
    acq = set_dict_values(acq,lines[0].split(), lines[1].split())
    assert  int(acq['#chan']) == len(lines)-5 # make sure that you have all the channels

    #channel information
    headings = ["channel","exposure_times","RLPosition"]
    d_channels = []
    for i in range(3, len(lines)-2):
        d = {}
        d = set_dict_values(d,headings,lines[i].split())
        d_channels.append(d)

    #data
    numtiles = int(acq['#chan']) * int(acq['MosaicX']) * int(acq['MosaicY'])
    tilefiles,metafiles = get_img_and_metafiles(sessiondir, d_channels)
    assert len(tilefiles) == numtiles & len(metafiles) == numtiles
    data = []
    for i in range (0, len(metafiles)):
        m = {}
        assert os.path.exists(metafiles[i])
        with open(metafiles[i]) as f:
            lines = f.readlines()

        m = set_dict_values(m,lines[0].split(), lines[1].split())
        m = set_dict_values(m,lines[2].split(), lines[3].split())
        m['img_path'] = tilefiles[i]
        data.append(m)

    #set metadata and output to file
    metadata['registration_series'] = get_session_number(sessiondir)
    metadata['acquisition_data'] = acq
    metadata['all_channels'] = d_channels
    metadata['data'] = data
    with open(os.path.join(sessiondir, "metadata.json"), 'w') as fp:
        json.dump(metadata, fp, indent=4)
