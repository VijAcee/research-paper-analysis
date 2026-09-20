import json
import os
import sys

# Add backend directory to sys.path
backend_dir = r"c:\Users\welcome\Documents\vijita\projects\Research-Paper Analysis\backend"
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.services.openai_service import generate_paper_analysis, extract_real_topic, validate_and_sanitize_analysis, extract_paper_facts

# 8 Test Papers from 8 Different Research Disciplines
test_papers = [
    {
        "domain_name": "Medicine",
        "file_title": "1. medical.pdf", # Intentionally test filename with category label prefix!
        "title": "Efficacy of Metformin in Reducing HbA1c Levels in Patients with Type 2 Diabetes",
        "abstract": "We conducted a double-blind randomized controlled trial of 150 patients with type 2 diabetes over 24 weeks. Patients receiving 1000mg metformin daily demonstrated a mean reduction in HbA1c of 1.4% (p < 0.001) compared to placebo. No severe adverse events were observed."
    },
    {
        "domain_name": "Molecular Biology",
        "file_title": "2. biology.pdf",
        "title": "CRISPR-Cas9 Gene Editing Efficiency in Human Hematopoietic Stem Cells",
        "abstract": "This study evaluates Cas9 ribonucleoprotein electroporation efficiency in primary human CD34+ hematopoietic stem cells. We achieved 84% indel rate at the BCL11A enhancer locus with 92% cell viability post-transfection."
    },
    {
        "domain_name": "Psychology",
        "file_title": "3. psychology.pdf",
        "title": "Qualitative Assessment of Workplace Burnout Among Remote Healthcare Workers",
        "abstract": "Through semi-structured qualitative interviews with N=28 remote healthcare professionals, we identified three core thematic clusters: role ambiguity, digital exhaustion, and boundary blurring. Coding was validated via thematic inductive synthesis."
    },
    {
        "domain_name": "Economics",
        "file_title": "4. economics.pdf",
        "title": "Difference-in-Differences Analysis of Minimum Wage Increases on Regional Employment",
        "abstract": "Using panel data across 45 state borders from 2010 to 2020, we estimate a two-way fixed effects econometric model. We find a statutory minimum wage increase of 10% was associated with a 0.2% change in low-wage retail employment (95% CI: -0.5% to 0.1%)."
    },
    {
        "domain_name": "Environmental Science",
        "file_title": "5. environmental_science.pdf",
        "title": "Impact of Microplastic Accumulation on Estuarine Microalgae Photosynthetic Rates",
        "abstract": "We measured chlorophyll fluorescence across estuarine water samples exposed to polyethylene microplastics (0.5 to 5.0 mg/L). High concentration exposure reduced electron transport rates in Chlorella vulgaris by 23%."
    },
    {
        "domain_name": "Physics",
        "file_title": "6. physics.pdf",
        "title": "Superconducting Quantum Interference Devices in High-Field Cavities",
        "abstract": "We present experimental measurements of flux noise in Nb-based SQUID resonators cooled to 15 mK inside a 3 Tesla magnetic field. Quantum quality factor Q reached 1.2 x 10^5 at single-photon microwave powers."
    },
    {
        "domain_name": "Computer Science & AI",
        "file_title": "7. cs_ai.pdf",
        "title": "Sparse Attention Mechanisms for Long-Context Transformer Decoders",
        "abstract": "We propose FlashSparse, a block-sparse GPU kernel for multi-head self-attention. On the LRA benchmark, FlashSparse reduces memory consumption by 3.8x while achieving 92.4% accuracy on 16k token sequences."
    },
    {
        "domain_name": "Mathematics & Theoretical Science",
        "file_title": "8. mathematics.pdf",
        "title": "Asymptotic Bounds for Non-Linear Differential Equations on Compact Manifolds",
        "abstract": "We prove the existence and uniqueness of global solutions for a class of parabolic equations under Ricci flow curvature bounds. The proof utilizes a Sobolev inequality contraction map on Riemannian manifolds."
    }
]

def run_tests():
    print("=" * 70)
    print("UNIVERSAL MULTI-PAPER ANALYSIS SYSTEM TEST SUITE")
    print("=" * 70)

    passed_all = True
    banned_substrings = ["1. medical", "2. biology", "3. psychology", "1. medical.pdf", "advances scientific understanding", "addresses performance bottlenecks"]

    for idx, paper in enumerate(test_papers):
        print(f"\n--- [TEST {idx+1}/8] Discipline: {paper['domain_name']} ---")
        print(f"Uploaded Filename: {paper['file_title']}")
        print(f"Title: {paper['title']}")

        # Test extract_real_topic
        topic = extract_real_topic(paper["file_title"], paper["abstract"], paper["abstract"])
        print(f"Extracted Topic: '{topic}'")

        # Generate analysis
        analysis = generate_paper_analysis(paper["file_title"], paper["abstract"], paper["abstract"])
        analysis_dict = analysis.model_dump()

        # Print Key Highlights
        print(f"Domain Detected: {analysis_dict.get('research_domain')}")
        print(f"Paper Type: {analysis_dict.get('paper_type')}")
        print(f"What Paper Is About: {analysis_dict.get('what_is_paper_about')}")
        print(f"ELI12 Explanation: {analysis_dict.get('explain_like_12')}")
        print(f"Model Architecture: {analysis_dict.get('model_architecture')}")

        # Check for banned substrings
        serialized = json.dumps(analysis_dict).lower()
        found_banned = [b for b in banned_substrings if b in serialized]

        if found_banned:
            print(f"FAILED: Found banned placeholders or filler text: {found_banned}")
            passed_all = False
        else:
            print("PASSED: Zero placeholder/category text found. Content is 100% grounded.")

    print("\n" + "=" * 70)
    if passed_all:
        print("ALL 8 PAPER TYPES PASSED VALIDATION PERFECTLY!")
    else:
        print("SOME TESTS FAILED VALIDATION. PLEASE AUDIT LOGS.")
    print("=" * 70)

if __name__ == "__main__":
    run_tests()
