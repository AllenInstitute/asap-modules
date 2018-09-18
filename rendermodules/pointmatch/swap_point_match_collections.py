import renderapi
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

class SwapPointMatchesModule(RenderModule):
    default_schema = SwapPointMatches
    default_output_schema = SwapPointMatchesOutput

    def run(self):
        # get match collections 
        collecs = renderapi.pointmatch.get_matchcollections(owner=self.args['match_owner'], render=self.render)

        collections = [c['collectionId']['name'] for c in collecs]

        print(self.args['source_collection'], self.args['target_collection'])
        print(collections)
        if (self.args['source_collection'] not in collections) or (self.args['target_collection'] not in collections):
            raise RenderModuleException("One of source or target collections does not exist")

        # get all groupIds from source and target collections
        source_ids = renderapi.pointmatch.get_match_groupIds(self.args['source_collection'], 
                                                            owner=self.args['match_owner'], 
                                                            render=self.render)
        
        target_ids = renderapi.pointmatch.get_match_groupIds(self.args['target_collection'],
                                                            owner=self.args['match_owner'],
                                                            render=self.render)

        # create a temp collection to copy the data
        zvalues = []
        for z in self.args['zValues']:
            groupid = "{}.0".format(str(z))
            
            if (groupid in source_ids) and (groupid in target_ids):
                # get all pt matches for this group (both within and outside group point matches)
                sourcematches = renderapi.pointmatch.get_matches_with_group(self.args['source_collection'], 
                                                                            groupid, 
                                                                            owner=self.args['match_owner'],
                                                                            render=self.render)
                targetmatches = renderapi.pointmatch.get_matches_with_group(self.args['target_collection'],
                                                                            groupid,
                                                                            owner=self.args['match_owner'],
                                                                            render=self.render)
                
                # get the qgroupIds in source matches
                sourcegroupIds = [m['qGroupId'] for m in sourcematches]

                # delete the matches between groupid and sourcegroupIds
                for sg in sourcegroupIds:
                    renderapi.pointmatch.delete_point_matches_between_groups(self.args['source_collection'],
                                                                             groupid,
                                                                             sg,
                                                                             owner=self.args['match_owner'],
                                                                             render=self.render)
                targetgroupIds = [m['qGroupId'] for m in targetmatches]
                for tg in targetgroupIds:
                    renderapi.pointmatch.delete_point_matches_between_groups(self.args['target_collection'],
                                                                             groupid,
                                                                             tg,
                                                                             owner=self.args['match_owner'],
                                                                             render=self.render)
                
                # import source matches into target collection
                renderapi.pointmatch.import_matches(self.args['target_collection'],
                                                    sourcematches,
                                                    owner=self.args['match_owner'],
                                                    render=self.render)
                # import target matches into source collection
                renderapi.pointmatch.import_matches(self.args['source_collection'],
                                                    targetmatches,
                                                    owner=self.args['match_owner'],
                                                    render=self.render)
                zvalues.append(z)

        self.output({"source_collection": self.args['source_collection'], 
                     "target_collection": self.args['target_collection'],
                     "swapped_zs": zvalues, 
                     "nonswapped_zs": set(self.args['zValues']).difference(zvalues)})

if __name__=="__main__":
    mod = SwapPointMatchesModule(input_data=example)
    mod.run()