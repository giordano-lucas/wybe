from scipy.stats import gamma
from .utils import Time,EdgeProps
import numpy as np
# additional delay to make connection. Ex 1 min 30 are needed to exit train and station (or change of track)
EXTRA_TRANSFER_TIME = {  
        'Bus'           : 20,
        'Foot'          : 20,
        'Tram'          : 30,
        'S-Bahn'        :100,
        'Extrazug'      :100,
        'InterRegio'    :120,
        'Eurocity'      :120,         
        'RegioExpress'  :120,       
        'ICE'           :120, 
        'Eurostar'      :120, 
        'Intercity'     :120,
    }

class Delay:
    """
    Model of the delay distribution and computation
    Should only be used as Static function
    """
    
    #-------------------------------------------------------------------------------------------------------------
    #---------------------------------------- Private Helper functions -------------------------------------------
    #-------------------------------------------------------------------------------------------------------------

    def __compute_delay(
            arrival_time         : Time,    
            next_departure_time  : Time, 
            ttype                : str, 
            previous_route_id    : str,
            next_route_id        : str
        ) -> Time:
        """
        Delay computation given the arrival and departure times
        """
        # Allowed delay is simply the difference between next departure and current arrival time
        time_to_make_connection  = next_departure_time - arrival_time
        if (previous_route_id != next_route_id):                   # if we are changing route add additional delay
            time_to_make_connection -= EXTRA_TRANSFER_TIME[ttype]  # decrease of allowed connection time
        return time_to_make_connection
    
    def __connection_probability(
            delay             : Time, 
            gamma_params      : np.array, 
            ttype             : str, 
            previous_route_id : str,
            next_route_id     : str
        ) -> float:
        """ 
        (Wrapper) for connection_probability
        """
        if (ttype == 'Foot'                        # no randomness if we go by foot
            or previous_route_id == next_route_id  # or if stay in the same route
            or gamma_params is None):              # or if delay distribution is not available
            return 1.0 
        # proba of observing a delay < given delay
        return gamma(*gamma_params).cdf(delay)
    
    #-------------------------------------------------------------------------------------------------------------
    #------------------------------------ User should only call this function ------------------------------------
    #-------------------------------------------------------------------------------------------------------------
    
    def connection_probability(prev_props : EdgeProps, curr_props : EdgeProps) -> float:
        """
        Compute probability of making the connection based on the attributes of the previous and current connections
        """
        d = Delay.__compute_delay(
                arrival_time        = prev_props['arr_time'],
                next_departure_time = curr_props['dep_time'], 
                ttype               = prev_props['ttype'], 
                previous_route_id   = prev_props['trip_id'],
                next_route_id       = curr_props['trip_id']
            )
        proba = Delay.__connection_probability(
            delay               = d, 
            gamma_params        = prev_props['gamma'], 
            ttype               = curr_props['ttype'], 
            previous_route_id   = prev_props['trip_id'],
            next_route_id       = curr_props['trip_id']
        )
        return proba 