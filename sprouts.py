#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sprouts.py -- 简化版 Sprouts（豆芽棋）.

规则（拓扑简化版）:
- n 个点开局，每个点 3 条"生命"。
- 每步：在同一区域内选两点 A、B（可相同，相同即自环，需要 2 条生命），
  连一条曲线，A、B 各消耗 1 条生命，曲线上产生一个新点（剩余 1 条生命）。
- 曲线把区域分成两个新区：A、B、新点同时属于两个新区（它们在分界线上），
  其余点由走棋方划分到两侧。后续走子必须在同一区域内进行。
- 无子可走者负（常规玩法）。

诚实说明：这是"生命数 + 区域划分"抽象，省略了真实 Sprouts 的平面嵌入
几何约束（真实规则里曲线不能交叉、区域形状由几何决定）。本实现里走棋方
自由选择划分方式——这恰好对应真实 Sprouts 里走棋方选择曲线走向。
"""

import argparse
import copy
import random
import sys


class IllegalMove(ValueError):
    """非法走法。"""


class Sprouts:
    """简化 Sprouts 对局状态。"""

    def __init__(self, n_spots=3, seed=None):
        if n_spots < 2:
            raise ValueError("至少需要 2 个点")
        self.rng = random.Random(seed)
        self.lives = {i: 3 for i in range(n_spots)}
        self.next_id = n_spots
        self.regions = [set(range(n_spots))]

    # ---- 查询 ----

    def live_in(self, r):
        """区域 r 中还有生命的点（排序后）。"""
        return sorted(s for s in self.regions[r] if self.lives.get(s, 0) > 0)

    def moves_in_region(self, r):
        """区域 r 内的全部走法：("link", r, a, b) 或 ("loop", r, a)。"""
        live = self.live_in(r)
        moves = []
        for i, a in enumerate(live):
            for b in live[i + 1:]:
                moves.append(("link", r, a, b))
            if self.lives[a] >= 2:
                moves.append(("loop", r, a))
        return moves

    def legal_moves(self):
        ms = []
        for r in range(len(self.regions)):
            ms.extend(self.moves_in_region(r))
        return ms

    def is_over(self):
        return not self.legal_moves()

    def total_lives(self):
        return sum(v for v in self.lives.values() if v > 0)

    # ---- 走子 ----

    def apply_move(self, move, partition=()):
        """执行走法。partition 为放入新区 1 的其余点集合（其余进新区 2）。

        返回新产生的点的编号。非法走法抛 IllegalMove。
        """
        kind = move[0]
        if kind not in ("link", "loop"):
            raise IllegalMove(f"未知走法类型: {kind}")
        r, a = move[1], move[2]
        b = move[3] if kind == "link" else a
        if not (0 <= r < len(self.regions)):
            raise IllegalMove(f"区域不存在: {r}")
        reg = self.regions[r]
        if a not in reg:
            raise IllegalMove(f"点 {a} 不在区域 {r}")
        if kind == "link":
            if b == a:
                raise IllegalMove("两点相同请用自环走法")
            if b not in reg:
                raise IllegalMove(f"点 {b} 不在区域 {r}")
            if self.lives.get(a, 0) < 1:
                raise IllegalMove(f"点 {a} 已无生命")
            if self.lives.get(b, 0) < 1:
                raise IllegalMove(f"点 {b} 已无生命")
        else:
            if self.lives.get(a, 0) < 2:
                raise IllegalMove(f"点 {a} 生命不足 2，不能自环")
        others = [s for s in reg if s not in (a, b)]
        part = set(partition)
        if not part <= set(others):
            raise IllegalMove("划分中含有不在本区域的点")
        # 生效：两端各耗 1 条生命（自环则同一点耗 2 条）
        self.lives[a] -= 1
        self.lives[b] -= 1
        s = self.next_id
        self.next_id += 1
        self.lives[s] = 3 - 2  # 新点天生 3 条生命，连线用掉 2 条，剩 1
        r1 = {a, b, s} | part
        r2 = {a, b, s} | (set(others) - part)
        self.regions[r] = r1
        self.regions.append(r2)
        self._cleanup()
        return s

    def _cleanup(self):
        for reg in self.regions:
            for s in [x for x in reg if self.lives.get(x, 0) <= 0]:
                reg.discard(s)
        self.regions = [reg for reg in self.regions if reg]


# ---- AI ----

def ai_move(game):
    """贪心 AI：采样 (走法, 划分)，选"困住"最多活点（使其所在区域无走法）的方案。"""
    moves = game.legal_moves()
    mv = game.rng.choice(moves)
    kind, r, a = mv[0], mv[1], mv[2]
    b = mv[3] if kind == "link" else a
    others = [s for s in game.regions[r] if s not in (a, b)]
    best, best_score = set(), None
    trials = min(16, 2 ** len(others)) if others else 1
    for _ in range(trials):
        part = {s for s in others if game.rng.random() < 0.5}
        g2 = copy.deepcopy(game)
        g2.apply_move(mv, part)
        stranded = sum(
            1
            for rr in range(len(g2.regions))
            if not g2.moves_in_region(rr)
            for _s in g2.live_in(rr)
        )
        score = (stranded, game.rng.random())
        if best_score is None or score > best_score:
            best, best_score = part, score
    return mv, best


def play_auto(n_spots=3, seed=None):
    """AI 对 AI 一局。返回 (胜方 0/1, 总步数)。"""
    g = Sprouts(n_spots, seed=seed)
    turn, moves = 0, 0
    while not g.is_over():
        mv, part = ai_move(g)
        g.apply_move(mv, part)
        turn = 1 - turn
        moves += 1
    return 1 - turn, moves  # 无子可走者负


# ---- 交互 ----

def render(g):
    lines = []
    for r, reg in enumerate(g.regions):
        pts = " ".join(f"{s}({g.lives[s]})" for s in sorted(reg))
        lines.append(f"区域{r}: {pts if pts else '(空)'}")
    return "\n".join(lines)


def play_interactive(n_spots, seed):
    g = Sprouts(n_spots, seed=seed)
    names = ["甲", "乙"]
    turn = 0
    while not g.is_over():
        print(render(g))
        print(f"轮到{names[turn]}（输入: 区域 A B；A==B 为自环；q 退出）")
        try:
            line = input("> ").strip()
        except EOFError:
            break
        if line == "q":
            break
        try:
            r, a, b = map(int, line.split())
        except ValueError:
            print("格式错误，应为: 区域 A B")
            continue
        kind = "loop" if a == b else "link"
        mv = (kind, r, a, b) if kind == "link" else (kind, r, a)
        part = set()
        if 0 <= r < len(g.regions):
            others = sorted(s for s in g.regions[r] if s not in (a, b))
            if others:
                print(f"其余点 {others}，输入放入新区 1 的点（空格分隔，直接回车=全放新区 2）:")
                try:
                    pline = input("划分> ").strip()
                except EOFError:
                    break
                if pline:
                    try:
                        part = set(map(int, pline.split()))
                    except ValueError:
                        print("划分格式错误")
                        continue
        try:
            s = g.apply_move(mv, part)
        except IllegalMove as e:
            print(f"非法走法: {e}")
            continue
        print(f"产生新点 {s}")
        turn = 1 - turn
    print(render(g))
    if g.is_over():
        print(f"对局结束，{names[1 - turn]}胜（{names[turn]}无子可走）")
    else:
        print("对局中断")


def main(argv=None):
    ap = argparse.ArgumentParser(description="简化版 Sprouts（豆芽棋）")
    ap.add_argument("--spots", type=int, default=3, help="开局点数（默认3）")
    ap.add_argument("--auto", action="store_true", help="AI 对 AI 自动演示")
    ap.add_argument("--games", type=int, default=10, help="自动演示局数")
    ap.add_argument("--seed", type=int, default=None, help="随机种子")
    args = ap.parse_args(argv)
    if args.auto:
        w0 = w1 = 0
        for i in range(args.games):
            seed = None if args.seed is None else args.seed + i
            winner, moves = play_auto(args.spots, seed=seed)
            if winner == 0:
                w0 += 1
            else:
                w1 += 1
            print(f"第 {i + 1}/{args.games} 局：{'甲' if winner == 0 else '乙'}胜（{moves} 步）")
        print(f"总计：甲胜 {w0}，乙胜 {w1}，和棋 0")
        return
    if not sys.stdin.isatty():
        print("交互模式需要终端；无头演示请用 --auto", file=sys.stderr)
        sys.exit(2)
    play_interactive(args.spots, args.seed)


if __name__ == "__main__":
    main()
