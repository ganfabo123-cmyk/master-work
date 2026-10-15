"""最多双挂的节点成员管理；变更先在副本验证，再整体替换。"""

import copy
import math

from clustering import bisect, dot, unit
from models import ValidationError


def summarize(members, vectors):
    ordered = sorted(members)
    total = [math.fsum(vectors[s][d] for s in ordered) for d in range(len(next(iter(vectors.values()))))]
    mean = [v / len(ordered) for v in total]
    return {"members": ordered, "count": len(ordered), "vector_sum": total,
            "mean": mean, "centroid": unit(total)}


def validate_layout(layout, vectors):
    try:
        if layout["version"] != 1 or layout["vector_space"] != "unit_description":
            raise ValidationError("不支持的节点状态格式")
        assignments, nodes = layout["assignments"], layout["nodes"]
        if set(assignments) != set(vectors):
            raise ValidationError("节点归属必须完整覆盖管理名单")
        if not nodes:
            raise ValidationError("节点集合不能为空")
        expected = {node: set() for node in nodes}
        for skill_id, names in assignments.items():
            if not isinstance(names, list) or not 1 <= len(names) <= 2 or len(set(names)) != len(names):
                raise ValidationError(f"{skill_id}: 必须归属1到2个不同节点")
            for name in names:
                if name not in nodes:
                    raise ValidationError(f"归属指向不存在的节点: {name}")
                expected[name].add(skill_id)
        for name, node in nodes.items():
            if not expected[name] or node["members"] != sorted(expected[name]):
                raise ValidationError(f"{name}: 成员与归属映射不一致或节点为空")
            actual = summarize(expected[name], vectors)
            if type(node["count"]) is not int or node["count"] != actual["count"]:
                raise ValidationError(f"{name}: 成员计数不一致")
            for field in ("vector_sum", "mean", "centroid"):
                saved = node[field]
                if len(saved) != len(actual[field]) or any(
                    isinstance(a, bool) or not isinstance(a, (int, float)) or
                    not math.isfinite(a) or not math.isclose(a, b, abs_tol=1e-10, rel_tol=1e-10)
                    for a, b in zip(saved, actual[field])):
                    raise ValidationError(f"{name}: {field}不满足质心不变量")
    except (KeyError, TypeError, AttributeError, ValueError) as exc:
        if isinstance(exc, ValidationError):
            raise
        raise ValidationError(f"节点状态无效: {exc}") from exc


def create_layout(vectors, fit, max_distance):
    ids = sorted(vectors)
    assignments = {}
    for node, indices in fit["groups"].items():
        for index in indices:
            assignments[ids[index]] = [node]
    # 仅根据硬聚类质心做一轮软分配，再以最终成员更新质心，避免循环抖动。
    for skill_id in ids:
        primary = assignments[skill_id][0]
        candidates = sorted((name for name in fit["centroids"] if name != primary),
                            key=lambda name: (-dot(vectors[skill_id], fit["centroids"][name]), name))
        if candidates and 1 - dot(vectors[skill_id], fit["centroids"][candidates[0]]) <= max_distance:
            assignments[skill_id].append(candidates[0])
    layout = {"version": 1, "vector_space": "unit_description", "assignments": assignments,
              "nodes": {}, "lineage": dict(fit["tree"]), "changes": []}
    for name in fit["groups"]:
        layout["nodes"][name] = summarize([s for s in ids if name in assignments[s]], vectors)
    validate_layout(layout, vectors)
    return layout


class NodeManager:
    def __init__(self, layout, vectors):
        self.vectors = {key: unit(value) for key, value in vectors.items()}
        validate_layout(layout, self.vectors)
        self.layout = copy.deepcopy(layout)

    def assign(self, skill_id, node_ids):
        """覆盖该skill的归属；可用于移动、增加或移除第二归属。"""
        if skill_id not in self.vectors:
            raise ValidationError("不能操作名单外skill")
        if not isinstance(node_ids, list) or not 1 <= len(node_ids) <= 2 or len(set(node_ids)) != len(node_ids):
            raise ValidationError("每个skill必须归属1到2个不同节点")
        if any(name not in self.layout["nodes"] for name in node_ids):
            raise ValidationError("目标节点不存在")
        changed = copy.deepcopy(self.layout)
        old = changed["assignments"][skill_id]
        changed["assignments"][skill_id] = list(node_ids)
        vector = self.vectors[skill_id]
        for name in set(old) ^ set(node_ids):
            node = changed["nodes"][name]
            sign = 1 if name in node_ids else -1
            members = set(node["members"])
            members.add(skill_id) if sign == 1 else members.remove(skill_id)
            if not members:
                del changed["nodes"][name]
                continue
            total = [a + sign * b for a, b in zip(node["vector_sum"], vector)]
            changed["nodes"][name] = {"members": sorted(members), "count": len(members),
                "vector_sum": total, "mean": [v / len(members) for v in total], "centroid": unit(total)}
        changed["changes"].append({"operation": "assign", "skill_id": skill_id,
                                   "before": old, "after": list(node_ids)})
        validate_layout(changed, self.vectors)
        self.layout = changed

    def oversized(self, target_size):
        if type(target_size) is not int or target_size <= 0:
            raise ValidationError("目标节点规模必须为正整数")
        return sorted(name for name, node in self.layout["nodes"].items() if node["count"] > 2 * target_size)

    def isolate(self, skill_id, node_id):
        """建立单成员节点，并原子移除该skill的旧归属。"""
        if skill_id not in self.vectors or not isinstance(node_id, str) or not node_id or node_id in self.layout["nodes"]:
            raise ValidationError("独立节点ID或skill无效")
        changed = copy.deepcopy(self.layout)
        old = list(changed["assignments"][skill_id])
        for name in old:
            remaining = [s for s in changed["nodes"][name]["members"] if s != skill_id]
            if remaining:
                changed["nodes"][name] = summarize(remaining, self.vectors)
            else:
                del changed["nodes"][name]
        changed["nodes"][node_id] = summarize([skill_id], self.vectors)
        changed["assignments"][skill_id] = [node_id]
        changed["changes"].append({"operation": "isolate", "skill_id": skill_id, "before": old, "after": [node_id]})
        validate_layout(changed, self.vectors)
        self.layout = changed

    def split(self, node_id, seed=42, max_iterations=50, reason="manual"):
        if node_id not in self.layout["nodes"]:
            raise ValidationError("待拆分节点不存在")
        members = self.layout["nodes"][node_id]["members"]
        if len(members) < 2:
            raise ValidationError("单成员节点不能拆分")
        fit = bisect([self.vectors[s] for s in members], 2, seed, max_iterations)
        changed = copy.deepcopy(self.layout)
        revision = len(changed["changes"]) + 1
        children = [f"{node_id}.r{revision}.{i}" for i in range(2)]
        if any(name in changed["nodes"] for name in children):
            raise ValidationError("局部节点ID冲突")
        for name, indices in zip(children, fit["groups"].values()):
            selected = [members[i] for i in indices]
            changed["nodes"][name] = summarize(selected, self.vectors)
            for skill_id in selected:
                changed["assignments"][skill_id] = [name if n == node_id else n for n in changed["assignments"][skill_id]]
        del changed["nodes"][node_id]
        changed["lineage"][node_id] = children
        changed["changes"].append({"operation": "local_split", "node_id": node_id,
            "children": children, "reason": reason, "before_members": members,
            "after_members": {name: changed["nodes"][name]["members"] for name in children}})
        validate_layout(changed, self.vectors)
        self.layout = changed
