"""Deterministic campaign generator: the original first-pass levels."""

STYLES = "XIJKLQUVWYZ"


def generate(level_num=0):
    cols = min(80 + level_num * 4, 136)
    rows = 24
    block = STYLES[level_num % len(STYLES)]
    floor = rows - 3
    g = [[" " for _ in range(cols)] for _ in range(rows)]
    for y in range(2):
        for x in range(cols):
            g[y][x] = block
    for y in range(floor, rows):
        for x in range(cols):
            g[y][x] = block
    for y in range(rows):
        g[y][0] = g[y][1] = g[y][cols - 2] = g[y][cols - 1] = block

    platforms = []
    step_count = 6 + (level_num % 5)
    step_w = max(5, (cols - 14) // step_count)
    mode = level_num % 5
    heights = ([floor - 3 - ((i * 2 + level_num) % 5) for i in range(step_count)]
               if mode in (1, 3) else
               [floor - 3 - ((i + level_num) % 3) for i in range(step_count)])
    for i, top in enumerate(heights):
        x0 = 5 + i * step_w
        x1 = min(cols - 6, x0 + step_w - 2)
        if x1 <= x0:
            continue
        for x in range(x0, x1 + 1):
            g[top][x] = block
        platforms.append((x0, x1, top))

    # Дополнительные вертикальные связки создают разные маршруты, а не только лестницу.
    if mode in (2, 4):
        for i in range(1, len(platforms), 2):
            x0, x1, top = platforms[i]
            for y in range(top + 1, floor - 1):
                if y % 2 == 0:
                    g[y][x0] = block

    def put(x, y, ch):
        if 2 <= x < cols - 2 and 2 <= y < floor and g[y][x] == " ":
            g[y][x] = ch

    for i, (x0, x1, top) in enumerate(platforms):
        stride = 2 if mode != 4 else 3
        for x in range(x0 + 1, x1, stride):
            put(x, top - 1, "f")
        if i % 2 == 0:
            put((x0 + x1) // 2, top + 1, "g")
    for x in range(8, cols - 7, 9):
        put(x, floor - 1, "f")

    if level_num >= 1:
        for x in range(12, cols - 10, 17):
            if g[floor - 1][x] == " ":
                g[floor - 1][x] = "^"
                if x + 1 < cols - 3:
                    g[floor - 1][x + 1] = "^"
    if level_num >= 2:
        for i, (x0, x1, top) in enumerate(platforms[1::3]):
            put((x0 + x1) // 2, top - 2, "S")
    if level_num >= 4:
        for x, ch in ((cols // 3, "T"), (cols // 2, "F"), (cols * 2 // 3, "B")):
            if g[floor - 1][x] == " ":
                g[floor - 1][x] = ch
    if level_num >= 6:
        for x in range(18, cols - 12, 23):
            put(x, floor - 1, "C")
    if level_num >= 8:
        for x in range(15, cols - 12, 26):
            put(x, floor - 2, "A")
    if level_num >= 10:
        for x in range(22, cols - 14, 29):
            put(x, floor - 3, "O")
    if level_num >= 12:
        for x in range(28, cols - 14, 31):
            put(x, floor - 3, "R")
    if mode == 1:
        for x in range(14, cols - 12, 18): put(x, floor - 5, "M")
    if mode == 3:
        for x in range(18, cols - 12, 22): put(x, floor - 4, "D")
    if mode == 4:
        for x in range(20, cols - 12, 24): put(x, floor - 5, "H")

    g[floor - 1][3] = "P"
    g[floor - 1][cols - 4] = "E"
    for x in range(2, 7):
        if g[floor - 1][x] in "^SFCBT":
            g[floor - 1][x] = " "
    for x in range(cols - 7, cols - 2):
        if g[floor - 1][x] in "^SFCBT":
            g[floor - 1][x] = " "
    return ["".join(row) for row in g]


def _reference_level_01():
    """Ручная реконструкция первого кадра из temple/19-22-30."""
    rows = [
        "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
        "XX                          XX",
        "XX X                       f XX",
        "XX     f  f       f  f   f   XX",
        "XX   f  fff      XXX       f XX",
        "XX        XXXXX              XX",
        "XX   ffff       f           XX",
        "XX       XXXXXXXX            XX",
        "XX             f             XX",
        "XX        XXXXXXXXXX        XX",
        "XX   ff   XXXXXXXXXX  ff    XX",
        "XX P      XXXX  XXXX       EXX",
        "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
        "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
        "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
    ]
    return [row[:30].ljust(30) for row in rows]
