# AI Record Generator

The AI Record Generator uses a configured local Ollama model to propose synthetic records for one selected table. It adapts Tender Designer's bounded LLM/action pattern into a table-first workspace: table navigation replaces chat history on the left, generation controls and schema context occupy the centre, and reviewable proposals appear on the right.

## Prerequisites

- An active approved project revision.
- At least one sample dataset.
- Ollama configured under **Settings** and the selected model installed, or another model name entered on the page.

## Generate a proposal

1. Open **AI record generator** from the project workbench.
2. Select a table from the left panel.
3. Choose the target sample dataset.
4. Request between 1 and 20 records.
5. Add scenario, range or edge-case instructions.
6. Select **Generate proposed records**.

The service sends the selected table's exact fields, types, markers, attributes and up to 20 existing rows to the local Ollama endpoint. For every outgoing relationship, it also supplies the allowed foreign-key values from the related table in the selected dataset. The prompt requires synthetic, non-sensitive output with exact field names and forbids invented references. Returned JSON must have the expected structure and every row must pass deterministic type, length, nullability and foreign-key validation.

Generate referenced/parent records first. For example, add suppliers before asking the AI to generate purchase orders. If a related table has no rows, the generator reports that no valid foreign-key choices exist instead of creating a proposal that will later fail during sandbox construction.

## Review and confirm

Generated rows are saved as an `AIAction` with `proposed` status, not as sample data. Review the JSON in the proposal panel:

- **Confirm and add** revalidates the rows and their foreign-key references against the current active revision and current dataset, then appends them.
- **Reject** records the rejection and creates no sample rows.

If the active model or dataset changes after generation, confirmation is refused and a new proposal is required. Applied and rejected proposals remain visible for audit context.

Generated data can still be inaccurate or inappropriate despite structural validation. Review business meaning, uniqueness and sensitivity before confirmation.

## Configure Ollama

Administrators can open **Settings** and edit the Ollama URL and default model. These catalogue settings take effect immediately and override the `OLLAMA_URL` and `OLLAMA_MODEL` environment fallbacks. The per-generation model field can temporarily override only the default model; it does not change the saved setting.
