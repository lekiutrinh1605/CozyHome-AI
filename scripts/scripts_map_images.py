"""One-off script: copy room photos from Hinh-anh/ into static/images/rooms/
and build a room_id -> [image urls] JSON mapping, matched by CSV row order
per branch against the sorted room-code image groups in each branch folder."""
from __future__ import annotations

import csv
import json
import re
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SRC_ROOT = BASE_DIR / "assets" / "raw_images" / "Hinh-anh"
DST_ROOT = BASE_DIR / "static" / "images" / "rooms"
ROOMS_CSV = BASE_DIR / "data" / "rooms.csv"

BRANCH_DIRS = {
    "BT": "CozyHome-BenThanh",
    "TD": "CozyHome-ThaoDien",
    "PMH": "CozyHome-PhuMyHung",
}

VARIANT_RE = re.compile(r"^(?P<code>.+?)(?:\((?P<n>\d+)\))?$")


def natural_room_codes(files: list[Path]) -> list[tuple[str, list[Path]]]:
    groups: dict[str, list[tuple[int, Path]]] = {}
    for f in files:
        stem = f.stem
        m = VARIANT_RE.match(stem)
        code = m.group("code")
        n = int(m.group("n")) if m.group("n") else 0
        groups.setdefault(code, []).append((n, f))
    ordered_codes = sorted(groups.keys())
    result = []
    for code in ordered_codes:
        variants = sorted(groups[code], key=lambda t: t[0])
        result.append((code, [p for _, p in variants]))
    return result


def main():
    with open(ROOMS_CSV, encoding="utf-8") as fh:
        rooms = list(csv.DictReader(fh))

    mapping: dict[str, list[str]] = {}

    for branch_id, folder_name in BRANCH_DIRS.items():
        src_dir = SRC_ROOT / folder_name
        files = sorted(p for p in src_dir.glob("*.png"))
        code_groups = natural_room_codes(files)

        branch_rooms = [r for r in rooms if r["branch_id"] == branch_id]
        if len(branch_rooms) != len(code_groups):
            raise SystemExit(
                f"Mismatch for {branch_id}: {len(branch_rooms)} rooms vs {len(code_groups)} image groups"
            )

        dst_dir = DST_ROOT / branch_id
        dst_dir.mkdir(parents=True, exist_ok=True)

        for room, (code, paths) in zip(branch_rooms, code_groups):
            urls = []
            for idx, p in enumerate(paths, start=1):
                dst_name = f"{room['room_id']}-{idx}.png"
                shutil.copyfile(p, dst_dir / dst_name)
                urls.append(f"/static/images/rooms/{branch_id}/{dst_name}")
            mapping[room["room_id"]] = urls
            print(f"{branch_id}: {code} -> {room['room_id']} ({len(urls)} ảnh)")

    out_path = DST_ROOT / "room_images.json"
    out_path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nĐã ghi mapping: {out_path}")


if __name__ == "__main__":
    main()
