# Projects and the ER Workbench

## Create a project

1. Sign in and select **New project**.
2. Enter a name, description and SQL dialect.
3. Select **Create project** to open the workbench.

The starter source demonstrates two tables and a field-level relationship. The three panes contain ER source, the server-rendered Graphviz preview and a structured model summary.

## Validate and save

1. Edit the source using the [ER language reference](../er-language/index.md).
2. Select **Validate**. Syntax and semantic failures include a location where available.
3. Enter a revision note and select **Create revision**.
4. Select **Approve** only after reviewing the diagram and catalogue.

Saving always creates a new draft. If another revision was created after the editor loaded, saving returns a conflict warning instead of overwriting newer work. Reload and reapply the intended changes.

Application notices appear as floating toast notifications in the upper-right corner and do not move the workbench. Select the close button to dismiss one immediately; otherwise it closes automatically after a short interval.

## Navigate the preview

Use minus, plus and fit controls to change scale. The preview has horizontal and vertical scrollbars for diagrams larger than its pane. Relationship lines attach to the outside boundary of their exact source and target field rows.

## Export

After creating a revision, the workbench offers SVG, 4× PNG, `.erd` source and structured JSON model exports. Render exports come from the complete model, not a browser screenshot.
