from math import inf
from .utils import * 


class TimeDistance:
    """
    Distance metric to minimize in the Dijsktra algorithm
    
    It essentially represents the sum of travel times but stores additional information about previous trips
    
    @attribute first (bool)      : is set to true if the distance hasn't be assigned to a path yet (and should therefore be infite)
                                   users should call `updated` to change behavior
    @attribute cum_time (Time)   : sum of travel and waiting time of the route => equal to the global travel time of the route
    @attribute prev_props (dict) : cache of edges properties (from the Networkx graph) that were previously considered in the Dijsktra 
                                   exploration. This is usefull to compute the delays since, for instance, 'Foot edges' have a probability 
                                   of one of making the connection.
                                   
    """
    #-------------------------------------------------------------------------------------------------------------
    #------------------------------------------ Creation and update  ---------------------------------------------
    #-------------------------------------------------------------------------------------------------------------
            
    def __init__(self, first=True, cum_time=0, prev_props=None,time=0):
        """
        Consruct the time distance
        
        /!\ Note that intially since we do not have a previous edge, we construct a `INIT_PROPS`
            object that does not "break" the recurrence properties of the class.
                - For example : we assume that we did not move before the initial stop 
                  (so that arrival time == departure time)
                - INIT_TTYPE and INIT_TRIP_ID are flags that are different from the other values
                  present in the graph.
        """
        self.first      = first
        self.cum_time   = cum_time
        if prev_props is None:
            INIT_PROPS = {
                    'gamma'   : None,
                    'arr_time': time,
                    'dep_time': time,
                    'ttype'   : INIT_TTYPE,
                    'trip_id' : INIT_TRIP_ID
                }
            self.prev_props = INIT_PROPS
        else:
            self.prev_props = prev_props
            
    
    def updated(self) -> None:
        """
        Encode the fact that the distance has been assigned once (should not longer be infinite)
        """
        self.first = False
        return self
    
    #-------------------------------------------------------------------------------------------------------------
    #---------------------------------------- Cost access and comparator  ----------------------------------------
    #-------------------------------------------------------------------------------------------------------------
    
    def __call__(self) -> Time:
        """
        Cost value of Distance function (initially infinite)
        """
        return inf if self.first else self.cum_time
    
    def __lt__(self, other) -> bool:
        """
        Need comparision method for the priority queue.
        """
        return self() < other()
    
    def __add__(self,props:EdgeProps):
        """
        Define semantics of addition operation on TimeDistances.
        Namely, next travel time = previous travel time + Waiting time + edge travel time
        
        /!\ In the graph arr_time and dep_time are equal 0 for foot edges since they are not
            linked to any fixed schedule (can walking at any time) and we manually have to set
            the props to the current timing of the graph.
        """
        # for walking edges => update departure and arrival time
        if (props['ttype'] == 'Foot'):
            props = props.copy()
            props['dep_time'] = self.prev_props['dep_time'] - props['travel_time']
            props['arr_time'] = self.prev_props['dep_time'] 
        # create updated distance object
        return TimeDistance(
            first          = self.first, 
            cum_time       = self.cum_time  + self.prev_props['dep_time'] - props['arr_time'] + props['travel_time'] ,
            prev_props     = props
        )
    
    #-------------------------------------------------------------------------------------------------------------
    #------------------------------------------------- Accessors  ------------------------------------------------
    #-------------------------------------------------------------------------------------------------------------
    
    def previous_dep_time(self):
        """
        Returns the previous departure time
        """
        return self.prev_props['dep_time']
