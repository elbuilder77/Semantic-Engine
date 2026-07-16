# Checklist

1. [ ] Identify the API endpoint(s) under test and their expected contracts (request/response payloads, headers, auth).
2. [ ] Locate or create the appropriate test suite file according to project conventions.
3. [ ] Implement a test for the "Happy Path" (200 OK, expected data structure).
4. [ ] Implement tests for common failure modes (400 Bad Request, 401 Unauthorized, 404 Not Found, 500 Server Error).
5. [ ] Mock external dependencies if the test is unit/integration level, or ensure staging environment is configured for E2E.
6. [ ] Execute the test suite using project-specific commands (e.g., `npm test`, `pytest`, `cargo test`).
7. [ ] Analyze test output; if failures occur, diagnose and refactor the code or adjust the test if the contract changed.
