# Conditional offline theory chapter

The optional research panel can generate a deterministic teaching chapter **only after the user confirms** that X represents current, Y represents voltage, and an approximately Ohmic model is relevant. Column names alone never confirm the experiment. Unconfirmed inputs produce a request for context, not a fabricated chapter. This is a narrowly scoped educational increment, not a general textbook-generation or literature system.

## What the chapter contains

The chapter labels the chosen model as a user assertion; provides a symbol/unit/origin table; derives `V = R I` conditionally from a constant `R = V / I` for `I ≠ 0`; distinguishes the fitted intercept from a physical explanation; checks units; includes a clearly labelled illustrative calculation; and discusses residuals, limitations, uncertainty and verification. At zero current the ratio is undefined: the model's zero-voltage statement is an extension of the assumed relationship, not a measurement. User-selected beginner, undergraduate, postgraduate and research levels add different emphasis without changing numerical fits; legacy intermediate and advanced values remain supported. These brief differences are not a complete curriculum.

For a successful linear fit and recognized current/voltage units, the conditional resistance in ohms is the actual fitted slope multiplied by `(voltage unit in V)/(current unit in A)`. Supported units: A, mA, uA, µA and V, mV, uV, µV. The generated value references `fit.parameters.slope` and records its conversion factor and conditional status. Missing or incompatible units, non-linear/failed fits or nonfinite slope do not produce a resistance. The original fit remains authoritative. This unit calculation is not a symbolic proof, and no measurement uncertainty or calibration is invented.

## Outputs and safety

The opt-in chapter is available in the Streamlit theory expander, `results.json` and existing `report.md`/ZIP export. User context is unverified and may contain personal information; review before exporting. Markdown escapes untrusted context. Changing research context invalidates cached live/mock reports through the existing context fingerprint. Research context is not automatically sent to the provider.

No citations, historical claims, instruments, materials or experimental conditions are invented. External references were not retrieved or verified. The chapter must be reviewed by a knowledgeable human; a good fit does not establish a physical law, causation or calibrated instrument accuracy. Broader derivations, literature synthesis, PDF grounding and other disciplines are not implemented.

## Verify

`python -m pytest -q tests/test_theory_engine.py tests/test_research_assistant.py tests/test_result_schema.py tests/test_domain_modules.py` exercises role confirmation, invalid units/models, mixed-prefix conversion, four levels, a real computation using the bundled file, Markdown/JSON/ZIP consistency and AppTest. The bundled sample's provenance should not be represented as independently verified experimental evidence.
