from pathlib import Path

from smarts.sstudio.genscenario import gen_scenario
from smarts.sstudio.sstypes import (
    EndlessMission,
    Flow,
    JunctionEdgeIDResolver,
    MapSpec,
    Mission,
    RandomRoute,
    Route,
    Scenario,
    Traffic,
    TrafficActor,
    Via,
)

ego_missions = [
    Mission(
        route=Route(begin=("edge-south-SN", 1, 10), end=("edge-west-EW", 1, "max")),
    ),
    EndlessMission(
        begin=("edge-south-SN", 1, 10),
        via=(
            Via(
                "edge-south-SN",
                lane_offset=30,
                lane_index=1,
                required_speed=4,
            ),
            Via(
                JunctionEdgeIDResolver("edge-south-SN", 1, "edge-west-EW", 0),
                lane_offset=10,
                lane_index=0,
                required_speed=2,
            ),
            Via(
                "edge-west-EW",
                lane_offset=20,
                lane_index=0,
                required_speed=8,
            ),
            Via(
                "edge-west-EW",
                lane_offset=50,
                lane_index=1,
                required_speed=2,
            ),
            Via(
                "edge-west-EW",
                lane_offset=55,
                lane_index=0,
                required_speed=5,
            ),
            Via(
                "edge-west-EW",
                lane_offset=60,
                lane_index=1,
                required_speed=2,
            ),
            Via(
                "edge-west-EW",
                lane_offset=65,
                lane_index=0,
                required_speed=2,
            ),
            Via(
                "edge-west-EW",
                lane_offset=70,
                lane_index=1,
                required_speed=2,
            ),
        ),
    ),
]

variations = 40
scenario = Scenario(
    traffic={
        f"t{i}": Traffic(
            flows=[
                Flow(
                    route=RandomRoute(),
                    rate=3600,
                    randomly_spaced=True,
                    actors={TrafficActor(name="car"): 1.0},
                )
            ]
        )
        for i in range(variations)
    },
    ego_missions=ego_missions,
    map_spec=MapSpec(
        source=Path(__file__).parent.absolute(),
        shift_to_origin=True,
        lanepoint_spacing=1.0,
    ),
)

gen_scenario(
    scenario=scenario,
    output_dir=Path(__file__).parent,
)
