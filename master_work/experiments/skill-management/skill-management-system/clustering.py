"""可复现的球形二分k-means及几何评估，纯标准库。"""

import math
import random
from collections import Counter

from models import ValidationError


def dot(left, right):
    return math.fsum(a * b for a, b in zip(left, right, strict=True))


def unit(vector):
    norm = math.hypot(*vector)
    if not math.isfinite(norm) or norm <= 1e-14:
        raise ValidationError("无法归一化零向量或抵消后的零质心")
    return [value / norm for value in vector]


def center(vectors, indices):
    return unit([math.fsum(vectors[i][d] for i in indices) for d in range(len(vectors[0]))])


def nearest(vector, centroids):
    return max(range(len(centroids)), key=lambda i: (dot(vector, centroids[i]), -i))


def _split(vectors, indices, seed, max_iterations):
    """多次确定种子的二分，保留最小球形损失；空簇不作伪修复。"""
    best = None
    rng = random.Random(seed)
    for _ in range(3):
        first = rng.choice(indices)
        second = min(indices, key=lambda i: (dot(vectors[first], vectors[i]), i))
        if dot(vectors[first], vectors[second]) >= 1 - 1e-12:
            continue
        centroids = [vectors[first], vectors[second]]
        previous = None
        for _iteration in range(max_iterations):
            groups = [[], []]
            for index in indices:
                groups[nearest(vectors[index], centroids)].append(index)
            if not all(groups):
                break
            centroids = [center(vectors, group) for group in groups]
            labels = tuple(tuple(group) for group in groups)
            if labels == previous:
                break
            previous = labels
        if not all(groups):
            continue
        # 子簇编号不受随机初始化左右：按最小样本下标排序。
        groups.sort(key=min)
        centroids = [center(vectors, group) for group in groups]
        loss = math.fsum(1 - dot(vectors[i], centroid)
                         for group, centroid in zip(groups, centroids) for i in group)
        candidate = (loss, tuple(tuple(group) for group in groups), centroids)
        if best is None or candidate[:2] < best[:2]:
            best = candidate
    if best is None:
        raise ValidationError("该节点没有可分离的向量，不能强行拆簇")
    return best[1], best[2]


def bisect(vectors, k, seed=42, max_iterations=50):
    if type(k) is not int or not 1 <= k <= len(vectors):
        raise ValidationError("k必须是1到样本数之间的整数")
    groups = {"n0": list(range(len(vectors)))}
    centers = {"n0": center(vectors, groups["n0"])}
    tree = {}
    while len(groups) < k:
        candidates = sorted(groups, key=lambda name: (
            -math.fsum(1 - dot(vectors[i], centers[name]) for i in groups[name]), name))
        split = None
        for name in candidates:
            if len(groups[name]) < 2:
                continue
            try:
                split = _split(vectors, groups[name], seed + len(tree), max_iterations)
            except ValidationError:
                continue
            break
        if split is None:
            raise ValidationError(f"只有{len(groups)}个可分离簇，不能达到k={k}")
        children, child_centers = split
        tree[name] = [name + ".0", name + ".1"]
        del groups[name], centers[name]
        for child, indices, centroid in zip(tree[name], children, child_centers):
            groups[child] = list(indices)
            centers[child] = centroid
    names = sorted(groups)
    labels = [None] * len(vectors)
    for label, name in enumerate(names):
        for index in groups[name]:
            labels[index] = label
    return {"groups": groups, "centroids": centers, "labels": labels, "tree": tree}


def silhouette(vectors, labels):
    groups = {}
    for index, label in enumerate(labels):
        groups.setdefault(label, []).append(index)
    if len(groups) < 2 or len(groups) == len(vectors):
        return None
    distances = [[max(0.0, min(2.0, 1 - dot(a, b))) for b in vectors] for a in vectors]
    values = []
    for i, label in enumerate(labels):
        own = groups[label]
        if len(own) == 1:
            values.append(0.0)
            continue
        a = math.fsum(distances[i][j] for j in own if j != i) / (len(own) - 1)
        b = min(math.fsum(distances[i][j] for j in members) / len(members)
                for other, members in groups.items() if other != label)
        values.append((b - a) / max(a, b) if max(a, b) > 0 else 0.0)
    return math.fsum(values) / len(values)


def adjusted_rand(left, right):
    if len(left) != len(right) or len(left) < 2:
        raise ValidationError("ARI需要两组等长且至少两个样本的标签")
    choose2 = lambda n: n * (n - 1) / 2
    cells = Counter(zip(left, right))
    observed = sum(choose2(n) for n in cells.values())
    a = sum(choose2(n) for n in Counter(left).values())
    b = sum(choose2(n) for n in Counter(right).values())
    expected = a * b / choose2(len(left))
    denominator = (a + b) / 2 - expected
    return (observed - expected) / denominator if denominator else 1.0


def bootstrap_stability(vectors, k, seed, rounds, max_iterations):
    """独立有放回采样两次；向同一全体样本投影标签后计算ARI。"""
    scores, failures = [], []
    rng = random.Random(seed)
    for iteration in range(rounds):
        predictions = []
        try:
            for arm in range(2):
                sample = [vectors[rng.randrange(len(vectors))] for _ in vectors]
                result = bisect(sample, k, seed + iteration * 2 + arm, max_iterations)
                centers = [result["centroids"][name] for name in sorted(result["centroids"])]
                predictions.append([nearest(vector, centers) for vector in vectors])
            scores.append(adjusted_rand(*predictions))
        except ValidationError as exc:
            failures.append({"round": iteration, "reason": str(exc)})
    return {"scores": scores, "mean_ari": math.fsum(scores) / len(scores) if scores else None,
            "failed_rounds": failures}


def select_k(vectors, config):
    evaluations, fitted = [], {}
    for k in config["k_candidates"]:
        try:
            result = bisect(vectors, k, config["seed"], config["max_iterations"])
            stability = bootstrap_stability(vectors, k, config["seed"], config["bootstrap_rounds"], config["max_iterations"])
            score = silhouette(vectors, result["labels"])
            eligible = (score is not None and not stability["failed_rounds"] and
                        stability["mean_ari"] >= config["min_stability"])
            evaluations.append({"k": k, "silhouette": score, "stability": stability, "eligible": eligible})
            fitted[k] = result
        except ValidationError as exc:
            evaluations.append({"k": k, "eligible": False, "error": str(exc)})
    eligible = [row for row in evaluations if row["eligible"]]
    selected = max(eligible, key=lambda row: (row["silhouette"], -row["k"]))["k"] if eligible else 1
    result = fitted.get(selected) or bisect(vectors, selected, config["seed"], config["max_iterations"])
    report = {"selection": "intrinsic_only", "task_calibrated": False, "selected_k": selected,
              "reason": "best_silhouette_after_stability_gate" if eligible else "no_eligible_candidate_use_single_node",
              "evaluations": evaluations}
    return result, report
