import os
import sys

# Add backend directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.services.openai_service import is_author_or_metadata_text, is_scientific_claim, evaluate_paper_analysis_quality
from app.services.pdf_parser import repair_extracted_pdf_text

def test_metadata_scrubber_and_quality_gate():
    print("Testing Journal Metadata Scrubber, Scientific Claim Classifier & Quality Gate...")

    # Case 1: Corrupted Journal Header Line
    header_line = "TREE3011No.of Pages14 Trends in Ecology & Evolution Review Predicting the impacts on animal groups Marcus Michelangeli"
    repaired_header = repair_extracted_pdf_text(header_line)
    
    assert is_author_or_metadata_text(header_line) == True, "Failed to identify journal header as metadata!"
    assert is_scientific_claim(header_line) == False, "Journal header line should NOT be classified as a scientific claim!"

    print("[OK] Header line correctly identified as metadata and discarded.")

    # Case 2: Authentic Scientific Claim
    claim_line_1 = "Chemical pollution is among the fastest-growing environmental pressures."
    claim_line_2 = "Synthetic chemicals can produce sublethal effects on animal behavior."

    assert is_scientific_claim(claim_line_1) == True, "Valid scientific claim 1 was falsely rejected!"
    assert is_scientific_claim(claim_line_2) == True, "Valid scientific claim 2 was falsely rejected!"

    print("[OK] Valid scientific claims correctly recognized.")

    # Case 3: Quality Gate Verification for Corrupted Output
    corrupted_data = {
        "research_problem": "TREE3011No.of Pages14 Trends in Ecology",
        "main_research_question": "Marcus Michelangeli Trends in Ecology",
        "what_researchers_discovered": "Review Article Trends in Ecology & Evolution"
    }

    evaluated = evaluate_paper_analysis_quality(corrupted_data)
    assert evaluated["is_low_confidence"] == True, "Quality Gate failed to trigger low confidence on corrupted paper!"
    assert "excessive formatting artifacts" in evaluated["confidence_message"], "Quality Gate message missing!"
    assert evaluated["research_problem"] == "Not clearly stated in the paper.", "Corrupted header was not sanitized!"

    print("[OK] Quality Gate successfully flagged low-confidence corrupted paper and provided clear user notice.")

    print("\nSUCCESS: All Journal Metadata & Quality Gate test cases passed!")

if __name__ == "__main__":
    test_metadata_scrubber_and_quality_gate()
