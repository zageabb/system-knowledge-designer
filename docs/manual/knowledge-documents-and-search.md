# Knowledge documents and local search

The project Knowledge page stores source documents beneath the application-managed data directory, extracts searchable passages and returns project-scoped citations. Search is local through SQLite FTS5; document contents are not sent to Ollama or an external search provider.

## Upload and index

1. Open a project and select **Knowledge**.
2. Select **Upload document**.
3. Choose a supported TXT, Markdown, CSV, PDF, DOCX, XLSX, EML or ZIP file. Text formats must use UTF-8.
4. Optionally provide a title, then select provenance and classification.
5. Select **Upload and index**.

The application ignores directory components in the supplied filename, generates its own managed storage name, calculates a SHA-256 content hash, extracts text and divides it into bounded chunks. Markdown and DOCX headings become citation locators; plain text uses chunk locators; PDF citations retain page numbers; CSV and XLSX headers label values while citations retain source rows and worksheet names; EML citations retain message date and subject.

Uploads are capped by the application request limit. PDF page/text extraction and workbook cell counts are bounded. DOCX/XLSX packages are checked for valid ZIP structure, entry count, expanded size and extreme compression ratios before parsing. Standalone ZIP ingestion is non-recursive and memory-only; it indexes only UTF-8 TXT, Markdown and CSV members, retains the member filename in each locator, and applies the same archive limits. Empty files, unsupported extensions, invalid signatures and invalid UTF-8 are rejected.

MSG and OCR for scanned PDFs remain planned and are not accepted by this development slice. EML currently indexes plain-text message bodies; HTML-only bodies and attachments are not indexed. Image-only PDF pages produce no text until OCR support is added.

## Delete a document

Select **Delete version** and confirm the warning. The application removes that version's FTS entries, chunks, catalogue record and managed original file. Remaining version lineage is reconnected where necessary. The action is audited and cannot be undone.

## Upload a new version

Select **Upload new version** beside an existing document and choose the replacement source. The application runs the complete validation, extraction and indexing pipeline, then creates a new immutable document record in the same version family. It keeps the shared title/classification defaults, assigns the next version number, and records the predecessor.

Prior versions, their chunks and their citations remain searchable and openable. The document table labels each record with its version number. This preserves historical evidence instead of silently replacing extracted text.

## Link documents to the model

With an approved active revision, select **Link to model** beside a document and choose an authoritative table or column. The application validates the selected target against the active parsed model and stores the revision that defined it. Duplicate and unknown targets are rejected.

Links appear in the document list and on every citation page for that document. Select **×** beside a link to remove it. Creating and removing links is audited. A link remains revision-bound when a later model is approved, preserving what the document was linked to at the time; future coverage tooling will flag links whose targets no longer exist in the active revision.

Only direct user actions create links in this slice. Future AI suggestions must remain proposals until explicitly confirmed.

### Link a specific passage

Open a search-result citation and use **Link this passage to** to attach only that chunk to an active table or column. Passage links are separately revision-bound, validated and audited. They appear under **This cited passage** and can be removed without changing whole-document links. Use document links when the complete source explains an object; use passage links when only a page, section, worksheet range or message passage is relevant.

## Review documentation coverage

The Knowledge page reports active-model coverage for tables and columns, plus the number of documents without any document- or passage-level model link. Counts use unique valid targets, so several passages linked to one table still count as one covered table.

After a new model revision is approved, historical links remain bound to the revision that defined them. If a linked table or column no longer exists in the active model, the page displays a **Stale model links** warning with the document, target and defining revision. The warning does not delete or retarget evidence automatically; review and remove or replace the link explicitly.

## Save an evidence snapshot

Run a project evidence search and select **Save evidence snapshot**. The application reruns the same deterministic, project-scoped retrieval and stores its query, source filter, active model revision, actor and bounded result payload. Saved snapshots appear on the Knowledge page and preserve the evidence returned at that time even if documents, samples or the active model later change.

Open a snapshot to review its schema, relationship, document and sample evidence. Stored document results retain chunk identifiers and link back to their citation when the chunk still exists. Select **Delete snapshot** to remove the saved record. Creating and deleting snapshots is audited. A snapshot is evidence history, not an AI answer and not an instruction to execute an action.

## Search all local evidence

Enter terms in **Search project evidence** and optionally filter to schema, documents or sample values. The combined result page can contain:

- Authoritative tables and fields from the active approved structured revision.
- Direct relationships whose endpoints, label or cardinality match the query.
- Document chunks ranked by FTS5. All entered terms must match a chunk.
- Bounded representative values from the project's sample datasets, labelled with dataset, table, row and classification.

Every source is project-scoped. Schema results link to the catalogue, relationships to the diagram workbench, sample evidence to its dataset, and document results to the stored chunk citation page. Document excerpts remain escaped when rendered.

When a query contains two or more schema concepts, the search service resolves matching table/field endpoints and performs a bounded breadth-first traversal of the active relationship graph. It returns shortest paths of at most four hops, with each field-to-field edge shown as evidence. For example, `supplier invoice` can show a route through purchase orders when those relationships exist in the approved model. Traversal is deterministic and does not invent missing edges.

Document content is evidence, not executable instruction. Search results do not modify the catalogue or execute actions.
