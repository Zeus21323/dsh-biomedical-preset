"""Resource-backed molecule labels; native identifiers are never discarded."""
import csv
import io
from pathlib import Path
import zipfile
from communication_contract import truth

SCHEMA = "hgnc-complete-complex-v1"


def gene_identity(symbols):
    symbols = sorted(set(str(s) for s in symbols if s))
    if not symbols:
        raise ValueError("分子缺少经资源核验的基因符号")
    return ("gene:" if len(symbols) == 1 else "complex:") + "&".join(symbols)


def cpdb_entities(database):
    """Read the exact supplied CPDB archive/tables, without network alias guessing.

    Multiple HGNC symbols for one protein and non-PPI proxy entities retain a
    database-specific identity; neither is collapsed into a gene complex.
    """
    database = Path(database)
    def read(name):
        if database.is_dir():
            with (database / name).open(newline="") as handle:
                return list(csv.DictReader(handle))
        with zipfile.ZipFile(database) as archive:
            return list(csv.DictReader(io.StringIO(archive.read(name).decode("utf-8"))))
    proteins = {r["id_protein"]: r["protein_multidata_id"] for r in read("protein_table.csv")}
    genes = {}
    for row in read("gene_table.csv"):
        if row["hgnc_symbol"]:
            genes.setdefault(proteins[row["protein_id"]], set()).add(row["hgnc_symbol"])
    composition = {}
    for row in read("complex_composition_table.csv"):
        composition.setdefault(row["complex_multidata_id"], set()).add(row["protein_multidata_id"])
    entities = {}
    for row in read("multidata_table.csv"):
        mid = row["id_multidata"]
        members = composition.get(mid, {mid})
        complete = all(len(genes.get(m, set())) == 1 for m in members)
        symbols = sorted({g for m in members for g in genes.get(m, set())})
        entities[mid] = dict(native_id=mid, native_name=row["name"], genes=symbols,
            label="_".join(symbols) if complete else row["name"],
            identity=gene_identity(symbols) if complete and not (mid in composition and len(symbols) == 1) else "cpdb:" + row["name"],
            identity_resolved=complete, receptor=truth(row["receptor"]))
    interactions = {}
    for row in read("interaction_table.csv"):
        a, b = (dict(entities[row[k]]) for k in ("multidata_1_id", "multidata_2_id"))
        if not truth(row.get("is_ppi", "false")):
            # CPDB non-protein ligand abundances use enzyme proxies. A proxy gene
            # is not the measured ligand, even when the complex has one member.
            for entity in (a, b):
                if entity["native_id"] in composition and not entity["receptor"]:
                    entity.update(label=entity["native_name"] + " [proxy]",
                                  identity="cpdb-proxy:" + entity["native_name"])
        interactions[row["id_cp_interaction"]] = dict(a=a, b=b,
            is_ppi=truth(row.get("is_ppi", "false")), native_row_id=row["id_interaction"])
    return interactions


def directed_fields(interaction):
    a, b = interaction["a"], interaction["b"]
    if a["receptor"] == b["receptor"]:
        return None
    ligand, receptor = (b, a) if a["receptor"] else (a, b)
    return dict(ligand=ligand["label"], receptor=receptor["label"],
        ligand_identity=ligand["identity"], receptor_identity=receptor["identity"],
        ligand_native=ligand["native_name"], receptor_native=receptor["native_name"],
        molecular_evidence="protein_interaction" if interaction["is_ppi"] else "nonprotein_proxy")


def cpdb_eligibility(debug):
    """Use native unrounded threshold masks, not P=1 or rounded percentages.

    Native CPDB uses strict > threshold for *each* complex subunit and masks a
    zero mean. Read only the pickle just written by this invocation, never a
    user-supplied pickle. Return a serializable native-ID keyed table.
    """
    mask = (debug["real_percent_analysis"] > 0) & (debug["real_mean_analysis"] > 0)
    identities = debug["interactions"]["id_cp_interaction"]
    mask.index = [str(identities.loc[i]) for i in mask.index]
    mask.index.name = "id_cp_interaction"
    return mask
