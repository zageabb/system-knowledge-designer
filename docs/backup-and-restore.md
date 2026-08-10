# Backup and restore

Stop the application, then copy the catalogue database and the complete `project_data/` directory together. Restore both into the same configured locations before starting the same application version. Verify file ownership, run database migrations, sign in, and validate that active revision hashes and managed artefacts match. Sandboxes/renders are derived, but retain them when exact proof reproduction matters.

