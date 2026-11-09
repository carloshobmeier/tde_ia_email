"""Saves Qev's per-email probabilities (validation + test) for the ensemble experiment.

Uses the Portuguese wording, which qev_email_eval.py selected on validation for both tasks.
Run inside the Qev runtime environment:
  python qev_dump_probs.py --project <foco dir> --checkpoint <qev-0.8b dir> --out qev-probs.json
"""
import argparse
import json
import sys
import time
from pathlib import Path

from qev_email_eval import CRITERIA, LABELS


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--device", default=None)
    args = parser.parse_args()

    sys.path.insert(0, str(Path(args.project).resolve()))
    from backend.corpus import CORPUS_VERSION, bootstrap_samples, partition
    from qev.inference import Agent

    agent = Agent(args.checkpoint, backend="torch", device=args.device)
    questions = {task: {"type": "choice", "instructions": text, "criteria": options}
                 for task, (text, options) in CRITERIA["pt"].items()}
    samples = [s for s in bootstrap_samples() if partition(s["group_id"]) in ("validation", "test")]
    probabilities, started = {}, time.perf_counter()
    for index, sample in enumerate(samples, 1):
        answers = agent.predict(sample["text"], questions)["answers"]
        probabilities[sample["id"]] = {task: [answers[task]["probabilities"][label] for label in LABELS[task]]
                                       for task in LABELS}
        if index % 25 == 0:
            print(f"  {index}/{len(samples)}", flush=True)
    Path(args.out).write_text(json.dumps({"corpus_version": CORPUS_VERSION, "wording": "pt", "labels": LABELS,
                                          "device": str(agent.device), "probabilities": probabilities}))
    print(f"Saved {len(probabilities)} emails in {time.perf_counter() - started:.0f} s to {args.out}")


if __name__ == "__main__":
    main()
