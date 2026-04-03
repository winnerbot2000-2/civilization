from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Grid:
    width: int
    height: int

    @property
    def size(self) -> int:
        return self.width * self.height

    def in_bounds_xy(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def patch_id(self, x: int, y: int) -> int:
        return y * self.width + x

    def coords(self, patch_id: int) -> tuple[int, int]:
        return patch_id % self.width, patch_id // self.width

    def neighbors(self, patch_id: int) -> list[int]:
        x, y = self.coords(patch_id)
        result: list[int] = []
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx = x + dx
            ny = y + dy
            if self.in_bounds_xy(nx, ny):
                result.append(self.patch_id(nx, ny))
        return result

    def distance(self, a: int, b: int) -> int:
        ax, ay = self.coords(a)
        bx, by = self.coords(b)
        return abs(ax - bx) + abs(ay - by)

    def ordered_edge(self, a: int, b: int) -> tuple[int, int]:
        return (a, b) if a <= b else (b, a)
