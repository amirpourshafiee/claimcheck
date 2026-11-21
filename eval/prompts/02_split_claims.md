# Prompt 2: split the answers into atomic claims

How to use: in the SAME chat, after Prompt 1's reply, send everything below the line as the next
message. Copy the code block from the reply into `eval/dataset/claims_raw.csv` (plain text, UTF-8).
Then check the split yourself (see LABELING_GUIDE.md, step 2). Do not ask the chatbot to judge
whether any claim is true or supported. Labeling must be yours alone.

---

Split each answer you just wrote into atomic claims.

Rules:

1. One claim = one checkable fact. If a sentence contains two facts, make two claims.
2. Each claim must stand alone: replace pronouns like "it", "they", "the device" with the
   specific name, so a reader who sees only the claim knows what it is about.
3. Keep the claim's meaning exactly. Do not add facts, do not drop qualifiers such as "about" or
   "may", and do not correct anything you think is wrong.
4. Each claim keeps the citation marker of the sentence it came from. Write it in the
   citation_id column as S1 or S2, without brackets.
5. Do not judge whether any claim is true or supported.
6. Number claims per answer: q01-c01, q01-c02, ..., q02-c01, and so on.
7. Per answer, output at most 3 claims whose citation is S1 and at most 3 whose citation is S2.
   Within each citation, keep the first 3 claims in the order they appear in the answer and
   drop the rest. Never choose which claims to drop by how hard or easy they look. Number the
   claims in the order they appear in the answer (S1 and S2 claims interleaved as written).

Output ONLY one CSV code block with this exact header and one row per claim. Put any claim_text
that contains a comma inside double quotes.

claim_id,answer_id,claim_text,citation_id
