"""Dependency-free CellNEST two-hop relay enumeration."""
from collections import Counter, defaultdict


def relay_instances(records, maximum):
    outgoing = defaultdict(list)
    for edge in records:
        outgoing[str(edge["from_cell"])].append(edge)
    counts, instances = Counter(), []
    for first in records:
        source, intermediate = str(first["from_cell"]), str(first["to_cell"])
        for second in outgoing.get(intermediate, []):
            receiver = str(second["to_cell"])
            if receiver in (source, intermediate):
                continue
            pattern = f"{first['ligand']}-{first['receptor']} to {second['ligand']}-{second['receptor']}"
            counts[pattern] += 1
            instances.append((pattern, first, second))
            if len(instances) > maximum:
                raise ValueError("CellNEST 两跳 relay 实例超过 maximum_relay_instances")
    return counts, instances
