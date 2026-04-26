"""
╔══════════════════════════════════════════════════════════════════╗
║       PATHFINDING VISUALIZER  v6.0  —  BFS · DFS · A*           ║
║       Pure Python + Tkinter  (no pip installs needed)            ║
╚══════════════════════════════════════════════════════════════════╝

ALL THREE ALGORITHMS collect every reachable star, then reach the goal.
They differ only in the ORDER they choose to visit stars:

  BFS  — visits stars in BFS discovery order (nearest by hops first).
          Tends to sweep outward in rings → compact route.

  DFS  — visits stars in DFS discovery order (dives deepest first).
          Tends to shoot far out then backtrack → longer, winding route.

  A*   — visits stars sorted by value (highest ★ first).
          Prioritises points over distance → often longest route,
          but maximum score.

HOW TO USE:
  1. Adjust grid size slider → click ⊕ NEW MAP (randomises walls,
     stars, AND start/goal positions)
  2. Optionally drag start (📍) or goal (🏁) to new cells
  3. Select algorithm, click ▶ RUN
  4. Click ⟳ RESET MAP to rerun another algorithm on the same map
  5. Run all 3 to compare results in the RESULTS bar
"""

import tkinter as tk
from tkinter import ttk
import random
from collections import deque

# ─── colours ──────────────────────────────────────────────────────────────────
C_BG     = "#0D1117"
C_PANEL  = "#161B22"
C_CARD   = "#1C2333"
C_BORDER = "#30363D"
C_BRIGHT = "#3D444D"
C_GREEN  = "#3FB950"
C_BLUE   = "#58A6FF"
C_ORANGE = "#F0883E"
C_RED    = "#F85149"
C_YELLOW = "#E3B341"
C_CYAN   = "#39D5D0"
C_WHITE  = "#E6EDF3"
C_MUTED  = "#8B949E"
C_DIM    = "#21262D"

ALGO_CLR = {"BFS": C_BLUE, "DFS": C_ORANGE, "A*": C_GREEN}

CS  = 38    # cell size px
PAD = 12    # canvas padding

EMPTY=0; WALL=1; STAR=2; START=3; GOAL=4


# ══════════════════════════════════════════════════════════════════════════════
#  GRID
# ══════════════════════════════════════════════════════════════════════════════
class Grid:
    def __init__(self, rows, cols):
        self.rows = rows
        self.cols = cols
        # FIX: randomise start and goal positions each time
        self._randomise_start_goal()
        self.generate()

    def _randomise_start_goal(self):
        """Pick random start and goal that are not the same cell."""
        all_cells = [(r, c) for r in range(self.rows) for c in range(self.cols)]
        self.start, self.goal = random.sample(all_cells, 2)

    def generate(self):
        """Randomise walls and stars. Keep existing start/goal.
        Retries until start->goal is reachable (handles rare dense-wall cases)."""
        while True:
            self.walls = set()
            self.stars = {}
            self.board = [[EMPTY]*self.cols for _ in range(self.rows)]
            self._place_walls()
            self._place_stars()
            self._stamp()
            if self.is_reachable(self.start, self.goal):
                break   # valid map — stop retrying

    def _place_walls(self):
        forbidden = {self.start, self.goal}
        n = random.randint(10, min(40, self.rows * self.cols // 4))
        placed = 0
        for _ in range(3000):
            if placed == n:
                break
            r = random.randint(0, self.rows - 1)
            c = random.randint(0, self.cols - 1)
            p = (r, c)
            if p not in forbidden and self.board[r][c] == EMPTY:
                self.board[r][c] = WALL
                self.walls.add(p)
                placed += 1

    def _place_stars(self):
        free = [
            (r, c) for r in range(self.rows) for c in range(self.cols)
            if self.board[r][c] == EMPTY
            and (r, c) not in (self.start, self.goal)
        ]
        k = min(len(free), max(5, self.rows * self.cols // 6))
        for (r, c) in random.sample(free, k):
            v = random.randint(1, 5)
            self.stars[(r, c)] = v
            self.board[r][c]   = STAR

    def _stamp(self):
        sr, sc = self.start
        gr, gc = self.goal
        self.board[sr][sc] = START
        self.board[gr][gc] = GOAL
        self.stars.pop(self.start, None)
        self.stars.pop(self.goal, None)

    def neighbors(self, r, c):
        out = []
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < self.rows and 0 <= nc < self.cols:
                if (nr, nc) not in self.walls:
                    out.append((nr, nc))
        return out

    def is_reachable(self, src, dst):
        if src == dst:
            return True
        seen = {src}
        q    = deque([src])
        while q:
            cur = q.popleft()
            for nb in self.neighbors(*cur):
                if nb == dst:
                    return True
                if nb not in seen:
                    seen.add(nb)
                    q.append(nb)
        return False

    def set_start(self, pos):
        self._restore(self.start)
        self.start = pos
        self._stamp()

    def set_goal(self, pos):
        self._restore(self.goal)
        self.goal = pos
        self._stamp()

    def _restore(self, pos):
        r, c = pos
        if pos in self.walls:   self.board[r][c] = WALL
        elif pos in self.stars: self.board[r][c] = STAR
        else:                   self.board[r][c] = EMPTY


# ══════════════════════════════════════════════════════════════════════════════
#  PATH HELPERS  (used internally by all algorithms)
# ══════════════════════════════════════════════════════════════════════════════

def _bfs_path(grid, src, dst):
    """Shortest path src→dst via BFS. Returns full list [src … dst]."""
    if src == dst:
        return [src]
    parent = {src: None}
    q      = deque([src])
    while q:
        cur = q.popleft()
        if cur == dst:
            path, c = [], dst
            while c is not None:
                path.append(c)
                c = parent[c]
            return list(reversed(path))
        for nb in grid.neighbors(*cur):
            if nb not in parent:
                parent[nb] = cur
                q.append(nb)
    return []  # unreachable


def _build_full_path(grid, ordered_stars):
    """
    Shared helper: start → star₁ → star₂ → … → starN → goal.
    Uses BFS shortest path for every segment.
    Returns the movement steps (excluding the start cell itself).
    """
    full_path = []
    current   = grid.start

    for star in ordered_stars:
        seg = _bfs_path(grid, current, star)
        if len(seg) > 1:
            full_path.extend(seg[1:])   # drop already-at-position
            current = star

    # Final leg to goal
    seg = _bfs_path(grid, current, grid.goal)
    if len(seg) > 1:
        full_path.extend(seg[1:])
    elif current != grid.goal:
        # Can't reach goal from current waypoint.
        # BUG FIX: fall back from *current*, not grid.start,
        # so we don't lose the star-collection progress already in full_path.
        seg = _bfs_path(grid, current, grid.goal)
        if seg:
            full_path.extend(seg[1:])
        else:
            # Truly unreachable — return empty to trigger "no path" warning
            return []

    return full_path


def _reachable_stars(grid):
    """Return stars that the agent can both reach AND continue to goal from."""
    return [
        p for p in grid.stars
        if grid.is_reachable(grid.start, p)
        and grid.is_reachable(p, grid.goal)
    ]


# ══════════════════════════════════════════════════════════════════════════════
#  ALGORITHMS  — all collect EVERY reachable star, differ only in visit ORDER
# ══════════════════════════════════════════════════════════════════════════════

def algo_bfs(grid):
    """
    BFS order: discover stars in BFS (breadth-first) order from start.
    Stars closer by hops are visited first → compact, ring-by-ring sweep.
    All reachable stars are still collected.
    """
    stars_set = set(_reachable_stars(grid))
    if not stars_set:
        seg = _bfs_path(grid, grid.start, grid.goal)
        return seg[1:] if seg else []

    # BFS from start — record stars in the order they are first encountered
    seen    = {grid.start}
    q       = deque([grid.start])
    ordered = []
    while q and len(ordered) < len(stars_set):
        cur = q.popleft()
        if cur in stars_set and cur not in ordered:
            ordered.append(cur)
        for nb in grid.neighbors(*cur):
            if nb not in seen:
                seen.add(nb)
                q.append(nb)

    return _build_full_path(grid, ordered)


def algo_dfs(grid):
    """
    DFS order: discover stars in DFS (depth-first) order from start.
    Agent dives deep before backtracking → long, winding route.
    All reachable stars are still collected.
    """
    stars_set = set(_reachable_stars(grid))
    if not stars_set:
        seg = _bfs_path(grid, grid.start, grid.goal)
        return seg[1:] if seg else []

    # DFS from start — record stars in visit order (mark visited on pop)
    seen    = set()
    stack   = [grid.start]
    ordered = []
    while stack and len(ordered) < len(stars_set):
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        if cur in stars_set and cur not in ordered:
            ordered.append(cur)
        # Push neighbours (reversed so left/up explored first → consistent DFS)
        for nb in reversed(grid.neighbors(*cur)):
            if nb not in seen:
                stack.append(nb)

    return _build_full_path(grid, ordered)


def algo_astar(grid):
    """
    A* / greedy-value order: visit stars sorted by value descending.
    Tie-breaks by Manhattan distance from the CURRENT position as the agent
    moves, so equal-value stars that are closer are preferred at each step.
    Highest-star stars collected first -> maximum points, typically longest route.
    All reachable stars are still collected.
    """
    candidates = _reachable_stars(grid)
    if not candidates:
        seg = _bfs_path(grid, grid.start, grid.goal)
        return seg[1:] if seg else []

    # Build ordered list dynamically: at each step pick the highest-value
    # star; break ties by Manhattan distance from current position.
    remaining = list(candidates)
    ordered   = []
    current   = grid.start
    while remaining:
        cr, cc = current
        remaining.sort(
            key=lambda p: (-grid.stars[p], abs(p[0]-cr) + abs(p[1]-cc))
        )
        chosen = remaining.pop(0)
        ordered.append(chosen)
        current = chosen   # next tie-break is from this star's position

    return _build_full_path(grid, ordered)


ALGOS = {"BFS": algo_bfs, "DFS": algo_dfs, "A*": algo_astar}


# ══════════════════════════════════════════════════════════════════════════════
#  APPLICATION
# ══════════════════════════════════════════════════════════════════════════════
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Pathfinding Visualizer  —  BFS · DFS · A*")
        self.configure(bg=C_BG)
        self.resizable(True, True)

        self.sz_var    = tk.IntVar(value=12)
        self.algo_var  = tk.StringVar(value="A*")
        self.speed_var = tk.StringVar(value="Medium")

        self.grid_obj  = None
        self.path      = []
        self.path_idx  = 0
        self.agent     = None
        self.collected = {}
        self.visited   = set()
        self.running   = False
        self.after_id  = None
        self.mode      = None   # "start" | "goal" | None

        self.results = {a: {"steps":0,"points":0,"stars":0,"done":False}
                        for a in ALGOS}

        self._build_ui()
        self._new_map()

    # ══ UI ═══════════════════════════════════════════════════════════════════
    def _build_ui(self):
        # title bar
        tf = tk.Frame(self, bg=C_BG)
        tf.pack(fill="x", padx=14, pady=(10, 2))
        tk.Label(tf, text="⬡ PATHFINDING VISUALIZER",
                 bg=C_BG, fg=C_CYAN,
                 font=("Courier", 16, "bold")).pack(side="left")
        tk.Label(tf, text="  BFS · DFS · A★",
                 bg=C_BG, fg=C_MUTED,
                 font=("Courier", 9)).pack(side="left")
        self.hdr = tk.Label(tf, text="",
                            bg=C_BG, fg=C_YELLOW,
                            font=("Courier", 9, "bold"))
        self.hdr.pack(side="right")

        # body
        body = tk.Frame(self, bg=C_BG)
        body.pack(fill="both", expand=True, padx=14, pady=4)

        # canvas
        cw = tk.Frame(body, bg=C_PANEL,
                      highlightthickness=1,
                      highlightbackground=C_BORDER)
        cw.pack(side="left", fill="both", expand=True)
        self.canvas = tk.Canvas(cw, bg=C_BG,
                                highlightthickness=0,
                                cursor="crosshair")
        self.canvas.pack(padx=3, pady=3)
        self.canvas.bind("<Button-1>", self._on_click)

        # side panel
        panel = tk.Frame(body, bg=C_PANEL, width=268,
                         highlightthickness=1,
                         highlightbackground=C_BORDER)
        panel.pack(side="right", fill="y", padx=(10, 0))
        panel.pack_propagate(False)
        self._build_panel(panel)

        # stats bar
        self.stats_f = tk.Frame(self, bg=C_PANEL,
                                highlightthickness=1,
                                highlightbackground=C_BORDER)
        self.stats_f.pack(fill="x", padx=14, pady=(4, 10))
        self._draw_stats()

    def _sep(self, p, txt):
        tk.Label(p, text=txt, bg=C_PANEL, fg=C_MUTED,
                 font=("Courier", 7, "bold")).pack(anchor="w", padx=12, pady=(12, 0))
        tk.Frame(p, bg=C_BORDER, height=1).pack(fill="x", padx=12, pady=(2, 5))

    def _build_panel(self, p):
        tk.Label(p, text="CONTROLS",
                 bg=C_PANEL, fg=C_CYAN,
                 font=("Courier", 12, "bold")).pack(pady=(12, 0))

        # grid size
        self._sep(p, "GRID SIZE  →  click ⊕ NEW MAP to apply")
        row = tk.Frame(p, bg=C_PANEL)
        row.pack(fill="x", padx=12)
        tk.Label(row, text="10", bg=C_PANEL, fg=C_MUTED,
                 font=("Courier", 8)).pack(side="left")
        ttk.Scale(row, from_=10, to=20, orient="horizontal",
                  variable=self.sz_var,
                  command=self._on_sz).pack(side="left", fill="x",
                                            expand=True, padx=4)
        tk.Label(row, text="20", bg=C_PANEL, fg=C_MUTED,
                 font=("Courier", 8)).pack(side="left")
        self.sz_lbl = tk.Label(p, text="12 × 12",
                               bg=C_PANEL, fg=C_CYAN,
                               font=("Courier", 9, "bold"))
        self.sz_lbl.pack()

        # start / goal
        self._sep(p, "PLACE START & GOAL  (optional)")
        r2 = tk.Frame(p, bg=C_PANEL)
        r2.pack(fill="x", padx=12, pady=(0, 2))
        self.btn_s = tk.Button(
            r2, text="📍 Set Start",
            bg=C_GREEN, fg=C_BG,
            font=("Courier", 9, "bold"), bd=0, relief="flat",
            padx=6, pady=5, cursor="hand2",
            command=lambda: self._set_mode("start")
        )
        self.btn_s.pack(side="left", fill="x", expand=True, padx=(0, 3))
        self.btn_g = tk.Button(
            r2, text="🏁 Set Goal",
            bg=C_RED, fg="white",
            font=("Courier", 9, "bold"), bd=0, relief="flat",
            padx=6, pady=5, cursor="hand2",
            command=lambda: self._set_mode("goal")
        )
        self.btn_g.pack(side="left", fill="x", expand=True, padx=(3, 0))
        self.mode_lbl = tk.Label(p, text="",
                                 bg=C_PANEL, fg=C_YELLOW,
                                 font=("Courier", 8, "bold"))
        self.mode_lbl.pack()

        # algorithm
        self._sep(p, "ALGORITHM  (all collect ALL stars)")
        self.rbs = {}
        descs = {
            "BFS": "nearest stars first · ring-by-ring sweep",
            "DFS": "deepest stars first · dives & backtracks",
            "A*":  "highest ★ value first · max score route",
        }
        for algo, clr in ALGO_CLR.items():
            fr = tk.Frame(p, bg=C_PANEL)
            fr.pack(fill="x", padx=12, pady=2)
            rb = tk.Radiobutton(
                fr, text=f"  {algo}",
                variable=self.algo_var, value=algo,
                bg=C_PANEL, fg=clr, selectcolor=C_CARD,
                activebackground=C_PANEL, activeforeground=clr,
                font=("Courier", 11, "bold"),
                command=self._on_algo
            )
            rb.pack(side="left")
            tk.Label(fr, text=descs[algo],
                     bg=C_PANEL, fg=C_DIM,
                     font=("Courier", 7)).pack(side="left", padx=5)
            self.rbs[algo] = rb

        # speed
        self._sep(p, "ANIMATION SPEED")
        for spd in ["Slow", "Medium", "Fast"]:
            tk.Radiobutton(
                p, text=f"  {spd}",
                variable=self.speed_var, value=spd,
                bg=C_PANEL, fg=C_WHITE, selectcolor=C_CARD,
                activebackground=C_PANEL, activeforeground=C_YELLOW,
                font=("Courier", 9)
            ).pack(anchor="w", padx=12, pady=1)

        # action buttons
        self._sep(p, "ACTIONS")
        bkw = dict(font=("Courier", 10, "bold"), bd=0,
                   relief="flat", padx=8, pady=8, cursor="hand2")

        self.run_btn = tk.Button(p, text="▶  RUN",
                                 bg=C_GREEN, fg=C_BG,
                                 command=self._run, **bkw)
        self.run_btn.pack(fill="x", padx=12, pady=(0, 5))

        self.reset_btn = tk.Button(p, text="⟳  RESET MAP",
                                   bg=C_CARD, fg=C_CYAN,
                                   highlightthickness=1,
                                   highlightbackground=C_CYAN,
                                   command=self._reset_map, **bkw)
        self.reset_btn.pack(fill="x", padx=12, pady=(0, 5))

        self.new_btn = tk.Button(p, text="⊕  NEW MAP",
                                 bg=C_CARD, fg=C_ORANGE,
                                 highlightthickness=1,
                                 highlightbackground=C_ORANGE,
                                 command=self._new_map, **bkw)
        self.new_btn.pack(fill="x", padx=12)

        # legend
        self._sep(p, "LEGEND")
        for sym, clr, lbl in [
            ("S", C_GREEN,  "Start  (random on New Map)"),
            ("G", C_RED,    "Goal   (random on New Map)"),
            ("★", C_YELLOW, "Star  value 1–5  (all collected)"),
            ("■", "#555",   "Wall"),
            ("●", C_BLUE,   "Agent"),
            ("·", C_BRIGHT, "Trail"),
            ("✓", C_GREEN,  "Collected star"),
        ]:
            r = tk.Frame(p, bg=C_PANEL)
            r.pack(fill="x", padx=16, pady=1)
            tk.Label(r, text=sym, bg=C_PANEL, fg=clr,
                     font=("Courier", 10), width=3).pack(side="left")
            tk.Label(r, text=lbl, bg=C_PANEL, fg=C_MUTED,
                     font=("Courier", 7)).pack(side="left")

    # ══ stats bar ═════════════════════════════════════════════════════════════
    def _draw_stats(self):
        for w in self.stats_f.winfo_children():
            w.destroy()
        tk.Label(self.stats_f, text="  RESULTS ▸",
                 bg=C_PANEL, fg=C_MUTED,
                 font=("Courier", 8, "bold")).pack(side="left",
                                                    padx=(8, 4), pady=6)
        for algo, clr in ALGO_CLR.items():
            res  = self.results[algo]
            done = res["done"]
            card = tk.Frame(self.stats_f, bg=C_CARD,
                            highlightthickness=2 if done else 1,
                            highlightbackground=clr if done else C_BORDER)
            card.pack(side="left", padx=5, pady=4)
            tk.Label(card, text=f" {algo} ",
                     bg=C_CARD, fg=clr if done else C_MUTED,
                     font=("Courier", 9, "bold")).pack(pady=(4, 0))
            info = (f"Steps:{res['steps']}  ★:{res['stars']}  Pts:{res['points']}"
                    if done else "not run yet")
            tk.Label(card, text=f" {info} ",
                     bg=C_CARD,
                     fg=C_WHITE if done else C_DIM,
                     font=("Courier", 8)).pack(pady=(0, 2))
            tk.Label(card,
                     text=" ✓ LOCKED " if done else "  ——  ",
                     bg=C_CARD,
                     fg=clr if done else C_DIM,
                     font=("Courier", 6, "bold")).pack(pady=(0, 3))
        self.live_lbl = tk.Label(self.stats_f, text="",
                                 bg=C_PANEL, fg=C_CYAN,
                                 font=("Courier", 9))
        self.live_lbl.pack(side="right", padx=12)

    # ══ drawing ═══════════════════════════════════════════════════════════════
    def _draw(self):
        self.canvas.delete("all")
        g   = self.grid_obj
        pad = PAD
        W   = pad * 2 + g.cols * CS
        H   = pad * 2 + g.rows * CS
        self.canvas.config(width=W, height=H)
        self.canvas.create_rectangle(0, 0, W, H, fill=C_BG, outline="")

        for r in range(g.rows):
            for c in range(g.cols):
                x1 = pad + c * CS;  y1 = pad + r * CS
                x2 = x1 + CS;       y2 = y1 + CS
                mx = x1 + CS // 2;  my = y1 + CS // 2
                pos  = (r, c)
                cell = g.board[r][c]

                # cell background
                if   pos == self.agent:     bg = "#0A1830"
                elif cell == WALL:          bg = "#111"
                elif cell == START:         bg = "#072010"
                elif cell == GOAL:          bg = "#200707"
                elif pos in self.collected: bg = "#071A07"
                elif pos in self.visited:   bg = "#0D1520"
                else:                       bg = C_BG

                self.canvas.create_rectangle(
                    x1+1, y1+1, x2-1, y2-1,
                    fill=bg, outline=C_BORDER, width=1
                )

                # cell content
                if pos == self.agent:
                    self.canvas.create_oval(x1+5, y1+5, x2-5, y2-5,
                                            fill=C_BLUE,
                                            outline=C_CYAN, width=2)
                    self.canvas.create_oval(x1+11, y1+11, x2-11, y2-11,
                                            fill="white", outline="")

                elif cell == WALL:
                    self.canvas.create_rectangle(x1+4, y1+4, x2-4, y2-4,
                                                 fill="#2A2A2A",
                                                 outline="#444", width=1)

                elif cell == START:
                    self.canvas.create_rectangle(x1+3, y1+3, x2-3, y2-3,
                                                 fill="#0A3A14",
                                                 outline=C_GREEN, width=2)
                    self.canvas.create_text(mx, my, text="S",
                                            fill=C_GREEN,
                                            font=("Courier", 13, "bold"))

                elif cell == GOAL:
                    self.canvas.create_rectangle(x1+3, y1+3, x2-3, y2-3,
                                                 fill="#3A0A0A",
                                                 outline=C_RED, width=2)
                    self.canvas.create_text(mx, my, text="G",
                                            fill=C_RED,
                                            font=("Courier", 13, "bold"))

                elif cell == STAR and pos not in self.collected:
                    v   = g.stars.get(pos, 1)
                    clr = ["", C_CYAN, C_BLUE, C_GREEN, C_ORANGE, C_YELLOW][v]
                    self.canvas.create_text(mx, my-3, text="★",
                                            fill=clr,
                                            font=("Courier", 13))
                    self.canvas.create_text(mx, my+9, text=str(v),
                                            fill=clr,
                                            font=("Courier", 7, "bold"))

                elif pos in self.collected:
                    self.canvas.create_text(mx, my, text="✓",
                                            fill=C_GREEN,
                                            font=("Courier", 11, "bold"))

                elif pos in self.visited:
                    self.canvas.create_text(mx, my, text="·",
                                            fill=C_BRIGHT,
                                            font=("Courier", 14, "bold"))

        # glow border when goal reached
        if self.agent == g.goal:
            x1 = pad + g.goal[1] * CS
            y1 = pad + g.goal[0] * CS
            self.canvas.create_rectangle(x1+1, y1+1, x1+CS-1, y1+CS-1,
                                         fill="", outline=C_RED, width=3)

    # ══ click handler ═════════════════════════════════════════════════════════
    def _set_mode(self, m):
        if self.running:
            return
        self.mode = m
        if m == "start":
            self.mode_lbl.config(text="▶ Click a cell to place START", fg=C_GREEN)
        else:
            self.mode_lbl.config(text="▶ Click a cell to place GOAL",  fg=C_RED)

    def _on_click(self, event):
        if self.running or self.mode is None:
            return
        g   = self.grid_obj
        col = (event.x - PAD) // CS
        row = (event.y - PAD) // CS
        if not (0 <= row < g.rows and 0 <= col < g.cols):
            return
        pos = (row, col)
        if g.board[row][col] == WALL:
            self.mode_lbl.config(text="⚠ Cannot place on a wall!", fg=C_RED)
            return
        if self.mode == "start" and pos == g.goal:
            self.mode_lbl.config(text="⚠ Start = Goal not allowed!", fg=C_RED)
            return
        if self.mode == "goal" and pos == g.start:
            self.mode_lbl.config(text="⚠ Goal = Start not allowed!", fg=C_RED)
            return
        if self.mode == "start":
            g.set_start(pos)
            self.mode_lbl.config(text=f"✓ Start placed at {pos}", fg=C_GREEN)
        else:
            g.set_goal(pos)
            self.mode_lbl.config(text=f"✓ Goal placed at {pos}", fg=C_RED)
        self.mode = None
        self._reset_agent()
        self._draw()

    # ══ map management ════════════════════════════════════════════════════════
    def _on_sz(self, val):
        # ttk.Scale passes a float string e.g. "12.000000001".
        # Round it, force-snap the IntVar so _new_map always reads a clean int.
        sz = int(round(float(val)))
        self.sz_var.set(sz)
        self.sz_lbl.config(text=f"{sz} x {sz}")

    def _on_algo(self):
        if not self.running:
            self._reset_agent()
            self._draw()

    def _new_map(self):
        """
        FIX: Always create a brand-new Grid with the current slider size.
        This randomises walls, stars, AND start/goal every time.
        """
        self._stop()
        sz = int(self.sz_var.get())
        self.grid_obj = Grid(sz, sz)          # always new → random S & G
        self.results  = {a: {"steps":0,"points":0,"stars":0,"done":False}
                         for a in ALGOS}
        self._reset_agent()
        self._draw_stats()
        self._enable()
        self.mode = None
        self.mode_lbl.config(text="")
        self.hdr.config(text="NEW MAP — READY", fg=C_CYAN)
        self._draw()

    def _reset_map(self):
        """Same walls + stars. Agent back to start. Locked results preserved."""
        if self.running:
            return
        self._reset_agent()
        self.mode = None
        self.mode_lbl.config(text="")
        self.hdr.config(text="RESET — SAME MAP", fg=C_MUTED)
        self.live_lbl.config(text="")
        self._draw()

    def _reset_agent(self):
        self.agent     = self.grid_obj.start
        self.path      = []
        self.path_idx  = 0
        self.collected = {}
        self.visited   = set()

    def _enable(self):
        self.run_btn.config(state="normal", bg=C_GREEN)
        self.reset_btn.config(state="normal")
        self.new_btn.config(state="normal")
        self.btn_s.config(state="normal")
        self.btn_g.config(state="normal")
        for rb in self.rbs.values():
            rb.config(state="normal")

    def _disable(self):
        self.run_btn.config(state="disabled", bg=C_DIM)
        self.reset_btn.config(state="disabled")
        self.new_btn.config(state="disabled")
        self.btn_s.config(state="disabled")
        self.btn_g.config(state="disabled")
        for rb in self.rbs.values():
            rb.config(state="disabled")

    # ══ run / animation ═══════════════════════════════════════════════════════
    def _run(self):
        if self.running:
            return
        algo = self.algo_var.get()
        if self.results[algo]["done"]:
            self.live_lbl.config(
                text=f"⚠  {algo} already ran — click ⟳ Reset Map first",
                fg=C_RED)
            return
        self._reset_agent()
        self.path = ALGOS[algo](self.grid_obj)
        if not self.path:
            self.live_lbl.config(
                text="⚠ No path found! Move Start/Goal or click ⊕ New Map",
                fg=C_RED)
            return
        self.running  = True
        self.path_idx = 0
        self._disable()
        self.hdr.config(text=f"RUNNING  {algo}…", fg=ALGO_CLR[algo])
        self._step()

    def _step(self):
        if not self.running:
            return
        if self.path_idx >= len(self.path):
            self._finish()
            return

        pos           = self.path[self.path_idx]
        self.agent    = pos
        self.visited.add(pos)
        self.path_idx += 1

        # collect star if present on this cell
        g = self.grid_obj
        if pos in g.stars and pos not in self.collected:
            self.collected[pos] = g.stars[pos]

        algo  = self.algo_var.get()
        steps = self.path_idx
        pts   = sum(self.collected.values())
        stars = len(self.collected)

        self.live_lbl.config(
            text=f"{algo}  ▸  step {steps}  ·  ★ {stars}  ·  pts {pts}",
            fg=ALGO_CLR[algo])
        self._draw()

        if pos == g.goal:
            self._finish()
            return

        ms = {"Slow": 350, "Medium": 100, "Fast": 20}[self.speed_var.get()]
        self.after_id = self.after(ms, self._step)

    def _finish(self):
        self.running = False
        algo  = self.algo_var.get()
        steps = self.path_idx
        pts   = sum(self.collected.values())
        stars = len(self.collected)

        self.results[algo] = {"steps":steps,"points":pts,
                              "stars":stars,"done":True}
        self._draw_stats()
        self._enable()
        self._draw()

        all_done = all(v["done"] for v in self.results.values())
        if all_done:
            best = min(self.results, key=lambda a: self.results[a]["steps"])
            most = max(self.results, key=lambda a: self.results[a]["points"])
            self.hdr.config(
                text=f"ALL DONE · ⚡{best}=fewest steps · ★{most}=most points",
                fg=C_YELLOW)
            self.live_lbl.config(
                text="All 3 complete! Click ⊕ New Map to compare again.",
                fg=C_YELLOW)
        else:
            left = [a for a in ALGOS if not self.results[a]["done"]]
            self.hdr.config(
                text=f"✓ {algo} LOCKED · {steps} steps · ★{stars} · {pts}pts",
                fg=ALGO_CLR[algo])
            self.live_lbl.config(
                text=f"Still to run: {', '.join(left)} — ⟳ Reset Map then ▶ Run",
                fg=ALGO_CLR[algo])

    def _stop(self):
        self.running = False
        if self.after_id:
            self.after_cancel(self.after_id)
            self.after_id = None
        self._enable()


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    App().mainloop()