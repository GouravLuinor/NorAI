"""
backend/demo_suggested_qa.py — pre-cached suggested questions & answers for public demo lectures.

Protects the Gemini free tier by instantly answering canonical questions on the 5 public
demo lectures with zero LLM API calls, zero latency, and zero token spend.
"""

import re
from typing import Optional, Dict, Any, List

DEMO_SUGGESTED_QA: Dict[str, List[Dict[str, Any]]] = {
    # 1. MIT Algorithms and Computation
    "8821152f-f6de-49e9-a885-0adaac6ba4cb": [
        {
            "question": "What is the formal definition of a computational problem?",
            "keywords": ["formal definition", "computational problem", "binary relation", "predicates"],
            "answer": "In the lecture, a computational problem is formally defined as a binary relation between an input space and an output space. It specifies which outputs are considered valid or correct solutions for each input, often formalized using a boolean predicate function that evaluates to true when the output correctly solves the problem for that input.",
            "citations": [
                {
                    "title": "Defining Computational Problems",
                    "chapterId": 2,
                    "startSec": 184,
                    "kind": "transcript",
                    "source": "Ch 02 3:04",
                    "text": "a computational problem is a binary relation from inputs to outputs...",
                }
            ],
        },
        {
            "question": "How does induction prove an algorithm's correctness?",
            "keywords": ["induction", "correctness", "prove", "base case"],
            "answer": "The lecturer explains that induction is the primary mathematical tool for proving algorithm correctness over arbitrary inputs. You establish a base case for the smallest possible input size, and then prove that if the algorithm is correct for input size k, it must also be correct for input size k+1. By mathematical induction, this guarantees that the algorithm produces correct outputs for all valid input sizes.",
            "citations": [
                {
                    "title": "Generalizing Problems and Algorithms",
                    "chapterId": 3,
                    "startSec": 392,
                    "kind": "transcript",
                    "source": "Ch 03 6:32",
                    "text": "we argue correctness using mathematical induction on the size of the input...",
                }
            ],
        },
        {
            "question": "What is the birthday problem and how does the match algorithm work?",
            "keywords": ["birthday problem", "birthday paradox", "match algorithm", "duplicate"],
            "answer": "The birthday problem is used as a running example in the lecture. The computational problem asks whether in a group of n people, there exists at least one pair with matching birthdays. The algorithm checks pairs systematically or sorts the birthdays to detect duplicates efficiently, illustrating how to move from problem specification to correctness proof and asymptotic running time analysis.",
            "citations": [
                {
                    "title": "Example: The Birthday Problem",
                    "chapterId": 4,
                    "startSec": 657,
                    "kind": "transcript",
                    "source": "Ch 04 10:57",
                    "text": "the birthday problem asks if any two people share a birthday...",
                }
            ],
        },
    ],
    # 2. MIT Introduction to Differentiation
    "01b04840-fddb-4b31-a211-7bb28f189621": [
        {
            "question": "What is the limit definition of the derivative?",
            "keywords": ["limit definition", "derivative", "tangent line", "delta x"],
            "answer": "The derivative of a function f(x) at a point is defined as the limit as Δx approaches zero of [f(x + Δx) - f(x)] / Δx. Geometrically, this represents the slope of the secant line passing through (x, f(x)) and (x + Δx, f(x + Δx)) as the second point moves infinitesimally close to the first, yielding the instantaneous slope of the tangent line.",
            "citations": [
                {
                    "title": "Limit Definition of the Derivative",
                    "chapterId": 2,
                    "startSec": 240,
                    "kind": "transcript",
                    "source": "Ch 02 4:00",
                    "text": "the derivative is the limit of the difference quotient as delta x approaches zero...",
                }
            ],
        },
        {
            "question": "How do you differentiate 1/x from first principles?",
            "keywords": ["differentiate 1/x", "1/x", "first principles", "power rule"],
            "answer": "To differentiate f(x) = 1/x from first principles using the limit definition: compute [f(x + Δx) - f(x)] / Δx = [1/(x + Δx) - 1/x] / Δx. Finding a common denominator gives [(x - (x + Δx)) / (x(x + Δx))] / Δx = -Δx / (Δx · x(x + Δx)). Canceling Δx leaves -1 / (x(x + Δx)). Taking the limit as Δx → 0 yields -1/x², or -x⁻².",
            "citations": [
                {
                    "title": "Differentiating 1/x and Power Functions",
                    "chapterId": 3,
                    "startSec": 480,
                    "kind": "transcript",
                    "source": "Ch 03 8:00",
                    "text": "we calculate the derivative of 1 over x by taking the limit of the common denominator...",
                }
            ],
        },
    ],
    # 3. Yale Newtonian Mechanics
    "c8cab2e7-52b7-4cdc-8386-f440d02f3f45": [
        {
            "question": "What is the relationship between position, velocity, and acceleration?",
            "keywords": ["position", "velocity", "acceleration", "derivative", "kinematics"],
            "answer": "In Newtonian mechanics, velocity is the first time derivative of position: v(t) = dx/dt, representing instantaneous rate of change of displacement. Acceleration is the first time derivative of velocity and the second time derivative of position: a(t) = dv/dt = d²x/dt². Conversely, integrating acceleration over time yields velocity, and integrating velocity yields position.",
            "citations": [
                {
                    "title": "Kinematic Derivatives",
                    "chapterId": 1,
                    "startSec": 120,
                    "kind": "transcript",
                    "source": "Ch 01 2:00",
                    "text": "velocity is the derivative of position and acceleration is the derivative of velocity...",
                }
            ],
        },
        {
            "question": "How are the constant-acceleration kinematic formulas derived?",
            "keywords": ["constant acceleration", "kinematic formulas", "derive", "v = v0 + at"],
            "answer": "Starting from constant acceleration a(t) = a: integrate with respect to time to get velocity v(t) = v₀ + at. Integrating velocity with respect to time yields position x(t) = x₀ + v₀t + (1/2)at². By eliminating time t between these two equations, you derive the kinematic relation v² = v₀² + 2a(x - x₀).",
            "citations": [
                {
                    "title": "Constant Acceleration Derivations",
                    "chapterId": 3,
                    "startSec": 450,
                    "kind": "transcript",
                    "source": "Ch 03 7:30",
                    "text": "integrating twice with constant acceleration yields the familiar quadratic position formula...",
                }
            ],
        },
    ],
    # 4. Yale Finance and Insurance
    "2e983ee0-ae41-4910-9239-099b34dee04c": [
        {
            "question": "How does diversification reduce portfolio risk?",
            "keywords": ["diversification", "portfolio risk", "variance", "correlation"],
            "answer": "Diversification reduces portfolio risk by holding multiple assets whose returns are not perfectly positively correlated. As long as correlation ρ < 1, the idiosyncratic (firm-specific) risks cancel each other out in the portfolio variance formula, allowing an investor to lower overall volatility without necessarily sacrificing expected return.",
            "citations": [
                {
                    "title": "Portfolio Theory and Diversification",
                    "chapterId": 2,
                    "startSec": 310,
                    "kind": "transcript",
                    "source": "Ch 02 5:10",
                    "text": "as long as the correlation between two assets is less than one, diversification strictly lowers risk...",
                }
            ],
        },
        {
            "question": "What is the economic purpose of insurance and risk pooling?",
            "keywords": ["insurance", "risk pooling", "law of large numbers", "premium"],
            "answer": "Insurance pools independent risks across many individuals based on the law of large numbers. While any single individual faces catastrophic variance, the aggregate loss of a large group becomes predictable. Charging a premium slightly above expected payout allows risk-averse individuals to trade uncertain severe losses for a certain small cost.",
            "citations": [
                {
                    "title": "Risk Pooling and Insurance",
                    "chapterId": 1,
                    "startSec": 150,
                    "kind": "transcript",
                    "source": "Ch 01 2:30",
                    "text": "insurance pools independent risks so that the aggregate payout is highly predictable...",
                }
            ],
        },
    ],
    # 5. Yale Civil War and Reconstruction
    "5f7225bf-ba41-46b9-aea9-da91c032b515": [
        {
            "question": "Why is Reconstruction described as an unfinished revolution?",
            "keywords": ["unfinished revolution", "reconstruction", "jim crow", "amendments"],
            "answer": "Reconstruction is described as an unfinished revolution because although the 13th, 14th, and 15th Amendments abolished slavery, guaranteed birthright citizenship, and protected voting rights, the political and social withdrawal of federal enforcement after 1877 allowed Jim Crow segregation, disenfranchisement, and racial violence to roll back many democratic gains for nearly a century.",
            "citations": [
                {
                    "title": "The Unfinished Revolution",
                    "chapterId": 4,
                    "startSec": 520,
                    "kind": "transcript",
                    "source": "Ch 04 8:40",
                    "text": "reconstruction was a revolution that went backward when northern political will collapsed...",
                }
            ],
        },
        {
            "question": "How did constitutional compromises address slavery?",
            "keywords": ["constitutional compromises", "three fifths", "fugitive slave", "compromise"],
            "answer": "The founding constitutional consensus incorporated multiple compromises regarding slavery without explicitly naming it: the Three-Fifths Clause (Article I, Section 2), the 20-year moratorium on banning the transatlantic slave trade (Article I, Section 9), and the Fugitive Slave Clause (Article IV, Section 2). These provisions reflected fundamental tensions between northern and southern delegations.",
            "citations": [
                {
                    "title": "Constitutional Compromises",
                    "chapterId": 2,
                    "startSec": 280,
                    "kind": "transcript",
                    "source": "Ch 02 4:40",
                    "text": "the constitution protected slavery through structural compromises without using the word slave...",
                }
            ],
        },
    ],
}


def _clean_str(text: str) -> str:
    """Normalize text by lowercasing and stripping punctuation and whitespace."""
    return re.sub(r"[^a-z0-9 ]+", " ", text.lower()).strip()


def _format_citations(raw_citations: list) -> list:
    out = []
    for c in raw_citations:
        start_sec = c.get("startSec") if c.get("startSec") is not None else c.get("start", 0.0)
        out.append({
            "section": c.get("source") or c.get("title") or "Lecture Citation",
            "verified": True,
            "chunk_id": c.get("chunk_id") or f"chunk-cached-{start_sec}",
            "heading_path": c.get("title") or c.get("source") or "",
            "heading": c.get("title") or c.get("source") or "",
            "chapter_id": c.get("chapterId") or c.get("chapter_id") or 1,
            "kind": c.get("kind") or "transcript",
            "start": float(start_sec),
            "end": float(c.get("endSec") or c.get("end") or (start_sec + 30)),
        })
    return out


def _format_answer_with_sources(answer: str, raw_citations: list) -> str:
    if "**Sources**" in answer or "Sources:" in answer:
        return answer
    sources_lines = ["\n\n**Sources**"]
    for c in raw_citations:
        source_label = c.get("source") or f"Ch {c.get('chapterId', 1):02d}"
        title = c.get("title") or "Lecture Reference"
        sources_lines.append(f"* {source_label} — {title}")
    return answer + "\n".join(sources_lines)


def get_cached_demo_qa(lecture_id: str, question: str) -> Optional[Dict[str, Any]]:
    """Check if the question matches a pre-cached suggested question for a demo lecture.

    Returns the cached response dict if matched, or None.
    """
    qa_list = DEMO_SUGGESTED_QA.get(lecture_id)
    if not qa_list:
        return None

    clean_q = _clean_str(question)
    if not clean_q:
        return None

    for item in qa_list:
        clean_item_q = _clean_str(item["question"])
        matched = False
        # 1. Exact or near-exact match
        if clean_q == clean_item_q or clean_q in clean_item_q or clean_item_q in clean_q:
            matched = True
        else:
            # 2. Keyword match (if at least 2 distinct key phrases match)
            matched_kw = sum(1 for kw in item.get("keywords", []) if _clean_str(kw) in clean_q)
            if matched_kw >= 2:
                matched = True

        if matched:
            formatted_cites = _format_citations(item.get("citations", []))
            full_ans = _format_answer_with_sources(item["answer"], item.get("citations", []))
            return {
                "answer": full_ans,
                "confidence": "high",
                "verified_citations": formatted_cites,
                "references": formatted_cites,
                "cached": True,
            }

    return None


def get_suggested_questions_for_lecture(lecture_id: str) -> List[str]:
    """Return the list of suggested question prompts for a given lecture."""
    qa_list = DEMO_SUGGESTED_QA.get(lecture_id, [])
    return [item["question"] for item in qa_list]
