import networkx as nx
import pandas as pd
import numpy as np
from hdfs3 import HDFileSystem
from scipy.stats import gamma
from datetime import datetime
from math import sin, cos, sqrt, atan2, radians,inf
from typing import Optional, Tuple, Dict, List, Set, Union, Any


##################################################################################################################
##################################################################################################################
#################################### Constants used in the routing  ##############################################
##################################################################################################################
##################################################################################################################

WALKING_SPEED    = 50.0 / 60.0 # walking speed of 50m/1min
FOOT_TTYPE       = 'Foot'
FOOT_TRIP_ID     = -1
INIT_TTYPE       = 'Init'
INIT_TRIP_ID     = -2

##################################################################################################################
##################################################################################################################
######################################### Type aliases  ##########################################################
##################################################################################################################
##################################################################################################################

ID    = str
Stop  = str
Name  = str
Time  = float
Graph = 'networkx.classes.multidigraph.MultiDiGraph'
EdgeProps = Dict[str,Any]

##################################################################################################################
##################################################################################################################
############################################ Helper functions ####################################################
##################################################################################################################
##################################################################################################################

class Utils:
    
    #-------------------------------------------------------------------------------------------------------------
    #------------------------------------------- Read/Write HDFS  ------------------------------------------------
    #-------------------------------------------------------------------------------------------------------------
    
    def load_hdfs_to_pandas(filename:str) -> pd.DataFrame:
        """
        Loads the required parquet file from HDFS into a data frame 
        """
        hdfs = HDFileSystem(host='hdfs://iccluster040.iccluster.epfl.ch', port=8020, user='ebouille') # impersonate ebouille to read the file
        files = hdfs.glob(f'/user/boesinge/finalproject/{filename}')
        df = pd.DataFrame()
        for file in files:
            if not 'SUCCESS' in file:
                with hdfs.open(file) as f:
                    df = df.append(pd.read_parquet(f))
        return df
    
    
    def save_graph_to_hdfs(G:Graph, stop_name_to_id:Dict[Name,ID],suffix='') -> None:
        """
        Saves the constructed Graph on HFDS in the pickle format
        """
        import pickle
        hdfs = HDFileSystem(host='hdfs://iccluster040.iccluster.epfl.ch', port=8020, user='ebouille')
        
        with hdfs.open('/user/boesinge/finalproject/graph' +suffix +'.pkl', 'wb') as f:
            graph_pickle = pickle.dumps(G)
            f.write(graph_pickle) 

        with hdfs.open('/user/boesinge/finalproject/stop_name_id' +suffix +'.pkl', 'wb') as f:
            stopnameid_pickle = pickle.dumps(stop_name_to_id)
            f.write(stopnameid_pickle) 
        
    def read_graph_from_hdfs(suffix='') -> Tuple[Graph, Dict[Name,ID]]:
        """
        Reads the Transport Graph from HFDS
        """
        import pickle
        hdfs = HDFileSystem(host='hdfs://iccluster040.iccluster.epfl.ch', port=8020, user='ebouille')
        
        with hdfs.open('/user/boesinge/finalproject/graph' +suffix +'.pkl', 'rb') as f:
            b = f.read()
            G = pickle.loads(b)

        with hdfs.open('/user/boesinge/finalproject/stop_name_id' +suffix +'.pkl', 'rb') as f:
            b = f.read()
            stopnameid = pickle.loads(b)
        
        return G, stopnameid
    
    #-------------------------------------------------------------------------------------------------------------
    #----------------------------------------- Timestamp <-> String ----------------------------------------------
    #-------------------------------------------------------------------------------------------------------------
    
    def print_timestamp(timestamp:Time, format_="%H:%M") -> str:
        """
        Nice printing of a timestamp for hours and minutes 
        """
        time = datetime.fromtimestamp(timestamp)
        return datetime.strftime(time, format_)
    
    MIN_TIME = datetime.timestamp(datetime.strptime("00:00:00","%H:%M:%S"))
    def to_timestamp(string:str) -> Time:
        """
        Parse dates string into a timestamp and substract the baseline to have positive values 
        """
        return datetime.timestamp(datetime.strptime(string,"%H:%M:%S")) - Utils.MIN_TIME
    
    
    #-------------------------------------------------------------------------------------------------------------
    #---------------------------------- Data formating and graph creation ----------------------------------------
    #-------------------------------------------------------------------------------------------------------------
    
    def format_edges(edges:pd.DataFrame) -> pd.DataFrame:
        """
        Massages the  edges df to be able to construct the graph
        (1) Keep only connections in the range 7h00 - 22h00
        (2) Parse string into timestapms
        (3) Compute travel time
        """
        def considered_dates(r,low=6,up=22) -> bool:
            """only connections in the range 7h00 - 22h00"""
            l = int(r.dep_time[:2])  # take hours from string
            h = int(r.arr_time[:2])  # take hours from string
            return (low < l) and (low < h) and (l < up) and (h < up)
        
        mask = edges.apply(lambda r: considered_dates(r),axis=1)                # create time mask
        edges = edges[mask]                                                     # apply it
        edges.dep_time = edges.dep_time.apply(lambda t: Utils.to_timestamp(t))  # parse string dates
        edges.arr_time = edges.arr_time.apply(lambda t: Utils.to_timestamp(t))  # parse string dates
        edges['travel_time'] =  edges.arr_time - edges.dep_time                 # compute travel time
        return edges
    
    def create_edges_foot(edges:pd.DataFrame) -> pd.DataFrame:
        """
        Computes all possible walking transfers and stores them into a dataframe
        """
        def calculate_dist(lat1,lon1,lat2,lon2):
            """ return flying distance in meters """
            # approximate radius of earth in km
            R = 6371.0
            # convert to radians (needed to apply next formula)
            lat1 = radians(lat1)
            lon1 = radians(lon1)
            lat2 = radians(lat2)
            lon2 = radians(lon2)

            # calculate the difference in coordinate
            delta_lat = lat1-lat2
            delta_lon = lon1-lon2
            # then we apply some trigonometry (from https://www.movable-type.co.uk/scripts/latlong.html)

            a = sin(delta_lat/2)**2 + cos(lat1)*cos(lat2)*sin(delta_lon)**2
            c = 2 * atan2(sqrt(a), sqrt(1 - a))
            distance = R * c * 1000
            return distance
        
        # compute the list of considered stops from the list of edges 
        stops_df = edges[['dep_stop_id','dep_stop_name','dep_lat','dep_lon']]\
                        .rename(columns={'dep_stop_id':'stop_id',
                                         'dep_stop_name':'stop_name',
                                         'dep_lat':'stop_lat',
                                         'dep_lon':'stop_lon'})\
                        .drop_duplicates()
        # for each stop we filter the 
        tmp = []
        for i in range(len(stops_df)):
            r = stops_df.iloc[i]
            stops_df['dist']      = stops_df.apply(lambda r2: calculate_dist(r.stop_lat,r.stop_lon,r2.stop_lat,r2.stop_lon),axis=1)
            stops_df['stop_id_2'] = r.stop_id
            # keep only only stops that are in the considered radius
            tmp.append(stops_df.query("1 < dist <= 500")) # note that we do not take self connections
        # concat results
        edges_foot =  pd.concat(tmp,ignore_index=True)
        # drop useless columns and rename others
        edges_foot = edges_foot.drop(columns=['stop_lat','stop_lon','stop_name']).rename(columns={'stop_id':'dep_stop_id','stop_id_2':'arr_stop_id'})
        # add travel time 
        edges_foot['travel_time'] = edges_foot.dist / WALKING_SPEED 
        # add Flag for foot ttype
        edges_foot['ttype'] = FOOT_TTYPE
        return edges_foot
    
    def create_graph(edges:pd.DataFrame,edges_foot:pd.DataFrame) -> Tuple[Graph, Dict[Name,ID]]:
        """
        Create the transport graph.
        
        Note that since we want to be able to query for a fixed arrival time, the edges stored in the graph are reversed compared to the `real` connection.
        """
        # add standard connections
        G = nx.from_pandas_edgelist(
            edges, 
            source="arr_stop_id", target="dep_stop_id", # inverse source and target to allow backward search
            edge_attr=[
                'dep_time', 
                'arr_time',
                'gamma',
                'ttype',
                'travel_time',
                'trip_id'
            ],
            create_using=nx.MultiDiGraph  #  multi directed graph
        )
        # For `Foot connections`:
        #    -  the fields `gamma` is irrelevant (set to `None`) 
        #    -  we cannot specify `dep_time` and `arr_time` at creations time (set to 0 initially) but they will be dynamically field in the traversal of the graph according to the current time. 
        stops = edges[['dep_stop_id', 'dep_stop_name','dep_lat','dep_lon']]\
                    .rename(columns={'dep_stop_id':'stop_id','dep_stop_name':'name','dep_lat':'lat','dep_lon':'lon'})\
                    .drop_duplicates()\
                    .set_index('stop_id')
        # add note attributes
        stop_map = stops.to_dict('index')
        stop_name_to_id = stops.reset_index().set_index('name').to_dict('index')
        nx.set_node_attributes(G, stop_map)
        edges_foot.apply(lambda r: G.add_edge(r.dep_stop_id, r.arr_stop_id,
                                           dep_time=0,
                                           arr_time=0,
                                           gamma = None,
                                           travel_time = r.travel_time,
                                           trip_id = FOOT_TRIP_ID,
                                           ttype =  r.ttype,
                                          ), axis=1);
        return G,stop_name_to_id