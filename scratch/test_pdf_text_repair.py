import os
import sys

# Add backend directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.services.pdf_parser import repair_extracted_pdf_text

def test_pdf_repair_cases():
    print("Testing PDF Text Repair Engine...")

    # Case 1: Concatenated tokens & hyphenated word breaks
    mangled_sample = """—Automaticmodulationrecognition(AMR)isofvital improve system efficiency...
efficient spectrum utilization and resistance to electronic inter-
ference... [1] [2-4] (Smith et al., 2020)
IEEE TRANSACTIONS ON COMMUNICATIONS, VOL. 70, NO. 4
References
[1] J. Doe, "Modulation recognition," 2021."""

    repaired = repair_extracted_pdf_text(mangled_sample)
    print("\nOriginal Text:\n", mangled_sample)
    print("-" * 50)
    print("Repaired Text:\n", repaired)
    print("=" * 50)

    # Assertions
    assert "interference" in repaired, "Hyphenated word break 'inter-\nference' was not repaired!"
    assert "Automatic" in repaired, "Concatenated title words not fixed!"
    assert "[1]" not in repaired, "Bracketed citation [1] was not scrubbed!"
    assert "[2-4]" not in repaired, "Bracketed citation [2-4] was not scrubbed!"
    assert "Smith et al." not in repaired, "Parenthetical citation was not scrubbed!"
    assert "IEEE TRANSACTIONS" not in repaired, "Publisher footer was not scrubbed!"
    assert "J. Doe" not in repaired, "References section was not truncated!"

    print("\nSUCCESS: All PDF text repair test cases passed!")

if __name__ == "__main__":
    test_pdf_repair_cases()
