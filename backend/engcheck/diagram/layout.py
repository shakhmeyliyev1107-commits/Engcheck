"""Avtomatik joylashtirish: oqim bo'yicha chapdan o'ngga qatlamlar. Bir xil kirish — bir xil natija."""
X0, Y0, DX, DY = 100, 90, 230, 130


def layout(nodes: list[dict], edges: list[dict]) -> None:
    """Tugunlarga x, y beradi (joyida o'zgartiradi). Sikllar uziladi; ulanmagan tugunlar pastki qatorga."""
    ids = sorted(n["id"] for n in nodes)
    out: dict[str, list[str]] = {i: [] for i in ids}
    connected: set[str] = set()
    for e in sorted(edges, key=lambda e: (e["from"], e["to"])):
        if e["from"] in out and e["to"] in out and e["from"] != e["to"]:
            out[e["from"]].append(e["to"])
            connected.update((e["from"], e["to"]))
    layer: dict[str, int] = {}
    state: dict[str, int] = {}   # 1 — ko'rilmoqda, 2 — tugagan

    def depth(node: str) -> int:
        """Tugundan chiqadigan eng uzun yo'l (orqaga qaytuvchi qirralar hisobga olinmaydi)."""
        stack = [(node, iter(out[node]))]
        state[node] = 1
        best = {node: 0}
        while stack:
            current, children = stack[-1]
            for child in children:
                if state.get(child) == 1:
                    continue                      # sikl: bu qirra e'tiborga olinmaydi
                if state.get(child) == 2:
                    best[current] = max(best[current], layer_len[child] + 1)
                    continue
                state[child] = 1
                best[child] = 0
                stack.append((child, iter(out[child])))
                break
            else:
                stack.pop()
                state[current] = 2
                layer_len[current] = best[current]
                if stack:
                    parent = stack[-1][0]
                    best[parent] = max(best[parent], best[current] + 1)
        return layer_len[node]

    layer_len: dict[str, int] = {}
    for i in ids:
        if i in connected and i not in state:
            depth(i)
    longest = max(layer_len.values(), default=0)
    for i in ids:
        if i in connected:
            layer[i] = longest - layer_len[i]      # manbalar chapda, oxirgi qabul qiluvchilar o'ngda
    columns: dict[int, list[str]] = {}
    for i in ids:
        if i in connected:
            columns.setdefault(layer[i], []).append(i)
    pos: dict[str, tuple[int, int]] = {}
    rows = 0
    for col, members in sorted(columns.items()):
        for row, i in enumerate(members):
            pos[i] = (X0 + col * DX, Y0 + row * DY)
        rows = max(rows, len(members))
    for k, i in enumerate(i for i in ids if i not in connected):   # ulanmaganlar: pastda, panjara bo'lib
        pos[i] = (X0 + (k % 5) * DX, Y0 + (rows + k // 5) * DY)
    for n in nodes:
        n["x"], n["y"] = pos[n["id"]]
