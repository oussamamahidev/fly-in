from parser import parser
from classes import drone, Path, connection
from errors import Invalid_graph
from typing import Union, Any, Optional
import heapq


class simulation:
    """Build paths through the parsed graph and drive drone movement.

    Attributes:
        zones: A mapping of zone names to zone objects.
        start_hub: The parsed start hub.
        end_hub: The parsed end hub.
        connection_list: The parsed connections.
        nb_drones: The number of drones in the simulation.
        drones: The drone objects controlled by the simulation.
    """

    def __init__(self, data_parsing: parser):
        """Initialize the simulation graph, paths, and drone fleet.

        Args:
            data_parsing: The parsed input data.
        """
        self.zones = {i.name: i for i in data_parsing.hub}
        self.zones.update({data_parsing.end_hub.name: data_parsing.end_hub})
        self.zones.update(
            {data_parsing.start_hub.name: data_parsing.start_hub}
            )
        self.start_hub = data_parsing.start_hub
        self.end_hub = data_parsing.end_hub
        self.connection_list = data_parsing.connection
        self.nb_drones = data_parsing._nb_drones
        # drone ids start at 1 to match the subject output (D1, D2, ...)
        self.drones = [
            drone(i, self.start_hub) for i in range(1, self.nb_drones + 1)
        ]
        self.nb_turn = 0
        self.create_adjs()
        self.dijkstra(self.start_hub.name, 4)
        self.min_cost()
        self.assign_path_to_drone()

    def create_adjs(self) -> None:
        """Build adjacency lists and a connection lookup table.

        Connections are bidirectional, so both directions are added.
        """
        self.adjs: dict[
            str,
            list[tuple[str, Union[int, float]]]
            ] = {i: [] for i in self.zones.keys()}
        self.connection_dict: dict[tuple[str, str], connection] = {}
        for i in self.connection_list:
            a = i.connection1
            b = i.connection2
            self.adjs[a.name].append((b.name, b.cost))
            self.adjs[b.name].append((a.name, a.cost))
            self.connection_dict[(a.name, b.name)] = i
            self.connection_dict[(b.name, a.name)] = i

    def distance_to_end(self) -> dict[str, float]:
        """Compute the cheapest cost from every zone to the end hub.

        A normal Dijkstra started from the end hub. Moving u -> v costs
        the cost of v (the zone we enter), so going backward from v we
        add ``zones[v].cost``.

        Returns:
            A mapping zone name -> minimal remaining cost (inf if the end
            hub cannot be reached from that zone).
        """
        dist: dict[str, float] = {name: float("inf") for name in self.zones}
        dist[self.end_hub.name] = 0
        queue: list[tuple[float, str]] = [(0, self.end_hub.name)]
        while queue:
            d, v = heapq.heappop(queue)
            if d > dist[v]:
                continue
            for u, _ in self.adjs[v]:
                if self.zones[u].type == 'blocked':
                    continue
                new_d = d + self.zones[v].cost
                if new_d < dist[u]:
                    dist[u] = new_d
                    heapq.heappush(queue, (new_d, u))
        return dist

    def dijkstra(self, start_zone: str, k: int) -> None:
        """Enumerate up to k simple paths from the start hub to the end hub.

        Best-first search (A*): partial paths are ordered by
        ``cost so far + cheapest remaining cost``, so the search goes
        straight toward the end hub instead of exploring every direction.

        Args:
            start_zone: The starting zone name.
            k: The maximum number of candidate paths to collect.
        """
        h = self.distance_to_end()
        self.paths: list[list[str]] = []
        if h[start_zone] == float("inf"):
            raise Invalid_graph("no paths exist in the graph")

        # (estimated total, -length, cost so far, zone, path)
        # -length: on equal estimates, extend the longest path first
        priority_queue: list[Any] = [
            (h[start_zone], -1, 0, start_zone, [start_zone])
            ]
        while priority_queue:
            _, _, c, zone, path = heapq.heappop(priority_queue)
            if zone == self.end_hub.name:
                self.paths.append(path)
                if len(self.paths) == k:
                    return
                continue

            for zone1, c1 in self.adjs[zone]:
                if self.zones[zone1].type == 'blocked':
                    continue
                # never visit the same zone twice in one path,
                # otherwise cycles make this loop run forever
                if zone1 in path or h[zone1] == float("inf"):
                    continue
                new_c = c + c1
                heapq.heappush(
                    priority_queue,
                    (new_c + h[zone1], -(len(path) + 1), new_c,
                     zone1, path + [zone1])
                    )

        if self.paths == []:
            raise Invalid_graph("no paths exist in the graph")

    def min_cost(self) -> None:
        """Compute the minimum bottleneck capacity for each discovered path."""
        self.min_path_cost: list[Any] = []
        for path in self.paths:
            min_cost = float("inf")
            zone1 = path[0]
            for zone in path[1:]:
                min_cost = min(
                    min_cost,
                    self.zones[zone1].max_drones,
                    self.connection_dict[(zone1, zone)].max_link_capacity
                    )
                zone1 = zone
            self.min_path_cost.append(min_cost)

    def assign_cost(self, path: list[str]) -> Union[float, int]:
        """Return the cumulative traversal cost of a path.

        Args:
            path: The ordered list of zone names.

        Returns:
            The total path cost.
        """
        cost = 0
        for zone in path:
            cost += self.zones[zone].cost
        return cost

    def assign_path_to_drone(self) -> None:
        """Assign each drone to the path where it should arrive the earliest.

        Estimated arrival = path cost + drones already queued / capacity.
        """
        path_obj = [
            Path(
                i,
                self.paths[i],
                self.assign_cost(self.paths[i]),
                self.min_path_cost[i]
            )
            for i in range(len(self.paths))
        ]
        for d in self.drones:
            best_cost = float("inf")
            best_path: Optional[Path] = None
            for path in path_obj:
                estimate = path.cost + path.exist_drones / path.capacity
                if estimate < best_cost:
                    best_cost = estimate
                    best_path = path
            if best_path is None:
                raise Invalid_graph("no path available for drones")
            best_path.exist_drones += 1
            d.path = best_path

    def is_finished(self) -> bool:
        """Return True when every drone has reached the end hub."""
        return all(d.zone is self.end_hub for d in self.drones)

    def try_move(self, d: drone) -> Optional[str]:
        """Try to move one drone along its path.

        Args:
            d: The drone to move.

        Returns:
            The move label, or None if the drone waits.
        """
        p: Any = d.path
        d.target_zone = self.zones[p.path[d.index_path]]
        con = self.connection_dict[(d.zone.name, d.target_zone.name)]
        return d.movement(con)

    def turn(self) -> list[tuple[drone, str]]:
        """Advance the simulation by one discrete turn.

        Returns:
            The (drone, label) pairs of every drone that moved this turn.
        """
        moves: list[tuple[drone, str]] = []
        if self.is_finished():
            return moves

        for con in self.connection_list:
            con.drones_in = 0

        active = [d for d in self.drones if d.zone is not self.end_hub]
        moved: set[int] = set()

        # 1) drones flying toward a restricted zone must arrive first
        for d in active:
            if d.in_connection:
                label = self.try_move(d)
                if label is not None:
                    moves.append((d, label))
                    moved.add(d.id)

        progress = True
        while progress:
            progress = False
            for d in active:
                if d.id in moved:
                    continue
                label = self.try_move(d)
                if label is not None:
                    moves.append((d, label))
                    moved.add(d.id)
                    progress = True

        if not moves:
            raise Invalid_graph(
                f"deadlock at turn {self.nb_turn + 1}: no drone can move"
            )
        self.nb_turn += 1
        moves.sort(key=lambda m: m[0].id)
        return moves
