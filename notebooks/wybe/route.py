from .routing import *
from .route import *
from .timedistance import *
from .delay import *
from .utils import *

class Route:
    """
    Class that encodes a Route returned by the Routing algorithm
    
    @attribute G           : Transport  Graph
    @attribute connections : list of stops to take to arrive from source to end
    @attribute distances   : list of iterative distances from source to end
    """
    
    #-------------------------------------------------------------------------------------------------------------
    #------------------------------------------------- Building  -------------------------------------------------
    #-------------------------------------------------------------------------------------------------------------
    
    def __init__(self,G:Graph):
        """
        Constructor : initialise with empty route
        """
        self.G:Graph                      = G
        self.connections:List[ID]         = []
        self.distances:List[TimeDistance] = []
    
    def append(self, node:ID, dist: TimeDistance) -> None:
        """
        Add one connection to the route (iterative builing)
        """
        self.connections.append(node)
        self.distances.append(dist)
        
    #-------------------------------------------------------------------------------------------------------------
    #------------------------------------------------ Accessors  -------------------------------------------------
    #-------------------------------------------------------------------------------------------------------------
    
    def success_proba(self) -> (float,(ID,ID,EdgeProps)):
        """
        Compute the sucess probability of the route assuming independence between connections
        """
        assert len(self.connections)!=0,'Empty route'
        # initial proba is 1
        proba       = 1.0
        least_proba = 1.0
        for i, v in enumerate(zip(self.connections, self.connections[1:])):  # iterate over all connections
            dep_stop, arr_stop = v
            next_proba = Delay.connection_probability(                       # compute probability
                self.distances[i].prev_props,
                self.distances[i+1].prev_props
            )
            proba = proba * next_proba                                       # update assuming independence
            
            if next_proba <= least_proba:
                least_proba = next_proba
                least_proba_edge = (arr_stop, dep_stop, self.distances[i].prev_props)
        return proba, least_proba_edge
        
    def dep_time(self) -> Time:
        """
        Return departure time 
        """
        assert len(self.connections)!=0,'Empty route'
        return self.distances[0].prev_props['dep_time']
    
    def travel_time(self) -> Time:
        """
        Return travel time 
        """
        assert len(self.connections)!=0,'Empty route'
        return self.distances[0].cum_time
    
    def arr_time(self) -> Time:
        """
        Return arrival time
        """
        assert len(self.connections)!=0,'Empty route'
        return self.travel_time() + self.distances[0].prev_props['dep_time']
    
    #-------------------------------------------------------------------------------------------------------------
    #--------------------------------------------- Output and printing  ------------------------------------------
    #-------------------------------------------------------------------------------------------------------------

    def to_Pandas(self) -> pd.DataFrame:
        """
        Cast route into a DataFrame (used in Visualisation)
        
        """
        d = {
            'ttype':[], 
            'trip_id':[], 
            'dep_stop_id':[],
            'arr_stop_id':[], 
            'dep_time':[], 
            'arr_time':[], 
            'dep_stop_name':[], 
            'arr_stop_name':[],
            'ttype':[], 
            'dep_lat':[], 
            'dep_lon':[], 
            'arr_lat':[],
            'arr_lon':[], 
            'travel_time':[]
        }
        for i, v in enumerate(zip(self.connections, self.connections[1:])):
            dep_stop, arr_stop = v
            d['ttype'].append(self.distances[i].prev_props['ttype'])
            d['trip_id'].append(self.distances[i].prev_props['trip_id']) 
            d['dep_stop_id'].append(dep_stop)
            d['arr_stop_id'].append(arr_stop) 
            d['dep_time'].append(self.distances[i].prev_props['dep_time']) 
            d['arr_time'].append(self.distances[i].prev_props['arr_time']) 
            d['dep_stop_name'].append(self.G.nodes[dep_stop]['name']) 
            d['arr_stop_name'].append(self.G.nodes[arr_stop]['name'])
            d['dep_lat'].append(self.G.nodes[dep_stop]['lat'])
            d['dep_lon'].append(self.G.nodes[dep_stop]['lon']) 
            d['arr_lat'].append(self.G.nodes[arr_stop]['lat'])
            d['arr_lon'].append(self.G.nodes[arr_stop]['lon']) 
            d['travel_time'].append(self.distances[i].prev_props.get('travel_time',0))
            
        df = pd.DataFrame(data=d)
        #give unique id to foot transfers
        df.loc[df.ttype == 'Foot', 'trip_id'] = df.loc[df.ttype == 'Foot', 'trip_id'].index
        return df
    
    def __str__(self) -> str:
        """
        Print some info about the current route
        """
        
        s = f"""
        =========== Route info  =========
        Departure time      : {Utils.print_timestamp(self.dep_time())}
        Arrival   time      : {Utils.print_timestamp(self.arr_time())}
        ---------------------------------
        Success probability : {self.success_proba()[0]:2.3f}
        Travel    time      : {Utils.print_timestamp(self.travel_time())}
        =========== Connections =========
        """
        
        for i, v in enumerate(zip(self.connections, self.connections[1:])):
            dep_stop, arr_stop = v 
            curr_props = self.distances[i].prev_props
            prev_props = self.distances[i+1].prev_props
            
            s = s + f"""
            At stop : {self.G.nodes[dep_stop]['name']} and at {Utils.print_timestamp(curr_props['dep_time'])}
            """
            ttype = curr_props['ttype']
            if ttype == 'Foot':
                s = s +  f"walk {round(curr_props['travel_time'] * WALKING_SPEED)} m to"
            else:
                s = s +  f"take the {ttype} {curr_props['trip_id']} to"
            s = s + f""" {self.G.nodes[arr_stop]['name']} which arrives at {Utils.print_timestamp(curr_props['arr_time'])}
            Wait {(prev_props['dep_time'] - curr_props['arr_time']) // 60} min
            """
        
        return s 