from errors import Invalid_Syntax
from classes import zones, connection
from typing import Tuple, Union, Any
from io import TextIOWrapper


class parser:
    """Parse the input file into hubs, connections, and settings.

    Attributes:
        path_file: The input file path.
        start_hub: The parsed start hub.
        end_hub: The parsed end hub.
        hub: The list of parsed intermediate hubs.
        connection: The list of parsed connections.
    """

    def __init__(self, path_file: str) -> None:
        """Initialize parser state and immediately read the input file.

        Args:
            path_file: The path to the input file.
        """
        self.path_file = path_file
        self.__first_line: Any = None
        self.start_hub: zones
        self.end_hub: zones
        self.__unique_names: set[str] = set()
        self.hub: list[zones] = []
        self.__zone_types: list[str] = [
            "normal", "blocked", "restricted", "priority"
            ]
        self.__connection_link: list[Tuple[str, str]] = []
        self.connection: list[connection] = []
        self.__states: list[str] = ["start_hub", "end_hub"]
        self.__known_types = [
            "start_hub", "hub", "end_hub", "nb_drones", "connection"
            ]
        self._cor_zones: set[Tuple[int, int]] = set()
        self.read_file()

    def read_file(self) -> None:
        """Open the input file and validate its content line by line."""
        with open(self.path_file) as file:
            self.validate_file(file)

    def validate_file(self, file: TextIOWrapper) -> None:
        """Validate each line and construct the domain objects from it.

        Args:
            file: The open file object being parsed.
        """
        metadata: Union[str, dict[Any, Any], list[str]]
        index = 0
        for index, line in enumerate(file, 1):
            line = line.strip()
            if line.startswith("#") or line == "":
                continue
            line = line.split("#", 1)[0]
            p = line.split(":", 1)

            if p[0] not in self.__known_types:
                raise Invalid_Syntax(
                    f"invalid zone_type: {line}", index
                    )
            if len(p) != 2:
                raise Invalid_Syntax(
                    f"missing ':' after {p[0]}", index
                    )
            if (
                p[0] == "nb_drones" and self.__first_line and
                "nb_drones" not in self.__states
                    ):
                raise Invalid_Syntax(
                    "nb_drones should be in the first line", index
                    )

            elif p[0] == "nb_drones" and self.__first_line is None:
                try:
                    value = int(p[1])
                    if value <= 0:
                        raise ValueError()
                except Exception:
                    raise Invalid_Syntax(
                        "nb_drones need to be a positiv integer", index
                    )

                self._nb_drones = int(p[1])
                self.__first_line = 1
            elif self.__first_line is None:
                raise Invalid_Syntax(
                    "nb_drones should be in the first line", index
                    )

            if (
                p[0].lower() == "start_hub" and
                "start_hub" not in self.__states
                    ):
                raise Invalid_Syntax("cant be there multuple start_hub", index)
            elif p[0].lower() == "start_hub" and "start_hub" in self.__states:
                d = p[1].strip().split(None, 3)

                if len(d) < 3:
                    raise Invalid_Syntax(
                        "zones should have only 3 or 4 argument", index
                    )
                name = str(d[0])
                try:
                    x = int(d[1])
                    y = int(d[2])
                except Exception:
                    raise Invalid_Syntax("x and y should be integers", index)
                if (x, y) in self._cor_zones:
                    raise Invalid_Syntax("x and y already exists", index)
                self._cor_zones.add((x, y))
                if len(d) == 4:
                    metadata = d[3]
                else:
                    metadata = "[zone=normal color=none max_drones="
                    metadata += f"{self._nb_drones}]"
                metadata = self.validate_zones_data(
                    name, x, y, metadata, index, "start_hub"
                )
                self.start_hub = zones(
                    name, x, y, metadata, capacity=self._nb_drones
                    )
                self.__states.remove("start_hub")
            if p[0].lower() == "end_hub" and "end_hub" not in self.__states:
                raise Invalid_Syntax("cant be there multuple end_hub", index)
            elif p[0].lower() == "end_hub" and "end_hub" in self.__states:
                d = p[1].strip().split(None, 3)
                if len(d) < 3 or len(d) > 4:
                    raise Invalid_Syntax(
                        "zones should have only 3 or 4 argument", index
                    )
                name = str(d[0])
                try:
                    x = int(d[1])
                    y = int(d[2])
                except Exception:
                    raise Invalid_Syntax("x and y should be integers", index)

                if (x, y) in self._cor_zones:
                    raise Invalid_Syntax("x and y already exists", index)
                self._cor_zones.add((x, y))

                if len(d) == 4:
                    metadata = d[3]
                else:
                    metadata = "[zone=normal color=none max_drones=1]"
                metadata = self.validate_zones_data(
                    name, x, y, metadata, index, "end_hub"
                )
                self.end_hub = zones(name, x, y, metadata)
                self.__states.remove("end_hub")
            elif p[0] == "hub":
                d = p[1].strip().split(None, 3)
                if len(d) < 3:
                    raise Invalid_Syntax(
                        "zones should have only 3 or 4 argument", index
                    )
                name = str(d[0])
                try:
                    x = int(d[1])
                    y = int(d[2])
                except Exception:
                    raise Invalid_Syntax("x and y should be integers", index)

                if (x, y) in self._cor_zones:
                    raise Invalid_Syntax("x and y already exists", index)
                self._cor_zones.add((x, y))

                if len(d) == 4:
                    metadata = d[3]
                else:
                    metadata = "[zone=normal color=none max_drones=1]"
                metadata = self.validate_zones_data(
                    name, x, y, metadata, index, "hub"
                    )
                self.hub.append(zones(name, x, y, metadata))

            elif p[0] == ("connection"):
                if self.__states != []:
                    raise Invalid_Syntax("missing start_hub or end_hub", index)
                d = p[1].strip().split("-")
                if len(d) != 2:
                    raise Invalid_Syntax(
                        'connection should be on this format "hub1-hub2"',
                        index
                    )
                metadata = d[1].split()
                if len(metadata) != 2:
                    metadata = "[max_link_capacity=1]"
                else:
                    d[1], metadata = d[1].split()
                if (
                    d[1] not in self.__unique_names or
                    d[0] not in self.__unique_names
                        ):
                    raise Invalid_Syntax(
                        f"unkown zone_name : ({d[0]}, {d[1]})", index
                        )
                self.__connection_link.append((d[0], d[1]))
                self.validate_connection(index)
                metadata = self.validate_metadata(
                    metadata, "connection", index, None
                    )

                # find the object of the first connection
                if d[0] == self.end_hub.name:
                    connection1 = self.end_hub
                elif d[0] == self.start_hub.name:
                    connection1 = self.start_hub
                else:
                    connection1 = [i for i in self.hub if i.name == d[0]][0]

                # find the object of the second connection
                if d[1] == self.start_hub.name:
                    connection2 = self.start_hub
                elif d[1] == self.end_hub.name:
                    connection2 = self.end_hub
                else:
                    connection2 = [i for i in self.hub if i.name == d[1]][0]

                self.connection.append(
                    connection(connection1, connection2, metadata)
                    )

        if self.__first_line is None:
            raise Invalid_Syntax("missing nb_drones (empty file?)", index)
        if self.__states != []:
            raise Invalid_Syntax(
                f"missing {' and '.join(self.__states)}", index
                )

    def validate_zones_data(self,
                            name: str,
                            x: int,
                            y: int,
                            metadata: str,
                            index: int,
                            zone_type: str
                            ) -> Any:
        """Validate zone naming rules and normalize zone metadata.

        Args:
            name: The zone name.
            x: The x coordinate.
            y: The y coordinate.
            zone_type: The zone role being validated.
            metadata: The raw metadata string.
            index: The current line number.

        Returns:
            A normalized metadata dictionary.
        """
        if len([i for i in name if i == "-" or i == " "]) != 0:
            raise Invalid_Syntax(
                f"name of {zone_type} cant have a space or dashes", index
            )
        if name in self.__unique_names:
            raise Invalid_Syntax("name of zones should be uniq", index)
        else:
            self.__unique_names.add(name)
        return self.validate_metadata(metadata, "zones", index, zone_type)

    def validate_metadata(
            self,
            metadata: str,
            type_metadata: str,
            index: int,
            zone_type: Union[str, None]
            ) -> dict[Any, Any]:
        """Parse and validate metadata blocks for zones and connections.

        Args:
            metadata: The raw metadata string.
            type_metadata: The metadata category to parse.
            index: The current line number.
            zone_type: The zone role when parsing zone metadata.

        Returns:
            A normalized metadata dictionary.
        """

        data: dict[Any, Any] = {}
        if type_metadata == "zones":
            allowed_metadata = ["zone", "color", "max_drones"]
            data["zone"] = "normal"
            data["color"] = "none"
            if zone_type == "start_hub" or zone_type == "end_hub":
                data["max_drones"] = self._nb_drones
            else:
                data["max_drones"] = 1
            if metadata[0] == "[" and metadata[-1] == "]":
                p = metadata[1:-1]
                parts = p.split()
                for i in parts:
                    sp = i.split("=")
                    if len(sp) != 2:
                        raise Invalid_Syntax(
                            "metadata should be like this [color=red]",
                            index
                        )

                    if sp[0] not in allowed_metadata:
                        raise Invalid_Syntax(
                            "Unknown metada type in zones", index
                            )

                    if sp[0] == "zone":
                        if sp[1] not in self.__zone_types:
                            raise Invalid_Syntax(
                                "invalid zone type in metadata", index
                                )
                        data[sp[0]] = sp[1]

                    elif sp[0] == "color":
                        data[sp[0]] = sp[1]

                    elif sp[0] == "max_drones":
                        try:
                            if (
                                zone_type != "end_hub"
                                and zone_type != "start_hub"
                                    ):
                                data[sp[0]] = int(sp[1])
                        except Exception:
                            raise Invalid_Syntax(
                                "max_drones should be integer not string",
                                index
                            )
                        if data[sp[0]] <= 0:
                            raise Invalid_Syntax(
                                "max_drones should be positiv integer",
                                index
                                )
            else:
                raise Invalid_Syntax("Invalid syntax of metadata", index)

        elif type_metadata == "connection":
            message = "syntax in metada should be like"
            message += "this [max_link_capacity=5]"
            allowed_metadata = ["max_link_capacity"]
            data["max_link_capacity"] = 1
            if metadata[0] == "[" and metadata[-1] == "]":
                p = metadata[1:-1:]
                parts = p.split("=")
                if len(parts) != 2:
                    raise Invalid_Syntax(
                        message,
                        index,
                    )
                if parts[0] not in allowed_metadata:
                    raise Invalid_Syntax(
                        "Unkown metadata type in connection", index
                        )
                try:
                    data[parts[0]] = int(parts[1])
                except Exception:
                    raise Invalid_Syntax(
                        "max_link_capacity should be integer not string", index
                    )
                if data[parts[0]] <= 0:
                    raise Invalid_Syntax(
                        "max_link capacity should be positiv integer",
                        index
                        )
            else:
                raise Invalid_Syntax(message, index)
        return data

    def validate_connection(self, index: int) -> None:
        """Reject duplicate connections regardless of endpoint order.

        Args:
            index: The current line number.
        """

        vis = set()

        for a, b in self.__connection_link:
            modified = tuple(sorted((a, b)))
            if modified in vis:
                raise Invalid_Syntax(
                    f"the connection ({a}, {b}) are duplicable", index
                    )
            else:
                vis.add(modified)
