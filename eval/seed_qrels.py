#!/usr/bin/env python3
"""Seed eval/qrels.csv with an explicit, evidence-based first-pass judgment.

These judgments apply the per-need rubric in common.INFORMATION_NEEDS to the
pooled candidates:

    2 = explicit evidence satisfying the need
    1 = partial / weak / indirect evidence
    0 = no evidence, or the evidence contradicts the need

The judgments are a reproducible starting point for the evaluation owner. They are
not a substitute for the team's verification: run `python eval/judge.py --review`
to inspect every candidate and change any grade. `judge` is recorded as
"preliminary" so it is easy to see which rows still need sign-off.

Usage:
    python eval/seed_qrels.py            # refuses to overwrite an existing qrels
    python eval/seed_qrels.py --force    # regenerate from scratch
"""

from __future__ import annotations

import argparse
import csv

try:
    import common
except ImportError:
    from . import common


JUDGMENTS: dict[str, dict[str, tuple[int, str]]] = {
    "Q1": {
        "766": (2, "review: 'quick witty dialogue ... hilarious'"),
        "5236": (2, "review: 'clever ... brilliant writing, dialogue'"),
        "115": (1, "witty dialogue mixed with borderline slapstick"),
        "929204": (2, "review: 'clever ... entertainment'"),
        "7518": (2, "review: 'story ... so clever'"),
        "417859": (2, "review: 'quite witty dialogue'"),
        "810": (0, "cleverly describes plot, not humour"),
        "98566": (1, "only 'odd bit of witty dialogue'; otherwise negative"),
        "508442": (2, "review: 'cleverly developed and very well-written'"),
        "748783": (1, "only 'quite witty one-liners now and again'"),
        "539681": (0, "clever describes a character, not the humour"),
        "620725": (0, "no wit/intelligence evidence"),
        "583": (1, "satire/absurdity implied, not explicit wit praise"),
        "1934": (2, "review: 'witty and stimulating' writing"),
        "137": (1, "excellent/creative writing, not explicit wit"),
        "496243": (1, "funny social satire, no explicit wit praise"),
        "844185": (2, "review: 'clever joke' (repeated)"),
        "515001": (2, "satire praised as hilarious and sharp"),
        "535581": (2, "review: 'wittily gory zombie comedy'"),
        "1064213": (2, "review: 'quite witty dialogue'"),
        "800939": (2, "review: 'witty, light, fun rom-com'"),
        "955916": (1, "witty dialogue but mixed/negative reviews"),
        "762": (2, "celebrated satire/wit of British humour"),
        "522627": (0, "no wit/cleverness evidence"),
        "813": (2, "satirical humour explicitly praised"),
        "256591": (1, "clever describes cons/plot, not humour"),
        "284053": (2, "review: 'witty comedy'"),
        "365177": (0, "no evidence; negative reviews"),
        "493529": (0, "hilarious but no wit/intelligence evidence"),
        "739405": (0, "no evidence; generic"),
        "515248": (2, "review: 'witty leads'"),
        "238713": (0, "clever describes a character, not humour"),
        "1581": (2, "review: 'script is witty'"),
        "505600": (0, "no explicit wit/cleverness evidence"),
        "1261825": (2, "review: 'funny, clever'"),
        "337404": (1, "clever twist is plot, not humour"),
        "2493": (2, "review: 'wit and humour'; 'clever, hilarious'"),
    },
    "Q2": {
        "10096": (2, "'heartwarming' + 'despite predictable plot'"),
        "843527": (1, "formulaic/predictable; warmth only indirect"),
        "987686": (2, "cheesy/corny + guilty pleasure/enjoyable"),
        "370663": (0, "formulaic/cliches but warmth describes another film"),
        "152601": (0, "heartwarming but explicitly avoids cliche"),
        "884605": (2, "heartwarming + 'far too predictable'"),
        "956842": (0, "cliches/predictable but no warm response"),
        "25704": (0, "predictable but no warm response"),
        "1259102": (1, "sentimental/cheesy but subverted; poignant"),
        "38317": (2, "heartwarming + 'incredibly predictable'"),
        "1068452": (0, "heartwarming but no cliche/formula evidence"),
        "9602": (2, "not original/unpredictable + heartwarming"),
        "9880": (1, "trope/sub-trope; only mild positive response"),
        "16996": (2, "'cliched' + 'you'll laugh, you'll cry'/has heart"),
        "746036": (0, "generic romance/tropes, but subverts and no warmth"),
        "455207": (1, "predictable but warmth only indirect"),
        "509": (0, "heartwarming but no cliche/formula evidence"),
        "1824": (1, "heartwarming + far-fetched/ridiculous premise"),
        "587792": (1, "formula/cliche and tropes mentioned; warmth indirect"),
        "804": (1, "'Predictable? Cliche? Of course' + mild reward"),
        "11622": (0, "heart warming but no cliche/formula evidence"),
        "843543": (2, "cheesy/cliche plotline + emotionally authentic"),
        "25633": (0, "formulaic but no warm response"),
        "9603": (0, "explicitly avoids lazy tropes; only feel-good"),
        "550205": (0, "heartwarming but no cliche/formula evidence"),
        "137": (1, "trope/cheesy + heartwarming climax"),
        "222935": (2, "predictable/sentimental + touching"),
        "9587": (0, "heartwarming ending but no cliche/formula evidence"),
        "1064213": (1, "predictable/cliched + emotional but not heartwarming"),
        "868759": (0, "tropes but no warm response"),
    },
    "Q3": {
        "30863": (2, "astronaut stranded in space; returns to Earth"),
        "286217": (2, "stranded on Mars; survival and rescue"),
        "339964": (0, "stranded princess but not survival/return premise"),
        "6795": (1, "space + return home, but not stranded astronauts"),
        "435": (0, "astronauts incidental; disaster film on Earth"),
        "945961": (1, "space + survival, not stranded crew returning home"),
        "365942": (1, "space + return to Earth, not stranded/survival"),
        "369972": (0, "astronaut biopic; no stranded/survival objective"),
        "8536": (0, "brief astronaut scene; no stranded/survival"),
        "299687": (0, "survival/left behind, but no astronaut space travel"),
        "75612": (0, "astronaut clones on Earth; not stranded away from Earth"),
        "670292": (0, "space station, but no stranded astronauts"),
        "982843": (0, "space station/survival, but not stranded astronauts"),
        "698": (0, "astronaut/space station, no stranded/survival"),
        "588228": (0, "alien spaceship/survival, not astronauts stranded"),
        "299536": (1, "space + stranded on Titan, but incidental/no survival objective"),
        "436969": (0, "astronauts only in backstory"),
        "320288": (0, "space rescue, no stranded/survival"),
        "70981": (2, "crew isolated on distant moon; survival central"),
        "11802": (2, "astronaut chimps stranded; must return"),
        "10681": (0, "space, but not stranded astronauts"),
        "297222": (1, "alien stranded on Earth; needs return, not astronaut away"),
        "535167": (1, "astronaut/space station + survival, not stranded"),
        "154": (0, "starship rescue, no stranded/survival"),
        "667": (0, "astronauts captured, no stranded/survival"),
        "118340": (0, "space, but no stranded astronaut survival"),
        "49521": (0, "spacecraft/survival of Kryptonians, not astronauts"),
        "335988": (0, "spacecraft, no stranded astronauts"),
        "44943": (0, "alien invasion, not astronauts"),
        "2157": (2, "space travellers stranded; survive and find way home"),
        "14623": (0, "space station peril, not stranded astronauts"),
    },
    "Q4": {
        "339527": (2, "FBI agent + serial killer investigation central"),
        "1032823": (2, "FBI profiler/manhunt for serial killer central"),
        "10871": (2, "FBI agent pursues serial killer central"),
        "602269": (1, "serial killer investigation led by sheriff/detective; FBI later"),
        "9411": (1, "homicide detective investigates serial killer; no FBI"),
        "9544": (1, "NYPD detective + FBI chase serial killer; not FBI-led"),
        "87462": (1, "LAPD detectives hunt serial killer; no FBI"),
        "34314": (0, "serial killer on plane; not an investigation"),
        "55846": (1, "UK police hunt serial killer; no FBI"),
        "12149": (2, "FBI agent investigates 'God's Hand' serial killings"),
        "241": (0, "serial murderers; no FBI investigation"),
        "274": (2, "FBI trainee investigates Buffalo Bill serial killer"),
        "3489": (1, "psychiatrist leads; FBI agent secondary"),
        "6498": (1, "serial murder case/police; no FBI"),
        "9437": (1, "detective leads; FBI agents collaborate"),
        "46342": (1, "detective/profiler hunt serial killer; no FBI"),
        "1226578": (2, "FBI agent assigned serial killer case central"),
        "995926": (1, "Korean detectives hunt serial killer; no FBI"),
        "580489": (0, "serial killer but no FBI investigation"),
        "181283": (1, "MGB agent investigates serial killer; no FBI"),
        "31001": (1, "police investigate serial killer; no FBI"),
        "14937": (1, "Sydney detective investigates murders; no FBI"),
        "807": (1, "homicide detectives hunt serial killer; no FBI"),
        "70585": (0, "serial killer; no investigation"),
        "51215": (1, "detectives track serial killer; no FBI"),
    },
    "Q5": {
        "769": (2, "Italian-American Mafia central; De Niro"),
        "398978": (2, "Italian-American Mafia central; De Niro lead"),
        "1578": (1, "Mafia controls boxing, but film is a boxing biopic"),
        "240": (2, "Corleone Italian-American crime family central; De Niro"),
        "1607": (2, "Italian-American Mafia presence central; De Niro"),
        "524": (2, "Italian-American Mafia central; De Niro lead"),
        "117": (2, "Capone's Italian-American crime organization central; De Niro"),
        "8195": (0, "Russian mafia; explicit false positive"),
        "112205": (2, "Italian-American Mafia family central; De Niro lead"),
        "11371": (0, "heist film; mob debt incidental, not Italian-American mafia"),
        "819": (0, "Irish Mob; not Italian-American"),
        "2142": (0, "police corruption; not Italian-American mafia central"),
    },
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if common.DEFAULT_QRELS.exists() and not args.force:
        raise SystemExit(
            f"{common.DEFAULT_QRELS} already exists; use --force to regenerate "
            "(this overwrites any manual edits)"
        )

    with common.DEFAULT_POOL.open(newline="", encoding="utf-8") as handle:
        pool_rows = list(csv.DictReader(handle))

    missing = []
    for row in pool_rows:
        if row["qid"] not in JUDGMENTS or row["docid"] not in JUDGMENTS[row["qid"]]:
            missing.append(f"{row['qid']}/{row['docid']}")
    if missing:
        raise SystemExit("unjudged pooled documents: " + ", ".join(missing))

    fields = ["qid", "docid", "title", "year", "rel", "judge", "notes"]
    with common.DEFAULT_QRELS.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in pool_rows:
            rel, note = JUDGMENTS[row["qid"]][row["docid"]]
            writer.writerow({
                "qid": row["qid"],
                "docid": row["docid"],
                "title": row["title"],
                "year": row["year"],
                "rel": rel,
                "judge": "preliminary",
                "notes": note,
            })

    print(f"wrote {common.DEFAULT_QRELS} ({len(pool_rows)} judgments)")
    counts: dict[str, dict[int, int]] = {}
    for row in pool_rows:
        rel, _ = JUDGMENTS[row["qid"]][row["docid"]]
        counts.setdefault(row["qid"], {}).setdefault(rel, 0)
        counts[row["qid"]][rel] += 1
    for qid in common.QIDS:
        grades = counts[qid]
        print(f"  {qid}: rel2={grades.get(2, 0)} rel1={grades.get(1, 0)} rel0={grades.get(0, 0)}")


if __name__ == "__main__":
    main()
