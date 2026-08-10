# Central System Map

Open **System map** from the main navigation to record relationships between projects, maintain discovery aliases and inspect bounded portfolio connectivity.

## Project links

Choose source and target projects and one fixed relationship type: `depends-on`, `integrates-with`, `provides-data-to`, or `replaces`. An optional label can capture the interface or business purpose. Self-links and duplicate source/target/type combinations are rejected.

Select a project under **Traverse from** to show connected projects up to three links away. Traversal is limited to fifty projects and does not itself grant access to another project's documents, samples or sandboxes.

## Selected evidence attachments

After linking two projects, choose a consumer project and one source document under **Attach selected evidence**. The selected document becomes searchable from the consumer's **Explicit cross-project evidence** source. Results show the owning project and citations open in that source project.

The project link and document attachment are separate gates. Other source documents, sample datasets and sandboxes remain isolated. An unlinked project cannot receive an attachment. Select **Remove** to revoke an attachment; deleting the source document also removes its attachments.

## Trusted aliases

Aliases provide alternative discovery names for projects. Punctuation and capitalization are normalized when checking uniqueness, so `Vendor-Master` and `vendor master` cannot identify different projects. Administrators may mark an alias trusted; other users can only create untrusted aliases.

A trusted alias can qualify a schema search from a directly linked project. For example, `Vendor Master supplier` searches the linked project identified by the trusted `Vendor Master` alias for `supplier`. Untrusted aliases and aliases belonging to unlinked projects do not expand the search boundary.

## Integrity scans

Select **Run integrity scan** to check the central graph for self-links, missing project endpoints, invalid active revisions, orphan aliases and invalid or unlinked attachments. Each result is persisted with its status, issue count, requester, timestamp and JSON evidence. A clean scan reports zero issues.
