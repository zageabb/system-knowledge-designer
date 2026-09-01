# Portfolio workflow handover

## Outcome

Replaced the informal convention of representing a portfolio as another system project with a first-class `Portfolio` entity and explicit nullable `SystemProject.portfolio_id` membership.

The dashboard now provides portfolio selection, portfolio project counts, an unassigned-project view, direct project reassignment, and two clear creation paths:

- **New portfolio** creates the portfolio and a required first project in one transaction.
- **New project** optionally assigns the project to an existing portfolio immediately.

## Persistence

Migration `0022_portfolios.sql` creates the portfolio table and adds the indexed project membership foreign key. Existing technical `ProjectLink` records remain reserved for system-to-system dependencies and integrations; portfolio membership no longer overloads those relationship types.

## Safety and evidence

- Portfolio plus first-project creation is atomic and rolls back on constraint failure.
- Portfolio selection is validated before project creation or reassignment.
- Creation and reassignment write audit events.
- Tests cover atomic creation, required first project, filtering, reassignment, direct project assignment, and migration shape.
