# Prompt 1: generate the answers

How to use: open a FRESH chat (no files attached, web search off if there is a toggle). Paste
everything below the line as one message. If you can, use a chatbot from a different company
than the judge you will use later (see LABELING_GUIDE.md, "Generator bias"). Whatever you use,
write down the product name, model name shown in the UI, and the date. The datasheet needs it.
Save the full reply to `eval/answers/answers_raw.md`.

---

You are helping build a test set for a citation checker. Answer each of the 12 questions below
from your own knowledge. Do not use web search or tools.

For each question you may cite ONLY the sources listed under it, by id. You are shown only the
titles of those sources, not their text. Rules:

1. Write one paragraph of 5 to 6 sentences (about 90 to 130 words) per question.
2. Every sentence must end with exactly one citation marker, such as [S1] or [S2]. Never put two
   markers on one sentence.
3. Every sentence must state a specific, checkable fact (names, numbers, dates, mechanisms,
   comparisons). No vague commentary and no transitions with no facts in them.
4. Use both sources in each answer, and cite the source you think most likely covers the fact.
5. Write naturally and confidently. Do not hedge, and do not mention that you have not seen the
   sources.

Output format: for each question, one line `ANSWER qNN` followed by its paragraph. No other text.

Questions:

q01. How did ancient and medieval devices model the motion of the sky?
    Allowed citations: [S1] = "Antikythera mechanism", [S2] = "Astrolabe"
q02. How do lead-acid and lithium-ion batteries differ in design and typical use?
    Allowed citations: [S1] = "Lead–acid battery", [S2] = "Lithium-ion battery"
q03. What did the Voyager 1 and Voyager 2 space probes accomplish?
    Allowed citations: [S1] = "Voyager 1", [S2] = "Voyager 2"
q04. How do tardigrades survive harsh conditions compared with other extremophiles?
    Allowed citations: [S1] = "Tardigrade", [S2] = "Extremophile"
q05. How were ancient writing systems deciphered, using the Rosetta Stone and Linear B as examples?
    Allowed citations: [S1] = "Rosetta Stone", [S2] = "Linear B"
q06. How do CRISPR and PCR work, and how do they differ?
    Allowed citations: [S1] = "CRISPR", [S2] = "Polymerase chain reaction"
q07. Why did the Tacoma Narrows Bridge collapse, and what caused the Millennium Bridge wobble?
    Allowed citations: [S1] = "Tacoma Narrows Bridge (1940)", [S2] = "Millennium Bridge, London"
q08. How did the transistor replace the vacuum tube?
    Allowed citations: [S1] = "Transistor", [S2] = "Vacuum tube"
q09. How do the Panama Canal and the Suez Canal compare?
    Allowed citations: [S1] = "Panama Canal", [S2] = "Suez Canal"
q10. How did movable type change printing in Europe?
    Allowed citations: [S1] = "Movable type", [S2] = "Printing press"
q11. How did the Enigma machine and the Lorenz cipher differ, and how were they broken?
    Allowed citations: [S1] = "Enigma machine", [S2] = "Lorenz cipher"
q12. What went wrong on Apollo 13, and how did it differ from Apollo 11?
    Allowed citations: [S1] = "Apollo 13", [S2] = "Apollo 11"
