#!/usr/bin/env python
"""
watch source directories for new TEMCA acquisitions
monitor space on target directory
upload and trigger workflow engine when it is feasible

TODO
    generic handling for makedirs errors (using errno)

"""
import os
import subprocess
import datetime
import time
import imghdr
import json
import re
import errno

import pytz

import dateutil.parser
import marshmallow
import argschema
from argschema.fields import List, InputDir, OutputDir, Float, Str, Nested

from rendermodules.ingest.schemas import IngestParams
from rendermodules.ingest import ingest_tileset

# "outdir": "/allen/programs/celltypes/production/incoming/wijem/",
example_input = {
    "indirs": [
        # "/data/em-131fs2/1x1mm_data/TEMCA3/Baylor_Test_Mouse#4/",
        "/data/em-131fs2/test_workflow/TEMCA3/Baylor_Nov_2017/",
        "/data/em-131fs2/test_workflow/TEMCA2/Baylor_Nov_2017/"],
    "outdir": "/allen/programs/celltypes/production/incoming/wijem/",
    "fillpercentage": 0.7,
    "copy_method": "gsutil",
    "ingest_client": {
        "app_key": "at_em_imaging_workflow",
        "workflow_name": "em_2d_montage"
    }
}


class IngestMonitorException(Exception):
    pass


class NoCandidateError(IngestMonitorException):
    pass


def get_available_space_percentage(d):
    s = os.statvfs(d)
    return float(s.f_bavail) / float(s.f_blocks)


def get_used_space_percentage(d):
    return 1. - get_available_space_percentage(d)


class SendAcquisitionParameters(argschema.ArgSchema):
    indirs = List(InputDir, required=True, description=(
        "directories to monitor for new acquisition directories"))
    outdir = OutputDir(required=True, description=(
        "directory to which aquisition directories will be copied"))
    fillpercentage = Float(
        required=False, default=0.7,
        validator=marshmallow.validate.Range(min=0.0, max=0.85),
        description=("Fraction of disk containing outdir which can "
                     "maximally be filled."))
    copy_method = Str(required=False, default="gsutil",
                      validator=marshmallow.validate.OneOf(
                          ["gsutil", "shutil"]))
    ingest_client = Nested(IngestParams, required=True)


class SendAcquisitionModule(ingest_tileset.IngestTileSetModule):
    default_schema = SendAcquisitionParameters

    copy_cmd = ['gsutil', '-m', 'cp', '-rn']
    mask = 000
    # subprocess_mode = subprocess.call

    inactive_timer = datetime.timedelta(hours=1)
    inactive_sleep_seconds = 300

    insufficient_space_sleep_seconds = 30
    noCandidate_sleep_seconds = 10

    reference_timeout = datetime.timedelta(hours=30)
    reference_filename = 'reference_set_list.json'

    reference_set_dir_re = '\d{14}_reference'
    finished_directory_re = '.*_.*_.*_montage.json'

    @classmethod
    def get_copy_command(cls, src, dst):
        # TODO this should drop into subshell setting umask
        return cls.copy_cmd + [src, dst]

    @classmethod
    def run_copy_command(cls, src, dst, **kwargs):
        def initshellfn():
            os.setpgrp()
            os.umask(cls.mask)
        return subprocess.check_call(
            cls.get_copy_command(src, dst),
            preexec_fn=initshellfn, **kwargs)

    def run_copy_command_with_retries(self, src, dst, retries=10, **kwargs):
        try:
            retries = (retries if self.retries is None else self.retries)
        except AttributeError as e:
            retries = retries

        attempts = 0
        while attempts < retries:
            try:
                r = self.run_copy_command(src, dst, **kwargs)
                if r != 0:
                    # call acts similarly to check_call
                    raise subprocess.CalledProcessError(r)
                else:
                    break
            except subprocess.CalledProcessError as e:
                attempts += 1
                self.logger.debug(
                    "copy attempt {} failed with code {}".format(
                        attempts, e))
                if attempts == retries:
                    raise
        self.logger.debug(
            "copy command completed in {} attempts".format(attempts))

    @staticmethod
    def generate_ingest_input(tile_dir, reference_set_id=None):
        # TODO should allow setting app_key and workflow_name
        return dict(ingest_tileset.example_input,
                    **{'tile_dir': tile_dir,
                       'reference_set_id': reference_set_id})

    def directory_is_complete(self, directory, metafile=None):
        # incomplete if we can't find a metadata file
        try:
            metafile = (self.find_metafile_in_dir(directory) if metafile
                        is None else metafile)
        except IndexError:
            # FIXME have this raise a custom error... fine for now
            self.logger.warning(
                "cannot find metadata file for {}".format(directory))
            return False

        with open(metafile, 'r') as f:
            md = json.load(f)
        image_files = [os.path.join(directory, imgdata['img_path'])
                       for imgdata in md[1]['data']]
        try:
            # return all([imghdr.what(imgfn) for imgfn in image_files])
            return all([os.path.isfile(imgfn) for imgfn in image_files])
        except IOError as e:
            self.logger.debug("directory incomplete with {}".format(e))
            return False

    @classmethod
    def get_finished_directories(cls, mondir):
        finished_tilesets = []
        try:
            monfiles = os.listdir(mondir)
        except OSError as e:
            # TODO make this catch nonexistent directories
            return []
        for fn in monfiles:
            if re.match(cls.finished_directory_re, fn):
                with open(os.path.join(mondir, fn), 'r') as f:
                    mon = json.load(f)
                finished_tilesets.append(os.path.join(
                    mon['origin_directory'], ''))
        # look for lcs
        lcfn = os.path.join(mondir, cls.reference_filename)
        try:
            with open(lcfn, 'r') as f:
                lcl = json.load(f)
            finished_tilesets.extend([
                os.path.join(d['origin_directory'], '') for d in lcl])
        except IOError as e:
            # TODO this should be aware of ENOENT
            pass
        return finished_tilesets

    @staticmethod
    def get_subdirectories(d):
        for subdir in os.listdir(d):
            if os.path.isdir(os.path.join(d, subdir)):
                yield subdir

    def get_available_directories(self, inputdir):
        """walk directories to find potential tilesets"""
        for sessdir in self.get_subdirectories(inputdir):
            sesspath = os.path.join(inputdir, sessdir)
            for loaddir in self.get_subdirectories(sesspath):
                loadpath = os.path.join(sesspath, loaddir)
                for griddir in self.get_subdirectories(loadpath):
                    gridpath = os.path.join(loadpath, griddir, '')
                    yield gridpath

    @staticmethod
    def get_directory_time(d):
        return os.stat(d).st_mtime

    @classmethod
    def is_reference_directory_re(cls, d):
        loaddir = os.path.split(os.path.split(
            os.path.split(
                os.path.join(d, ''))[0])[0])[1]
        return bool(re.match(cls.reference_set_dir_re, loaddir))

    @classmethod
    def is_reference_directory(cls, d):
        return cls.is_reference_directory_re(d)

    def scan_directories(self, inputdirs, mondirs):
        """return untransferred directories which can be transferred"""
        untransferred_directories = []
        for inputdir, mondir in zip(inputdirs, mondirs):
            self.logger.debug(
                'scanning directory {} with monitoring directory {}'.format(
                    inputdir, mondir))
            finished_directory_ids = [
                self.gen_tileset_id(d) for d in self.get_finished_directories(
                    mondir)]
            available_directories = [
                d for d in self.get_available_directories(inputdir)
                if self.gen_tileset_id(d) not in finished_directory_ids]
            untransferred_directories.extend(
                [(avail_d, inputdir, mondir)
                 for avail_d in available_directories])
        # sort based on isreference, then modification time
        # FIXME this is returning as tuple w/ input and mondir.... not great
        return sorted(
            untransferred_directories,
            key=lambda x: (not self.is_reference_directory(x[0]),
                           self.get_directory_time(x[0])))

    def gather_refsets(self, mondirs):
        refset_files = [os.path.join(mondir, self.reference_filename)
                        for mondir in mondirs]
        refsets = []
        for refset_file in refset_files:
            if os.path.isfile(refset_file):
                with open(refset_file, 'r') as f:
                    refsets.extend(json.load(f))
        return refsets

    def metastructure_from_griddir(self, griddir):
        # returns relative path (from session dir) of griddir
        sess_load_griddir_l = [d for d in griddir.split(os.sep)
                               if d != ''][-3:]
        return os.path.join(*sess_load_griddir_l)

    def gen_tileset_id(self, tileset_dir):
        # assumes metastructure is unique which... basically it is
        return self.metastructure_from_griddir(tileset_dir).replace(
            os.sep, '_')

    def gen_montageset_monfn(self, montage_dir):
        return '{}_montage.json'.format(
            self.gen_tileset_id(montage_dir))

    def transfer_lenscorrection(self, d, outputdir, mondir):
        d = os.path.split(os.path.join(d, ''))[0]
        dstdir = os.path.join(outputdir, self.gen_tileset_id(d), '')
        try:
            os.makedirs(dstdir)
        except OSError as e:
            # TODO be okay with eexist, else raise
            pass
        self.run_copy_command_with_retries(os.path.join(d, '*'), dstdir)
        ingestinput = self.generate_ingest_input(dstdir)

        # FIXME dummy for this test
        # class FakeRefSetMod:
        #     def run(self):
        #         self.acquisition_time = pytz.timezone(
        #             ingest_tileset.IngestTileSetModule.timezone).localize(
        #                 datetime.datetime.now())
        #         self.microscope = 'sometemca'
        #         self.camera = '1234'
        #         return 'not-a-real-id'
        # refsetmod = FakeRefSetMod()

        refsetmod = ingest_tileset.IngestTileSetModule(
            input_data=ingestinput)
        refsetid = refsetmod.run()['enqueued_object_uid']

        lcd = {'refsetid': refsetid,
               'origin_directory': os.path.abspath(d),
               'transfer_time': datetime.datetime.now().isoformat(),
               'output_directory': outputdir,
               'monitoring_directory': mondir,
               'acquisition_time': refsetmod.acquisition_time.isoformat(),
               'microscope': refsetmod.microscope,
               'camera': refsetmod.camera,
               'tileset_id': self.gen_tileset_id(d)}

        monfile = os.path.join(mondir, self.reference_filename)
        try:
            with open(monfile, 'r') as f:
                newjson = json.load(f) + [lcd]
        except IOError:
            self.logger.info(
                'starting lens correction monitoring with file {}'.format(
                    monfile))
            newjson = [lcd]

        with open(monfile, 'w') as f:
            json.dump(newjson, f)

    def transfer_montageset(self, d, outputdir, refsets, mondir):
        d = os.path.split(os.path.join(d, ''))[0]
        dstdir = os.path.join(outputdir, self.gen_tileset_id(d), '')
        try:
            os.makedirs(dstdir)
        except OSError as e:
            # TODO allow EEXIST else raise
            pass
        self.run_copy_command_with_retries(os.path.join(d, '*'), dstdir)

        with open(ingest_tileset.IngestTileSetModule.find_metafile_in_dir(
                d), 'r') as f:
            md = json.load(f)

        montage_timestamp = ingest_tileset.IngestTileSetModule.gen_datetime(
            md[0]['metadata']['roi_creation_time'])
        montage_microscope = md[0]['metadata']['temca_id']
        montage_camera = md[0]['metadata']['camera_info']['camera_id']

        # potential refsets assume same camera and microscope
        # as well as acquisition time preceding montage set
        potential_refsets = [
            i for i in refsets
            if i['camera'] == montage_camera and
            i['microscope'] == montage_microscope and
            dateutil.parser.parse(i['acquisition_time']) < montage_timestamp]

        refsetid = None
        if potential_refsets:
            nearest_refsets = sorted(potential_refsets, key=lambda x: (
                montage_timestamp - dateutil.parser.parse(
                    x['acquisition_time'])))
            nearest_refset = nearest_refsets[0]
            if ((montage_timestamp -
                 dateutil.parser.parse(nearest_refset['acquisition_time'])) <
                    self.reference_timeout):
                self.logger.debug(
                    'associating montage set {} taken at {} '
                    'with reference set id {} taken at {}'.format(
                        d, montage_timestamp, nearest_refset['refsetid'],
                        nearest_refset['acquisition_time']))
                refsetid = nearest_refset['refsetid']
        if refsetid is None:
            self.logger.warning(
                'No Reference Set found to be associated '
                'with MontageSet {}'.format(d))

        ingestinput = self.generate_ingest_input(dstdir, refsetid)
        # FIXME comment out for sake of workflow
        _ = ingest_tileset.IngestTileSetModule(
            input_data=ingestinput).run()

        monfile = os.path.join(mondir, self.gen_montageset_monfn(d))
        montaged = {
            'refsetid': refsetid,
            'origin_directory': os.path.abspath(d),
            'transfer_time': datetime.datetime.now().isoformat(),
            'output_directory': outputdir,
            'monitoring_directory': mondir,
            'acquisition_time': montage_timestamp.isoformat(),
            'microscope': montage_microscope,
            'camera': montage_camera}

        with open(monfile, 'w') as f:
            json.dump(montaged, f)

    def transfer_directory(self, inputdirs, outputdir, mondirs):
        """raise NoCandidateError, return time of completion"""
        #
        for d, inputdir, mondir in self.scan_directories(inputdirs, mondirs):
            if self.directory_is_complete(d):
                self.logger.debug('attempting to transfer {}'.format(d))
                if self.is_reference_directory(d):
                    self.transfer_lenscorrection(d, outputdir, mondir)
                else:
                    refsets = self.gather_refsets(mondirs)
                    self.transfer_montageset(d, outputdir, refsets, mondir)
                return datetime.datetime.now()
            else:
                self.logger.debug('skipping incomplete directory {}'.format(d))
        raise NoCandidateError(
            'No candidate found for inputdirs {} and mondirs {}'.format(
                inputdirs, mondirs))

    def startmonitor(self, inputdirs, outputdir, fillpercentage, mondirs=None):
        """Check space utilization and pause if inactive"""
        mondirs = ([os.path.join(inputdir, '.monitor', '')
                    for inputdir in inputdirs] if mondirs is None else mondirs)
        if not len(mondirs) == len(inputdirs):
            raise IngestMonitorException(
                '{} monitoring directories are tracking '
                '{} input directories'.format(len(mondirs), len(inputdirs)))
        for mondir in mondirs:
            try:
                os.makedirs(mondir)
            except:
                # TODO allow eexist, else raise
                pass

        last_transfer = datetime.datetime.now()
        is_active = True
        while True:
            if not is_active:
                self.logger.debug(
                    "monitor is inactive -- last transfer at {}. "
                    "Sleeping for {}s".format(
                        last_transfer, self.inactive_sleep_seconds))
                time.sleep(self.inactive_sleep_seconds)
            if get_used_space_percentage(outputdir) < fillpercentage:
                try:
                    last_transfer = self.transfer_directory(
                        inputdirs, outputdir, mondirs)
                except NoCandidateError:
                    self.logger.debug("Nothing to transfer.")
                    time.sleep(self.noCandidate_sleep_seconds)
            else:
                self.logger.warning(
                    'cannot transfer due to space limitations: {} '
                    'occupied with threshold {}.'.format(
                        get_used_space_percentage(outputdir), fillpercentage))
                time.sleep(self.insufficient_space_sleep_seconds)
            is_active = ((datetime.datetime.now() - last_transfer) <
                         self.inactive_timer)

    def run(self):
        """handle arguments and start monitor"""
        self.startmonitor(self.args['indirs'], self.args['outdir'],
                          self.args['fillpercentage'])


if __name__ == "__main__":
    sendrunner = SendAcquisitionModule(input_data=example_input)
    sendrunner.run()
