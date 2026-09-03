# SentinelLog-AI
Information Security Project
---

# ABSTRACT
Modern networks generate security logs faster than any team can read them, and most of it is routine. Checking everything by hand doesn't scale, and running every log through an LLM is expensive overkill for traffic that's almost certainly benign. SentinelLog AI works on a simpler premise: not every log deserves the same attention.
Machine learning triages incoming logs into Low, Medium, and High risk, based on pattern, frequency, severity, and system sensitivity. Only High-risk events reach an LLM, which explains the incident, flags the likely attack type, maps it to MITRE ATT&CK, and suggests a response like blocking an IP. A dashboard ranks everything by priority.

---

# OBJECTIVES
1. Build a machine learning classifier that sorts incoming logs into Low, Medium, and High risk tiers, based on pattern, frequency, severity, and the importance of the system the log came from not by treating every entry as a potential threat.
2. Parse and structure raw log data automatically, so the system can process high volumes without manual formatting or cleanup.
3. Limit LLM involvement to High-risk events only, keeping routine and low-risk logs out of the expensive analysis path entirely.
4. Use the LLM, when it is invoked, to explain flagged incidents in plain language, identify the probable attack type, and map the observed behavior to the MITRE ATT&CK framework.
5. Produce response recommendations for high-risk incidents rather than raw alerts with no next step.
   
---
