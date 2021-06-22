# Wybe : a Robust Journey Planner

**Executive summary:** build a robust SBB journey planner for the Zürich area

----
## Content

* [Problem Motivation](#Problem-Motivation)
* [Problem Description](#Problem-Description)
* [Solution Desription](#Solution-description)
* [How to run the code](#How-to-run-the-code)
* [Video Presentations](#Video-Presentations)
* [Dataset Description](#Dataset-Description)

    - [Actual data](#Actual-data)
    - [Timetable data](#Timetable-data)
    - [Stations data](#Stations-data)
    - [Misc data](#Misc-data)

* [References](#References)

----

## Problem Motivation

Imagine you are a regular user of the public transport system, and you are checking the operator's schedule to meet your friends for a class reunion.
The choices are:

1. You could leave in 10mins, and arrive with enough time to spare for gossips before the reunion starts.

2. You could leave now on a different route and arrive just in time for the reunion.

Undoubtedly, if this is the only information available, most of us will opt for option 1.

If we now tell you that option 1 carries a fifty percent chance of missing a connection and be late for the reunion. Whereas, option 2 is almost guaranteed to take you there on time. Would you still consider option 1?

Probably not. However, most public transport applications will insist on the first option. This is because they are programmed to plan routes that offer the shortest travel times, without considering the risk factors.

[top](#Content)

----

## Problem Description

In repository we built our own _robust_ public transport route planner to improve on that. We used the SBB dataset (See next section: [Dataset Description](#dataset-description)).

Given a desired arrival time, our route planner will compute the fastest route between departure and arrival stops within a provided confidence tolerance expressed as interquartiles.
For instance, "what route from _A_ to _B_ is the fastest at least _Q%_ of the time if I want to arrive at _B_ before instant _T_". Note that *confidence* is a measure of a route being feasible within the travel time computed by the algorithm.

The output of the algorithm is a list of routes between _A_ and _B_ and their confidence levels. The routes must be sorted from latest (fastest) to earliest (longest) departure time at _A_, they must all arrive at _B_ before _T_ with a confidence level greater than or equal to _Q_. Ideally, it should be possible to visualize the routes on a map with straight lines connecting all the stops traversed by the route.

In order to answer this question, we :

- Modeled the public transport infrastructure for our route planning algorithm using the SBB data.
- Built a predictive model using the historical arrival/departure time data, and optionally other sources of data.
- Implemented a robust route planning algorithm using this predictive model.
- Tested and validated our results.
- Implemented a simple Jupyter-based visualization to demonstrate our method, using the Jupyter dashboard [Voilà](https://voila.readthedocs.io/en/stable/).

Since solving this problem accurately is quite difficult, we wored with a few **simplifying assumptions**:

- We only consider journeys at reasonable hours of the day, and on a typical business day, and assuming the schedule of May 13-17, 2019.
- We allow short (total max 500m "As the Crows Flies") walking distances for transfers between two stops, and assume a walking speed of _50m/1min_ on a straight line, regardless of obstacles, human-built or natural, such as building, highways, rivers, or lakes.
- We only consider journeys that start and end on known station coordinates (train station, bus stops, etc.), never from a random location. However, walking from the departure stop to a nearby stop is allowed.
- We only consider stops in a 15km radius of Zürich's train station, `Zürich HB (8503000)`, (lat, lon) = `(47.378177, 8.540192)`.
- We only consider stops in the 15km radius that are reachable from Zürich HB, either directly, or via transfers through other stops within the same 15km area.
- There is no penalty for assuming that delays or travel times on the public transport network are uncorrelated with one another.
- Once a route is computed, a traveller is expected to follow the planned routes to the end, or until it fails (i.e. miss a connection).
- The planner will not need to mitigate the traveller's inconvenience if a plan fails. Two routes with identical travel times under the uncertainty tolerance are equivalent, even if the outcome of failing one route is much worse for the traveller than failing the other route, such as being stranded overnight on one route and not the other.
- All other things being equal, we will prefer routes with the minimum walking distance, and then minimum number of transfers.
- We assumed that the timetables remain unchanged throughout the 2018 - 2020 period.

[top](#Content)

----

## Solution Description

### Methodology

The main idea is to use historical SBB data to model delays. Then, given a route we can output the probability of making all connections and use this information to propose robust routes to the user with probabilistic guarantees.

#### Graph modeling

We model the public transport network by a graph, where each stop is a node and each trip between stops is an edge. Note that there may be multiple edges between two nodes. Each edge is characterized by a departure time, an arrival time, a transport type and a probability distribution for its delay. We also consider that a user can walk between two stops that are less than five hundred meters apart, hence we add the corresponding edges. More detailed information can be foud in the corresponding notebooks.

> Note that since we want to be able to query for a fixed arrival time, the edges stored in the graph are reversed compared to the 'real' connection.

#### Delay modeling

The data used for the delay modeling is obtained from both the istdaten and the timetable datasets.

Delays are modelled by gamma distributions. This is due to the fact that it is a simple distribution, which we can represent with only two parameters,
and it is a more general distribution compared to the exponential distribution : The highest density of the distribution doesn't have to be for x=0.

Unfortunately, not all stops in the timetable are present in the istdaten dataset : this is due to some operators not uploading their delay data to the SBB.

In order to fix this problem, we decided to fit gammas with two granularity levels :
- A coarse grained fit for the stops where we don't have any delay data
- A fined grained fit for stops where we have the istdaten data available

During our Data Exploration, we noticed that two parameters which are quite important in determining delays are the Transport Group (Train, Tram, S-Bahn, etc..)
 and Time Category (in the notebooks, you can see the Hourly categories we selected, representing the Early Morning, Morning, Noon ... time periods)
 
The coarse grained fit thus simply fits a gamma per (Transport Group, Time Category) Pair.

Then, since the fine-grained fit only uses Data from Zürich, and we still wanted robustness (some stops don't have many delays recorded in istdaten), we performed a clustering.
The clustering uses the percentile of delays for each tuple of (Transport Group, Departure Stop, Arrival Stop), to assign clusters. One clustering is performed for each Time category, for a total of 5 clusterings.
Then, gammas are fit for each cluster (where we use the clusterings to join many delays together), and joined back to each tuple of (Transport Group, Departure Stop, Arrival Stop).

#### Notebooks

The notebooks used are **sample_istdaten**, **gamma_fitting**, and **time_transport_cat**.

The sample_istdaten should be run first (if you care about reproducibility), to generate the stratified sampled datasets used for the other notebooks.
It generates one sampled dataset per Time Category, and one per (Time Category, Transport Group) pair.

The time_transport_cat can than be run, using sampled data, to show graphs and our reasoning on the selection of specific Time Categories and Transport Groups.

Finally, the gamma_fitting notebook can be run. It contains both methods of gamma fitting, and our reasoning for the fit.

#### Routing algorithm

Our main routing algorthim is a derivation from the well-known Dijkstra Shortest path algorithm to which we added a time-dimension.

The main idea is to :
* First find the shortest route
* Then compute the probability of making all individual connections using the trip-independence assumption and our previously computed delay distributions.
* Finally, we check if its success probability is higher that the given threshold. If it is not the case, we will iteratively remove from the Graph the edges having the lowest probability on the path and start over
* In the end, either we exhausted our iteration budget and we say that no path exists given the threshold or we return all the distincts paths meeting the requirements and sort them from lastest to earliest and by the number of connections.

In terms of implementation details, we defined the cost function on edges to be the traveling time between the stops + the waiting time before the next connection. We can also perform some dynamic pruning at the neighbour search phase of algorithm. 
Indeed, the algorithm keeps track of the current time so, for instance, if we are at 9AM we do not have to consider any routes leaving after that time (remember that the graph is reversed). Furthermore, due to the independence, we observe that if a single edge gives a success proba < threshold the overall path will not meet the probability requirements and we can filter out these edges to speed up the computation.

##### Assumptions
We chose to make the following additional assumption to perform the routing : 
* Maximum waiting time of 45 minutes at a stop 
* Only connections between 6 AM and 10 PM are considered
* Add additional delay to make connection. Ex 1 min 30 are needed to exit train and station (or change of track)

#### Robustness implementation
We first run the routing algorithm once and get the fastest route found. Then we compute the route's probability of not missing any connection. If this probability is higher than the threshold, we keep the route as valid. Then, we remove the edge with the smallest probability on the path and rerun the algorithm. We repeat this until we have found enough valid routes (e.g 3) or until we have reached the maximum number of iterations.

### Conclusion

This first version of our planner already allows us to have promising results and a tool that we can use in everyday life. But some refinements can be made to improve the performance of our model. To improve the prediction of delays, we could for instance improve the fit of the gammas by increasing the granularity of the clustering. Better delays will allow us to better approximate the reality. 

Another area of improvement is to modify the cost function to take into account other parameters directly in the djikstra algorithm and potentially to be able to prune even more efficiently.

[top](#Content)

## How to run the code

To test our code, you can do it in several ways. From the notebook viz, you can directly run all the cells to have access to our planner.  Another way to test our planner is to run the javascript cell, this cell launches a voila page that will allow you to test our planner. You need to select a departure and arrival stop from the list of stops, as well as an arrival time between 8:00 and 22:00, and finally a confidence value. Then you can click on go to trigger the algorithm.

For a quick tutorial, we invite you to watch our video presentation where you can find a demo of our tool at the end of the video.  

### Repository organisation

- Notebook 

In order to be able to run our notebooks, you should have a folder structure similar to:

    .
    ├── data                                      
    │ ├── stops.csv      
    ├── figs    
    │ ├── journeys.png
    │ ├── journeys.svg                             
    ├── notebooks 
    │ ├── Validation_images
    │ │ ├── ...
    │ ├── wybe
    │ │ ├── __init__.py
    │ │ ├── delay.py
    │ │ ├── route.py
    │ │ ├── routing.py
    │ │ ├── timedistance.py
    │ │ ├── utils.py
    │ ├── arrival_routing.ipynb
    │ ├── distances.ipynb
    │ ├── gamma_fitting.ipynb
    │ ├── GraphCreation&Validation.ipynb
    │ ├── sample_istdaten.ipynb
    │ ├── time_transport_cat.ipynb
    │ ├── vis.ipynb
    │ ├── ...
    ├── Dockerfile                         
    ├── environment.yml               
    ├── README.md   
    └── requirements.txt

### Dependencies

You should have the following additional libraries installed

| Library                         |
|:--------------------------------| 
| PyArrow                         |
| NetworkX                        |

[top](#Content)

## Video Presentations

The video presentation of the project (google drive) can be found [here](https://drive.google.com/file/d/16QK5hjkC1RE1bGkhKn8MV9ab4nk8zne8/view?usp=sharing).
The moodle upload is available [here](https://moodle.epfl.ch/pluginfile.php/2909146/assignsubmission_file/submission_files/392460/GroupEVideo.mp4?forcedownload=1)

[top](#Content)

----
## Dataset Description

For this project we will use the data published on the [Open Data Platform Mobility Switzerland](<https://opentransportdata.swiss>).

We will use the SBB data limited around the Zurich area, focusing only on stops within 15km of the Zurich main train station.

#### Actual data

Students should already be familiar with the [istdaten](https://opentransportdata.swiss/de/dataset/istdaten). A daily feed is available
from the open data platform mobility, and [google drive archives](https://drive.google.com/drive/folders/1SVa68nJJRL3qgRSPKcXY7KuPN9MuHVhJ).

The 2018 to 2020 data is available as a Hive table in ORC format on our HDFS system, under `/data/sbb/orc/istdaten`.

See assignments and exercises of earlier weeks for more information about this data, and methods to access it.

We provide the relevant column descriptions below.
The full description of the data is available in the opentransportdata.swiss data [istdaten cookbooks](https://opentransportdata.swiss/en/cookbook/actual-data/).
If needed you can translate the column names and descriptions from
German to English with an automated translator, such as [DeepL](<https://www.deepl.com>).

- `BETRIEBSTAG`: date of the trip
- `FAHRT_BEZEICHNER`: identifies the trip
- `BETREIBER_ABK`, `BETREIBER_NAME`: operator (name will contain the full name, e.g. Schweizerische Bundesbahnen for SBB)
- `PRODUCT_ID`: type of transport, e.g. train, bus
- `LINIEN_ID`: for trains, this is the train number
- `LINIEN_TEXT`,`VERKEHRSMITTEL_TEXT`: for trains, the service type (IC, IR, RE, etc.)
- `ZUSATZFAHRT_TF`: boolean, true if this is an additional trip (not part of the regular schedule)
- `FAELLT_AUS_TF`: boolean, true if this trip failed (cancelled or not completed)
- `HALTESTELLEN_NAME`: name of the stop
- `ANKUNFTSZEIT`: arrival time at the stop according to schedule
- `AN_PROGNOSE`: actual arrival time (when `AN_PROGNOSE_STATUS` is `GESCHAETZT`)
- `AN_PROGNOSE_STATUS`: look only at lines when this is `GESCHAETZT`. This indicates that `AN_PROGNOSE` is the measured time of arrival.
- `ABFAHRTSZEIT`: departure time at the stop according to schedule
- `AB_PROGNOSE`: actual departure time (when `AN_PROGNOSE_STATUS` is `GESCHAETZT`)
- `AB_PROGNOSE_STATUS`: look only at lines when this is `GESCHAETZT`. This indicates that `AB_PROGNOSE` is the measured time of arrival.
- `DURCHFAHRT_TF`: boolean, true if the transport does not stop there

Each line of the file represents a stop and contains arrival and departure times. When the stop is the start or end of a journey, the corresponding columns will be empty (`ANKUNFTSZEIT`/`ABFAHRTSZEIT`).
In some cases, the actual times were not measured so the `AN_PROGNOSE_STATUS`/`AB_PROGNOSE_STATUS` will be empty or set to `PROGNOSE` and `AN_PROGNOSE`/`AB_PROGNOSE` will be empty.

#### Timetable data

We have copied the  [timetable](https://opentransportdata.swiss/en/cookbook/gtfs/) to HDFS.

We are in the process of converting the files in an easy to query table form, and will keep you updated when the tables are available.

You will find there the timetables for the years [2018](https://opentransportdata.swiss/en/dataset/timetable-2018-gtfs), [2019](https://opentransportdata.swiss/en/dataset/timetable-2019-gtfs) and [2020](https://opentransportdata.swiss/en/dataset/timetable-2020-gtfs).
The timetables are updated weekly. It is ok to assume that the weekly changes are small, and a timetable for
a given week is thus the same for the full year - you can for instance use the schedule of May 13-17, 2019, which was
a typical week for the year.

Only GTFS format has been copied on HDFS, the full description of which is available in the opentransportdata.swiss data [timetable cookbooks](https://opentransportdata.swiss/en/cookbook/gtfs/).
The more courageous who want to give a try at the [Hafas Raw Data Format (HRDF)](https://opentransportdata.swiss/en/cookbook/hafas-rohdaten-format-hrdf/) format must contact us.

We provide a summary description of the files below. The most relevant files are marked by (+):

* stops.txt(+):

    - `STOP_ID`: unique identifier (PK) of the stop
    - `STOP_NAME`: long name of the stop
    - `STOP_LAT`: stop latitude (WGS84)
    - `STOP_LON`: stop longitude
    - `LOCATION_TYPE`:
    - `PARENT_STATION`: if the stop is one of many collocated at a same location, such as platforms at a train station

* stop_times.txt(+):

    - `TRIP_ID`: identifier (FK) of the trip, unique for the day - e.g. _1.TA.1-100-j19-1.1.H_
    - `ARRIVAL_TIME`: scheduled (local) time of arrival at the stop (same as DEPARTURE_TIME if this is the start of the journey)
    - `DEPARTURE_TIME`: scheduled (local) time of departure at the stop 
    - `STOP_ID`: stop (station) identifier (FK), from stops.txt
    - `STOP_SEQUENCE`: sequence number of the stop on this trip id, starting at 1.
    - `PICKUP_TYPE`:
    - `DROP_OFF_TYPE`:

* trips.txt:

    - `ROUTE_ID`: identifier (FK) for the route. A route is a sequence of stops. It is time independent.
    - `SERVICE_ID`: identifier (FK) of a group of trips in the calendar, and for managing exceptions (e.g. holidays, etc).
    - `TRIP_ID`: is one instance (PK) of a vehicle journey on a given route - the same route can have many trips at regular intervals; a trip may skip some of the route stops.
    - `TRIP_HEADSIGN`: displayed to passengers, most of the time this is the (short) name of the last stop.
    - `TRIP_SHORT_NAME`: internal identifier for the trip_headsign (note TRIP_HEADSIGN and TRIP_SHORT_NAME are only unique for an agency)
    - `DIRECTION_ID`: if the route is bidirectional, this field indicates the direction of the trip on the route.
    
* calendar.txt:

    - `SERVICE_ID`: identifier (PK) of a group of trips sharing a same calendar and calendar exception pattern.
    - `MONDAY`..`SUNDAY`: 0 or 1 for each day of the week, indicating occurence of the service on that day.
    - `START_DATE`: start date when weekly service id pattern is valid
    - `END_DATE`: end date after which weekly service id pattern is no longer valid
    
* routes.txt:

    - `ROUTE_ID`: identifier for the route (PK)
    - `AGENCY_ID`: identifier of the operator (FK)
    - `ROUTE_SHORT_NAME`: the short name of the route, usually a line number
    - `ROUTE_LONG_NAME`: (empty)
    - `ROUTE_DESC`: _Bus_, _Zub_, _Tram_, etc.
    - `ROUTE_TYPE`:
    
**Note:** PK=Primary Key (unique), FK=Foreign Key (refers to a Primary Key in another table)

The other files are:

* _calendar-dates.txt_ contains exceptions to the weekly patterns expressed in _calendar.txt_.
* _agency.txt_ has the details of the operators
* _transfers.txt_ contains the transfer times between stops or platforms.

Figure 1. better illustrates the above concepts relating stops, routes, trips and stop times on a real example (route _11-3-A-j19-1_, direction _0_)


 ![journeys](figs/journeys.png)
 
 _Figure 1._ Relation between stops, routes, trips and stop times. The vertical axis represents the stops along the route in the direction of travel.
             The horizontal axis represents the time of day on a non-linear scale. Solid lines connecting the stops correspond to trips.
             A trip is one instances of a vehicle journey on the route. Trips on same route do not need
             to mark all the stops on the route, resulting in trips having different stop lists for the same route.
             

#### Stations data

For your convenience we also provide a consolidated liste of stop locations in ORC format under `/data/sbb/orc/geostops`. The schema of this table is the same as for the `stops.txt` format described earlier.

Finally, you can find also additional stops data in [BFKOORD_GEO](https://opentransportdata.swiss/en/dataset/bhlist).
This list is older and not as complete as the stops data from the GTFS timetables. Nevertheless, it has the altitude information of the stops, which is not available from the timetable files, in case you need that.

It has the schema:

- `STATIONID`: identifier of the station/stop
- `LONGITUDE`: longitude (WGS84)
- `LATITUDE`: latitude (WGS84)
- `HEIGHT`: altitude (meters) of the stop
- `REMARK`: long name of the stop

#### Misc data

Althought, not required for this final, you are of course free to use any other sources of data of your choice that might find helpful.

You may for instance download regions of openstreetmap [OSM](https://www.openstreetmap.org/#map=9/47.2839/8.1271&layers=TN),
which includes a public transport layer. If the planet OSM is too large for you,
you can find frequently updated exports of the [Swiss OSM region](https://planet.osm.ch/).

Others had some success using weather data to predict traffic delays.
If you want to give a try, web services such as [wunderground](https://www.wunderground.com/history/daily/ch/r%C3%BCmlang/LSZH/date/2019-8-1), can be a good
source of historical weather data.

[top](#Content)

----
## References

Here is a list of useful references for those of you who want to push it further or learn more about it:

* Adi Botea, Stefano Braghin, "Contingent versus Deterministic Plans in Multi-Modal Journey Planning". ICAPS 2015: 268-272.
* Adi Botea, Evdokia Nikolova, Michele Berlingerio, "Multi-Modal Journey Planning in the Presence of Uncertainty". ICAPS 2013.
* S Gao, I Chabini, "Optimal routing policy problems in stochastic time-dependent networks", Transportation Research Part B: Methodological, 2006.

[top](#Content)

----