import sys
import os

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.services.pdf_parser import reconstruct_academic_paper
from app.services.openai_service import classify_paper_type, extract_paper_facts, generate_paper_analysis, verify_analysis_quality

sample_amr_survey_text = """
A Survey of AI-Based Technologies for Automatic Modulation Recognition
IEEE Transactions on Communications, Vol. 70, No. 4, April 2024.
Authors: Smith, J., Johnson, K., Lee, M.

ABSTRACT:
Automatic modulation recognition (AMR) plays a vital role in modern wireless communication and radar signal processing. This paper presents a comprehensive survey of recent AI-based technologies for AMR, covering model-based machine-learning approaches and data-driven deep-learning approaches. We examine modulation types used in communication and radar systems, analyze feature extraction mechanisms, discuss performance bottlenecks under low SNR conditions, and outline future research directions.

1. INTRODUCTION
Automatic modulation recognition (AMR) is of vital importance in spectrum monitoring, cognitive radio, and electronic warfare. Signal modulation formats must be recognized accurately without prior knowledge of signal parameters. Legacy feature extraction relies on high-order cumulants and multi-layer perceptrons (MLP). However, early MLP models struggle to capture local feature correlations as modulation complexity increases.

2. MODEL-BASED VS DATA-DRIVEN AMR
Model-based machine learning methods incorporate domain knowledge and likelihood ratio tests. Data-driven deep learning methods learn representations directly from raw I/Q samples using convolutional neural networks (CNNs) and transformers.

3. TECHNICAL CHALLENGES & LOW SNR PERFORMANCE
A major challenge facing existing AMR approaches is performance degradation under low signal-to-noise ratio (SNR) conditions and severe channel fading.

4. CONCLUSION & FUTURE DIRECTIONS
This survey synthesizes AI-based AMR developments and provides a taxonomy for future research in intelligent communication systems.
"""

def test_full_pipeline():
    print("==================================================")
    print("STEP 1: Universal Academic PDF Reconstruction (Prompt 1)")
    print("==================================================")
    reconstructed = reconstruct_academic_paper("A Survey of AI-Based Technologies for AMR", sample_amr_survey_text)
    print("Reconstruction Quality Score:", reconstructed.get("extraction_quality"))
    print("Clean Text snippet:\n", reconstructed.get("clean_text")[:300])

    print("\n==================================================")
    print("STEP 2: Paper Type Classification (Prompt 2a)")
    print("==================================================")
    paper_type_data = classify_paper_type("A Survey of AI-Based Technologies for AMR", sample_amr_survey_text)
    print("Classification Output:", paper_type_data)

    print("\n==================================================")
    print("STEP 3: Fact Extraction")
    print("==================================================")
    facts = extract_paper_facts("A Survey of AI-Based Technologies for AMR", sample_amr_survey_text)
    print("Extracted Facts Keys:", list(facts.keys()))

    print("\n==================================================")
    print("STEP 4: Paper-Type-Aware Analysis Engine (Prompt 2b)")
    print("==================================================")
    analysis = generate_paper_analysis("A Survey of AI-Based Technologies for AMR", sample_amr_survey_text)
    print("Paper Type in Analysis:", analysis.paper_type)
    print("Story Big Picture:", analysis.story_big_picture)
    print("Story Important Caveats:", analysis.story_important_caveats)
    print("Glossary Terms:", analysis.glossary)

    print("\n==================================================")
    print("STEP 5: Quality Gate (Prompt 3)")
    print("==================================================")
    quality = verify_analysis_quality(reconstructed.get("clean_text"), analysis.model_dump())
    print("Quality Gate Output:", quality)

    print("\n=== PIPELINE TEST FINISHED SUCCESSFULLY ===")

if __name__ == "__main__":
    test_full_pipeline()
