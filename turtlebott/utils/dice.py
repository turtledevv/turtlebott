import random
import re
from dataclasses import dataclass
from typing import Optional, List


dice_regex = re.compile(
    r'(?:(\d*)d(\d+))([+-]\d+(?:\.\d+)?)?(?:\s+for\s+(.+))?',
    re.IGNORECASE
)


@dataclass
class DiceResult:
    count: int
    size: int
    rolls: List[int]
    modifier: float
    total: float
    reason: Optional[str]
    expression: str


def roll_die(size: int) -> int:
    return random.randint(1, size)


def roll_dice(count: int, size: int) -> List[int]:
    return [roll_die(size) for _ in range(count)]

def clean_number(n):
    if isinstance(n, float) and n.is_integer():
        return int(n)
    return n


def parse_roll(expr: str) -> DiceResult:
    expr = expr.strip()
    match = dice_regex.fullmatch(expr)

    if not match:
        raise ValueError("Invalid dice syntax")

    count = int(match.group(1) or 1)
    size = int(match.group(2))

    modifier_str = match.group(3)
    modifier = float(modifier_str) if modifier_str else 0.0

    reason = match.group(4)

    rolls = roll_dice(count, size)
    total = sum(rolls) + modifier

    return DiceResult(
        count=count,
        size=size,
        rolls=rolls,
        modifier=modifier,
        total=total,
        reason=reason,
        expression=expr
    )