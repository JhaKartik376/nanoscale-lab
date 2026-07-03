"""services/chat.py

Optional Claude-backed tutor, grounded in the current sim numbers. Degrades to
the deterministic rule-based engine when no API key / SDK is available, so the
endpoint never hard-fails.
"""
import os
from services.explanation_engine import explain

MODEL = "claude-opus-4-8"
SYSTEM = (
    "You are a semiconductor scaling tutor. Ground answers in the provided "
    "sim numbers. When you make a quantitative claim, cite the specific value "
    "from the context (e.g. 'leakage is 41% of on-current'). If the sim numbers "
    "don't support an answer, say so rather than inventing figures. Keep answers "
    "to a few sentences, at the level of a curious student."
)


def _context_block(results: dict, node: str, mode: str) -> str:
    verdict = explain(results, node, mode)["verdict"]
    return "\n".join([
        f"Node: {node}   Mode: {mode}",
        f"Overall verdict: {verdict['label']} (severity {verdict['severity']}/4)",
        f"On/off ratio: {results.get('on_off_ratio', 0):,.0f}x",
        f"Subthreshold swing: {results.get('ss_mv_dec')} mV/dec (ideal 60)",
        f"Leakage fraction (I_off/I_on): {results.get('leakage_frac', 0):.2%}",
        f"Barrier tunneling probability: {results.get('tunnel_prob', 0):.2e}",
        f"Gate control (1.0 = ideal): {results.get('gate_control')}",
        f"I_on: {results.get('i_on_a_um', 0):.2e} A/um   "
        f"I_off: {results.get('i_off_a_um', 0):.2e} A/um",
    ])


def _fallback(results, node, mode) -> dict:
    e = explain(results, node, mode)
    text = e["headline"] + " " + " ".join(i["text"] for i in e["insights"][:2])
    return {"source": "rule-based-fallback", "answer": text}


def chat(results: dict, node: str, mode: str, question: str) -> dict:
    """Answer a free-form question grounded in the current sim numbers."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return _fallback(results, node, mode)
    try:
        import anthropic
        client = anthropic.Anthropic()
        ctx = _context_block(results, node, mode)
        resp = client.messages.create(
            model=MODEL, max_tokens=1024, system=SYSTEM,
            messages=[{"role": "user",
                       "content": f"Current simulation:\n{ctx}\n\n"
                                  f"Student question: {question}"}],
        )
        answer = next((b.text for b in resp.content if b.type == "text"), "")
        return {"source": "claude", "answer": answer}
    except Exception:
        return _fallback(results, node, mode)
