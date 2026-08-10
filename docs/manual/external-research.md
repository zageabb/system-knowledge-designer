# Privacy-controlled external research

Open **External research** from a project workbench. The feature uses Wikipedia as a fixed public provider and is disabled by default under **Settings → External research**.

## Review before sending

Enter a public research question and select **Prepare sanitised query**. This local step removes URLs, email addresses, IP addresses, UUIDs, long numbers and quoted passages, then limits output to twelve generic terms. If fewer than two useful terms remain, the query is rejected.

The activity card displays both the original local question and the exact outbound text. Nothing is sent during preparation. When external research is enabled, select **Confirm and send to Wikipedia** to make the request. A prepared query cannot be edited invisibly; prepare another job if the outbound wording is unsuitable.

## Results, citations and failures

The job records proposed, running, completed or failed status. Completed jobs retain up to five source titles, fixed Wikipedia URLs and short excerpts. External links open separately with opener access disabled.

Select **Cancel unsent proposal** to cancel a prepared query before it reaches the provider. Only `proposed` jobs can be cancelled. Once **Confirm and send** starts the current synchronous provider request, it cannot be interrupted from the browser.

For a failed job, select **Prepare reviewed retry**. This creates a new proposed job with the same already-sanitised outbound text and records its source job. Retry does not contact Wikipedia automatically: review the new card and select **Confirm and send** separately. Completed, running, proposed and cancelled jobs cannot use the retry action.

If the provider is unavailable, the job is marked failed and no catalogue, document, model or sample data changes. Use **Local knowledge search** to continue entirely within the project. External results do not automatically enter the local knowledge index or assistant context.

## Promote selected evidence

After reviewing a completed result, select **Add selected citation to local knowledge** beside the individual citation you want to retain. This is a separate explicit write: the application validates the fixed Wikipedia URL, creates a managed Markdown source, labels it `external-wikipedia` and `public`, creates its initial version, and indexes one citation chunk containing the title, excerpt and source URL.

The job and citation number are permanently mapped to the local document, preventing duplicate promotion. The resulting item behaves like other project knowledge: it can be searched, cited, linked and deleted. Deleting it also removes its promotion mapping and search entry. Promotion stores only the returned bounded excerpt, not the full Wikipedia page.

Do not put confidential identifiers into an external research question. Sanitisation reduces common accidental disclosure shapes but is not a substitute for user review of the exact outbound query or the selected evidence.
