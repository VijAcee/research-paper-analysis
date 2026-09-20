import sys
import os

# Append app to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend', 'app')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))

from services.pdf_parser import clean_raw_pdf_text, extract_structured_sections
from services.openai_service import build_paper_memory, validate_paper_memory, generate_analysis_from_paper_memory, get_mock_analysis

def run_tests():
    print("======================================================================")
    print("TEST 1: Document Cleaning & Section Detection (Ecology Header Junk)")
    print("======================================================================")
    
    messy_pdf_text = """
    TREE3011 No. of Pages 14 Trends in Ecology & Evolution Review
    Predicting the impacts on animal groups
    Marcus Michelangeli
    Department of Biological Sciences, Monash University, Australia

    Abstract
    Chemical pollution is among the fastest-growing environmental pressures on wildlife globally.
    However, predicting its impacts on group-living animals remains challenging.

    Methods
    We conducted systematic behavioral assays across 50 groups of fish to evaluate social cohesion.

    Results
    Exposed groups showed a 35% reduction in polarized alignment compared to unexposed controls.

    Discussion
    These findings demonstrate that sublethal chemical exposure alters group dynamics.
    """

    clean_text = clean_raw_pdf_text(messy_pdf_text)
    print("--- CLEAN TEXT OUTPUT ---")
    print(clean_text)

    # Verify header junk removed
    assert "TREE3011" not in clean_text, "Failed: TREE3011 header was not cleaned!"
    assert "No. of Pages" not in clean_text, "Failed: No. of Pages was not cleaned!"
    assert "Department of Biological Sciences" not in clean_text, "Failed: Author affiliation was not cleaned!"
    print("[OK] STEP 1 CLEANING PASSED!")

    sections = extract_structured_sections(clean_text)
    print("--- STRUCTURED SECTIONS ---")
    print("Abstract:", sections.get("abstract"))
    print("Methods:", sections.get("methods"))
    print("Results:", sections.get("results"))
    print("[OK] STEP 2 SECTION DETECTION PASSED!")

    memory = build_paper_memory(sections, "Predicting the impacts on animal groups")
    print("--- PAPER MEMORY LAYER ---")
    print(memory)

    is_valid, val_mem = validate_paper_memory(memory, "Predicting the impacts on animal groups")
    print("--- VALIDATED MEMORY ---")
    print(val_mem)

    # Assert zero author names in findings
    for finding in val_mem["key_findings"]:
        assert "Marcus Michelangeli" not in finding, "Failed: Author name leaked into findings!"
        assert "TREE3011" not in finding, "Failed: Journal header leaked into findings!"
    print("[OK] STEP 3 & STEP 4 MEMORY & VALIDATION PASSED!")

    analysis = generate_analysis_from_paper_memory(val_mem)
    print("--- FINAL GENERATED ANALYSIS ---")
    print("Research Problem:", analysis.get("research_problem"))
    print("Research Question:", analysis.get("main_research_question"))
    print("Methodology:", analysis.get("methodology"))
    print("What Researchers Discovered:", analysis.get("what_researchers_discovered"))
    print("Key Findings:", analysis.get("key_findings"))
    print("[OK] STEP 5 ANALYSIS GENERATION PASSED!")

    print("\n======================================================================")
    print("TEST 2: MALL Paper (Semi-Structured Interview Methodology Isolation)")
    print("======================================================================")

    mall_text = """
    Abstract
    Foreign language learners frequently utilize mobile devices to support their learning activities outside the classroom.
    The aim of this study is to examine how language learners engage with mobile devices and whether those devices meet their learning needs.

    Methods
    We conducted semi-structured interviews with foreign language learners to evaluate their experiences and behaviors.

    Results
    Participants reported using mobile devices for vocabulary acquisition and listening exercises, but effectiveness varied depending on individual goals.
    """

    mall_analysis = get_mock_analysis("Mobile Assisted Language Learning", "", mall_text)
    print("--- MALL ANALYSIS OUTPUT ---")
    print("Research Question:", mall_analysis.get("main_research_question"))
    print("Methodology:", mall_analysis.get("methodology"))
    print("What Researchers Discovered:", mall_analysis.get("what_researchers_discovered"))
    print("Key Findings:", mall_analysis.get("key_findings"))

    # Assert semi-structured interview is inside Methodology ONLY, not Research Question or Findings
    assert "semi-structured interview" in mall_analysis.get("methodology").lower(), "Methodology missing interview protocol!"
    assert "semi-structured interview" not in mall_analysis.get("what_researchers_discovered").lower(), "Interview method leaked into Discoveries!"
    assert "semi-structured interview" not in mall_analysis.get("main_research_question").lower(), "Interview method leaked into Research Question!"
    print("[OK] MALL TEST PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_tests()
