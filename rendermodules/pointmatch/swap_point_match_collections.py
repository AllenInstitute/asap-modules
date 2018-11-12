import renderapi
import requests
from functools import partial
from rendermodules.module.render_module import RenderModule, RenderModuleException
from rendermodules.pointmatch.schemas import SwapPointMatches, SwapPointMatchesOutput
import time

example = {
    "render": {
        "host": "em-131db",
        "port": 8080,
        "owner": "gayathrim",
        "project": "17797_1R",
        "client_scripts": "/allen/aibs/pipeline/image_processing/volume_assembly/render-jars/production/scripts/"
    },
    "match_owner": "match_owner",
    "source_collection": "source_collection",
    "target_collection": "target_collection",
    "zValues": [1015]
}

def swap_pt_matches(render, source_collection, target_collection, z, match_owner=None):
    session = requests.Session()
    session.mount('http://', requests.adapters.HTTPAdapter(max_retries=5))

    groupid = "{}.0".format(str(z))
    match_owner = match_owner if match_owner is not None else render.DEFAULT_OWNER

    # get all pt matches for this group (both within and outside group point matches)
    sourcematches = renderapi.pointmatch.get_matches_with_group(source_collection, 
                                                                groupid, 
                                                                owner=match_owner,
                                                                render=render,
                                                                session=session)
    targetmatches = renderapi.pointmatch.get_matches_with_group(target_collection,
                                                                groupid,
                                                                owner=match_owner,
                                                                render=render,
                                                                session=session)
    # write them to a temp collection
    temp_col1 = "temp_{}_{}_{}".format(source_collection, groupid, time.strftime("%m%d%y_%H%M%S"))
    temp_col2 = "temp_{}_{}_{}".format(target_collection, groupid, time.strftime("%m%d%y_%H%M%S"))

    try:
        renderapi.pointmatch.import_matches(temp_col1, sourcematches, owner=match_owner, render=render, session=session)
        renderapi.pointmatch.import_matches(temp_col2, targetmatches, owner=match_owner, render=render, session=session)
    except Exception as e:
        print("Could not create temp point match collections")
        return False
    
    # get the qgroupIds in source matches
    sourcegroupIds = [m['qGroupId'] for m in sourcematches]

    # delete the matches between groupid and sourcegroupIds
    for sg in sourcegroupIds:
        renderapi.pointmatch.delete_point_matches_between_groups(source_collection,
                                                                    groupid,
                                                                    sg,
                                                                    owner=match_owner,
                                                                    render=render,
                                                                    session=session)
    targetgroupIds = [m['qGroupId'] for m in targetmatches]
    for tg in targetgroupIds:
        renderapi.pointmatch.delete_point_matches_between_groups(target_collection,
                                                                groupid,
                                                                tg,
                                                                owner=match_owner,
                                                                render=render,
                                                                session=session)
    try:
        # import source matches into target collection
        renderapi.pointmatch.import_matches(target_collection,
                                            sourcematches,
                                            owner=match_owner,
                                            render=render,
                                            session=session)
        # import target matches into source collection
        renderapi.pointmatch.import_matches(source_collection,
                                            targetmatches,
                                            owner=match_owner,
                                            render=render,
                                            session=session)
    except Exception as e:
        print("Cannot swap point matches, but temp collections {} and {} have been created for z = {}".format(temp_col1, temp_col2, z))
        return False
    
    try:
        # delete the two temp collections
        renderapi.pointmatch.delete_collection(temp_col1, owner=match_owner, render=render, session=session)
        renderapi.pointmatch.delete_collection(temp_col2, owner=match_owner, render=render, session=session)
    except Exception as e:
        print("Could not delete temp collections {} and {}".format(temp_col1, temp_col2))

    return True


class SwapPointMatchesModule(RenderModule):
    default_schema = SwapPointMatches
    default_output_schema = SwapPointMatchesOutput

    def run(self):
        # get match collections 
        collecs = renderapi.pointmatch.get_matchcollections(owner=self.args['match_owner'], render=self.render)

        collections = [c['collectionId']['name'] for c in collecs]

        if (self.args['source_collection'] not in collections) or (self.args['target_collection'] not in collections):
            raise RenderModuleException("One of source or target collections does not exist")

        # get all groupIds from source and target collections
        source_ids = renderapi.pointmatch.get_match_groupIds(self.args['source_collection'], 
                                                            owner=self.args['match_owner'], 
                                                            render=self.render)
        
        target_ids = renderapi.pointmatch.get_match_groupIds(self.args['target_collection'],
                                                            owner=self.args['match_owner'],
                                                            render=self.render)

        # check existence of zvalues
        ids = [s for s in self.args['zValues'] if "{}.0".format(str(s)) in source_ids and "{}.0".format(str(s)) in target_ids]
        
        # create a temp collection to copy the data
        zvalues = []
        mypartial = partial(swap_pt_matches,
                            self.render,
                            self.args['source_collection'],
                            self.args['target_collection'],
                            match_owner=self.args['match_owner'])

        with renderapi.client.WithPool(self.args['pool_size']) as pool:
            output_bool = pool.map(mypartial, ids)
            
        zvalues = [z for z, n in zip(ids, output_bool) if n]    
        

        self.output({"source_collection": self.args['source_collection'], 
                     "target_collection": self.args['target_collection'],
                     "swapped_zs": zvalues, 
                     "nonswapped_zs": set(self.args['zValues']).difference(zvalues)})

if __name__ == "__main__":
    mod = SwapPointMatchesModule(input_data=example)
    mod.run()
