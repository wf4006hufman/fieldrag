"""Evaluation harness.  Run:  python -m app.eval

Metrics:
  - retrieval hit@k : did the expected source appear in retrieved chunks?
  - keyword recall  : fraction of expected keywords present in the answer
  - groundedness    : Gemini-as-judge scores 1-5 that the answer is supported by context
"""
import json
import os

from . import config, gemini, rag

JUDGE_SYSTEM = (
    "You are a strict evaluator. Given a QUESTION, the retrieved CONTEXT, and an ANSWER, "
    "rate 1-5 how well the ANSWER is SUPPORTED by the CONTEXT (5 = fully grounded, "
    "1 = unsupported/hallucinated). Reply with ONLY the integer."
)


def judge(question, context, ans) -> int:
    prompt = f"QUESTION: {question}\n\nCONTEXT:\n{context}\n\nANSWER:\n{ans}"
    txt, _ = gemini.generate(prompt, system=JUDGE_SYSTEM)
    for tok in txt.split():
        if tok.strip().rstrip(".").isdigit():
            return max(1, min(5, int(tok.strip().rstrip("."))))
    return 0


def main():
    path = os.path.join(os.path.dirname(__file__), "..", "eval", "golden.jsonl")
    cases = [json.loads(l) for l in open(path) if l.strip()]

    hits = kw = ground_sum = 0
    rows = []
    for c in cases:
        hitset = rag.retrieve(c["question"], k=config.TOP_K)
        sources = {h["source"] for h in hitset}
        context = "\n\n".join(f"[{h['source']}] {h['content']}" for h in hitset)
        res = rag.answer(c["question"])
        ans = res["answer"]

        hit = 1 if c.get("expect_source") in sources else 0
        kws = c.get("expect_keywords", [])
        kw_hit = sum(1 for k in kws if k.lower() in ans.lower()) / len(kws) if kws else 1.0
        g = judge(c["question"], context, ans)

        hits += hit; kw += kw_hit; ground_sum += g
        rows.append({"q": c["question"], "hit": hit, "kw_recall": round(kw_hit, 2), "ground": g})
        print(f"[{'HIT ' if hit else 'MISS'}] ground={g}/5 kw={kw_hit:.2f}  {c['question'][:60]}")

    n = len(cases)
    report = {
        "n": n,
        "retrieval_hit@k": round(hits / n, 3),
        "keyword_recall": round(kw / n, 3),
        "groundedness_mean": round(ground_sum / n, 2),
        "rows": rows,
    }
    print("\n=== SUMMARY ===")
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}, indent=2))
    out = os.path.join(os.path.dirname(__file__), "..", "eval", "report.json")
    json.dump(report, open(out, "w"), indent=2)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
