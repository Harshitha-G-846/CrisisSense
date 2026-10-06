APPROVED — proceed with PHASE 1.

Before coding, follow these constraints strictly:

1. Create ONLY:
   backend/member2/schemas.py
   backend/tests/test_member2_contract.py

2. Do NOT modify:
   - Member 1
   - main.py
   - requirements.txt
   - datasets
   - models

3. Keep the implementation small and precise.
   No unnecessary abstractions.

4. Do not create additional folders/files.

5. Define the minimum stable Pydantic schemas needed for:
   - EvidenceItem
   - CurrentnessResult
   - Member1Context
   - extracted details if genuinely necessary
   - currentness/action enums

6. Use:
   CURRENT | OLD | UNCERTAIN

   and:

   ALLOW | HUMAN_VERIFICATION_REQUIRED

7. Evidence must distinguish:
   - supporting CURRENT evidence
   - supporting OLD evidence
   - neutral/missing evidence

   "No reuse match found" must NOT be treated as proof that media is current.

8. Add concise contract tests covering:
   - valid CURRENT result
   - valid OLD result
   - valid UNCERTAIN result
   - confidence range 0.0–1.0
   - invalid enum values
   - malformed evidence

9. Do NOT implement temporal logic yet.

10. Do NOT implement OCR, video, audio, reuse detection, fusion, or API yet.

11. After implementation:
   - run the contract tests
   - report exactly what files changed
   - report test results
   - briefly explain the schema

Do not continue to Phase 2 automatically.
STOP after Phase 1.