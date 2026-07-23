from dataclasses import dataclass, field


@dataclass
class SteerChannel:
    title: str = ""
    id: int = 0
    bias: int = 0
    pmin: int = 500
    pmax: int = 2500
    lab_left: str = ""
    lab_right: str = ""
    enable: bool = False
    x: int = 0
    y: int = 0


@dataclass
class ActionGroup:
    index: int
    moves: list[tuple[int, int, int]] = field(default_factory=list)


@dataclass
class Project:
    steers: list[SteerChannel] = field(default_factory=list)
    groups: list[ActionGroup] = field(default_factory=list)
    raw_sections: dict[str, list[tuple[str, str]]] = field(default_factory=dict)
    meta: dict = field(default_factory=dict)


def enabled_steers(project: Project) -> list[SteerChannel]:
    return [steer for steer in project.steers if steer.enable]
