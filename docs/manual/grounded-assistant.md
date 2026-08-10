# Grounded Knowledge Assistant

The project Assistant uses the configured local Ollama model to explain a system from bounded project evidence. It retrieves authoritative schema objects, relationships, indexed document chunks and representative sample values before asking the model to compose an answer.

## Ask a question

1. Open a project and select **Assistant**.
2. Enter a focused question such as `How does supplier data connect to purchase orders?`.
3. Select **Retrieve evidence and ask Ollama**.
4. Review the answer, limitations, citations and the retrieved evidence panel.

Each exchange is stored in project-scoped history with the model name, requesting user and exact bounded evidence context. Document citations open the precise stored chunk. Schema, relationship and sample citations retain their evidence identifiers in the answer history.

## Grounding and safety

- The assistant receives at most 32 evidence items, with each evidence family independently bounded during retrieval.
- Document and sample contents are labelled as untrusted evidence, never instructions.
- The structured response must use only supplied evidence identifiers.
- Answers with retrieved evidence must contain citations; invented citation identifiers are rejected.
- Empty retrieval requires an explicit insufficiency limitation.
- Assistant answers do not invoke tools automatically. The page separately exposes three user-invoked, typed read tools and no SQL execution.

## Typed read tools

The Assistant page exposes an explicit read-tool form:

- `schema.inspect` accepts one table name and returns its typed definition and direct relationships.
- `documents.read_chunk` accepts one integer chunk ID and returns that citation only when it belongs to the current project.
- `sql.validate` accepts one SQL statement, applies the deterministic read-only validator and returns referenced objects with `executable: false`.

Every invocation is persisted and audited as completed or rejected. Unknown tools—including shell or arbitrary function names—are rejected. Tool arguments cannot select filesystem paths, execute SQL, mutate data or bypass project scoping.

### Opt-in model-selected tools

Select **Allow Ollama to select up to three read-only tools** when asking a question if retrieval alone may be insufficient. Ollama returns a structured tool plan, but the application enforces the same fixed allow-list and executes each request itself. Successful results become additional evidence with `tool:{id}` citations before the final answer is generated. Rejected calls remain visible in Tool activity and are not supplied as factual evidence.

This option is off by default for each question. Enabling it does not broaden the read-tool catalogue: shell, filesystem, network and SQL execution remain unavailable regardless of what the model requests.

## Reviewable document-link actions

Select **Allow Ollama to suggest reviewable document links** to let the assistant propose links between an existing project document and an exact table or field in the active model. The option is off by default and permits no other mutation type.

Each suggestion is persisted as a proposed `AIAction`; it does not create a link. Review its document, target and reason, then select **Confirm link** or **Reject**. Confirmation rechecks project ownership, the active model revision, the exact target and duplicate links before applying the deterministic link operation. Model drift or an invalid/duplicate target prevents application. Both proposal and decision are audited.

## Explicit follow-up context

Use **Optional follow-up context** to select one earlier exchange from the current project. No conversation history is included automatically. The selected question, bounded answer and its citation labels are added as one untrusted evidence item, and the new exchange records a persistent link to its parent. Follow-up citations link back to that exchange.

Only one parent exchange can be selected, and cross-project exchange IDs are rejected. Prior assistant wording is context rather than authoritative schema: important claims still require review against the original evidence.

Answers may still be incomplete or poorly phrased. Verify important claims against the displayed evidence and citations. Additional mutation types and multi-exchange context strategies remain later work.

## SQL impact diagrams

After a statement passes deterministic validation, the SQL Workbench displays the active model beneath the validation result. Referenced tables use a pale-yellow heading and explicitly named fields use amber rows. Confirming an AI SQL proposal loads the statement and opens this preview automatically; it does not execute the query.
