# dependencies for our dijkstra's implementation
from .utils import *
from .timedistance import *
from .delay import *
from .route import *
from math import sin, cos, sqrt, atan2, radians,inf
from queue import PriorityQueue
from math import inf
import networkx as nx

class Routing:
    """
    Modified Dijsktra
    
    @attribute G (Graph)                       : transport network graph
    @attribute stop_name_to_id (Dict[Name,ID]) : dictionnary from stop names to ids
    """
    #-------------------------------------------------------------------------------------------------------------
    #------------------------------------------- Object creation  ------------------------------------------------
    #-------------------------------------------------------------------------------------------------------------
    
    MAX_WAITING_TIME = 45 * 60  # maximum waiting time 
    
    def __init__(self, G:Graph, stop_name_to_id:Dict[Name,ID]):
        """
        Route constructor 
        """
        self.G = G
        self.stop_name_to_id = stop_name_to_id

    #-------------------------------------------------------------------------------------------------------------
    #------------------------------------------- Simple planning  ------------------------------------------------
    #-------------------------------------------------------------------------------------------------------------
    
    def stochastic_dijkstra(self, 
                            start: Union[Name,ID],     # start node (either name or id. If id, names_format to False)
                            end: Union[Name,ID],       # end node (either name or id. If id, names_format to False)
                            arr_time:Union[str,Time],  # target arrival time (ex '12:45:00' or timestamp)
                            threshold = 0.8,           # target probability of making all connections in time
                            names_format=True          # If we want to use IDs for start and end set to False
                           ) -> Optional[Route]:
        """
        Modified Dijkstra's shortest path algorithm to include probabilities
        """
        def build_route() -> Optional[Route]:
            """
            Get the shortest path of nodes by going backwards through prev list
            """
            if start not in prev.keys():
                return None
            
            route = Route(self.G)
            node = start
            dist = distances[start]
            path = []
            while node != end:
                route.append(node,dist)
                node = prev[node]
                dist = distances[node]
            route.append(node,dist) 
            return route
       
        def neighbours(stop:ID):
            """
            Returns valid neighbors (edges) of a stop. Valid neighbors must satisfy time and probability constraints and no two walking edges in a row.
            """
            prev_props            = distances[stop].prev_props
            previous_dep_time     = distances[stop].previous_dep_time()
            current_best_dep_time = arr_time - distances[start]()
            possible_neighbours   = self.G.out_edges(stop,data=True) # get edges with properties
            
            def time_filter(e:Tuple[ID,ID,EdgeProps]) -> bool:
                """
                Function used to filter the neighbors (edges) of the stop. An edge is valid if it is a walking edge (except if it is the second in a row)
                or if it is in the time range, meaning that the arrival time is sufficiently early to not miss the connection, but sufficiently late to not wait too much. 
                It also filters edges that have no chance of yielding a better result than the best we have so far, and the edges that have a probability less than the threshold. 
                """
                u,v,props       = e # unpack edge
                isFoot          = lambda: props['ttype'] == 'Foot'                                                         # True if it is a walking edge
                consecutiveFoot = lambda: isFoot() and prev_props['ttype'] == 'Foot'                                       # True if it is the second walking edge in a row
                inTimeRange     = lambda: (previous_dep_time >= props['arr_time']                                          # True if the arrival time is sufficiently early
                                        and props['arr_time'] >= previous_dep_time - Routing.MAX_WAITING_TIME              # True if the arrival time is sufficiently late
                                        and props['dep_time'] >= current_best_dep_time)                                    # True if it has a chance of beating the best result we have so far
                # reverse props to compute pre arrival delay
                enoughProba     = lambda:Delay.connection_probability(prev_props=props,curr_props=prev_props) >= threshold # True if the probability is higher than the threshold
                
                return (isFoot() or inTimeRange()) and not consecutiveFoot() and enoughProba()
                     
            return filter(time_filter,possible_neighbours)
        
        #  Initialise variables and format input 
        if type(arr_time)==str:                            # convert to timestamp if initially given as strings
            arr_time = Utils.to_timestamp(arr_time)        
        if names_format:                                   # If names are given as strings => get their ids
            start = self.stop_name_to_id[start]['stop_id'] 
            end   = self.stop_name_to_id[end]['stop_id']
            
        prev = {}                                                                   # predecessor of current node on shortest path 
        distances = {v: TimeDistance(time=arr_time) for v in nx.nodes(self.G)}      # initialize distances from end to any given node
        visited = set()                                                             # nodes we've visited
        # prioritize nodes from start -> node with the shortest distance!
        queue = PriorityQueue()                        
        distances[end].updated()                                                    # dist from end -> end is zero
        queue.put((distances[end], end))                                               # add end node for exploration
        # main search phase of algorithm
        while not queue.empty():
            _, curr = queue.get()
            visited.add(curr)
            for _,neighbor,properties in neighbours(curr):              # look at curr's adjacent nodes
                new_dist = distances[curr] + properties                 # if we found a shorter path 
                if new_dist < distances[neighbor]:                      # update the distance, we found a shorter one!
                    distances[neighbor] = new_dist.updated()            # update the previous node to be prev on new shortest path
                    prev[neighbor] = curr                               # if we haven't visited the neighbor
                    if neighbor not in visited:                         # insert into priority queue and mark as visited
                        visited.add(neighbor)
                        queue.put((distances[neighbor],neighbor))          # prioritize search on small distances
        # compute the route 
        return build_route()
    
    #-------------------------------------------------------------------------------------------------------------
    #------------------------------------------- Robust planning  ------------------------------------------------
    #-------------------------------------------------------------------------------------------------------------
    
    def robust(self,
                    start   : str,             # start node (either name or id. If id, names_format to False)
                    end     : str,             # end node (either name or id. If id, names_format to False)
                    arr_time: str,             # target arrival time (ex '12:45:00' or timestamp)
                    threshold = 0.8,           # target probability of making all connections in time):
                    max_iter  = 10,            # max number of iterations allowed to find a path
                    number_of_routes = 1,      # number of different routes we want to compute
                    verbose = False            # allow for nice iteration printing if required
                   )  -> Optional[List[Route]]:
        """
        Tries to find routes from start to end with success probability higher than threshold. It repeatedly computes the fastest route, 
        store it if the success probability is higher than the threshold, and delete the edge that induce the smallest probability. 
        It stops when max_iter iterations have been done or when number_of_routes valid routes have been found.
        """
        routes_list = []
        graph = self.G.copy()
        # compute fastest route
        route = self.stochastic_dijkstra(start, end, arr_time, threshold)
        if route is None:
            # no route between start and end
            return None
        # probability of the route, and properties of the edge with smallest probability on the route
        proba, (u,v,props) = route.success_proba()
        if verbose :
            print(f"Iteration : 1 || Proba : {proba}")
        
        if proba >= threshold:
            # we have found a valid route
            routes_list.append(route)
        
        def find_edge_key(u : ID, v : ID, props: EdgeProps)  -> Optional[ID]:
            """
            Find in the graph the key of the edge from u to v that has the properties props
            """
            # test whether e is the edge we are looking for
            isSameEdge = lambda e: ((edges[e]['dep_time'] == props['dep_time'] and 
                                    edges[e]['arr_time']  == props['arr_time'] and 
                                    edges[e]['trip_id']   == props['trip_id']) 
                                or (props['ttype'] == 'Foot' and edges[e]['ttype'] == 'Foot')) 
            #iterate on edges between u and v to find the one we want
            edges = graph[u][v]
            for e in edges:
                if isSameEdge(e):
                    return e
            return None
        
        # Try to find routes that matches the wished probability threshold
        i = 1
        while i < max_iter and len(routes_list) < number_of_routes :
            # find the key of the least probable edge
            to_remove = find_edge_key(u,v,props) 
            # remove it from the graph
            graph.remove_edge(u,v,key=to_remove)
            # rerun the routing algorithm
            new_routing = Routing(graph, self.stop_name_to_id)
            new_route   = new_routing.stochastic_dijkstra(start, end, arr_time, threshold)
            
            if new_route is None:
                # there are no more routes between start and end. We just return the list we have so far.
                if not routes_list :
                    # if the list is empty, we add the most robust route we have
                    if verbose :
                        print(f"No path found satisfying {threshold} probability")
                    routes_list.append(route) # Add best route we have
                return routes_list
            
            # new probability of the route, and properties of the edge with smallest probability
            new_proba, (u,v,props) = new_route.success_proba()

            if verbose :
                  print(f"Iteration : {i+1} || Proba : {new_proba:2.3f}")
            
            # if the probability is higher than the threshold, we add the route to the list
            if new_proba >= threshold:
                routes_list.append(new_route)

            # update current best route
            if proba < new_proba:
                proba = new_proba
                route = new_route
            i += 1
            
        # if we have not found any route satisfying the threshold, we return the best we have
        if not routes_list :
            if verbose :
                print(f"No path found satisfying {threshold} probability in {max_iter} trials")
            routes_list.append(route) # Add most robust path found
            
        return routes_list