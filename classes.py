from typing import Any, Union, Optional


class zones:
    def __init__(
            self,
            name: str,
            x: int, y: int,
            metadata: Union[Any, dict[str, Any]],
            capacity: int = 0
            ):
        """Initialize a zone from parsed metadata.

        Args:
            name: The zone name.
            x: The x coordinate.
            y: The y coordinate.
            metadata: Parsed zone metadata.
            capacity: Initial number of drones (or reservations) in the zone.
        """
        self.name = name
        self.x = x
        self.y = y
        self.type = metadata['zone']
        self.max_drones = metadata['max_drones']
        self.capacity = capacity
        self.metadata = metadata
        self.cost: Any
        if self.type == 'normal':
            self.cost = 1
        elif self.type == 'priority':
            self.cost = 0.9
        elif self.type == 'blocked':
            self.cost = float("inf")
        elif self.type == 'restricted':
            self.cost = 2


class connection:
    def __init__(
            self,
            connection1: zones,
            connection2: zones,
            metadata: Any
            ):
        """Initialize a connection between two zones.

        Args:
            connection1: The first zone.
            connection2: The second zone.
            metadata: Parsed connection metadata.
        """
        self.connection1 = connection1
        self.connection2 = connection2
        self.max_link_capacity = metadata['max_link_capacity']
        # number of drones using this connection during the CURRENT turn
        # (reset to 0 by the simulation at the start of every turn)
        self.drones_in = 0
        self.metadata = metadata


class Path:
    def __init__(
            self,
            id: int,
            path: list[str],
            cost: Any,
            capacity: int
            ):
        """Initialize a path record used to assign drones to routes.

        Args:
            id: The path identifier.
            path: The ordered list of zone names.
            cost: The traversal cost for the path.
            capacity: The bottleneck capacity of the path.
        """
        self.id = id
        self.path = path
        self.cost = cost
        self.capacity = capacity
        self.exist_drones = 0


class drone:
    def __init__(self, id: int, zone: zones, path: Union[Path, None] = None):
        """Initialize a drone at a starting zone.

        Args:
            id: The drone identifier.
            zone: The starting zone.
            path: The assigned path, if any.
        """
        self.id = id
        self.zone = zone
        self.path = path
        self.index_path = 1
        self.target_zone: zones = zone
        self.in_connection = False

    def movement(self, con: connection) -> Optional[str]:
        """Try to advance the drone one step toward its target zone.

        Args:
            con: The connection between the current zone and the target.

        Returns:
            The label to print for this move ("zone" or "zone1-zone2"
            while flying toward a restricted zone), or None if the
            drone had to wait this turn.
        """
        if self.in_connection:
            # 2nd turn of a restricted move: the drone MUST arrive.
            # The target capacity was already reserved on the 1st turn,
            # so the reservation simply becomes the real occupancy.
            con.drones_in += 1
            self.zone = self.target_zone
            self.in_connection = False
            self.index_path += 1
            return self.zone.name

        if (
            self.target_zone.capacity >= self.target_zone.max_drones
            or con.drones_in >= con.max_link_capacity
        ):
            return None

        con.drones_in += 1
        self.zone.capacity -= 1
        self.target_zone.capacity += 1

        if self.target_zone.type == "restricted":
            # 1st turn: the drone leaves its zone and flies on the link
            self.in_connection = True
            return f"{self.zone.name}-{self.target_zone.name}"

        self.zone = self.target_zone
        self.index_path += 1
        return self.zone.name
