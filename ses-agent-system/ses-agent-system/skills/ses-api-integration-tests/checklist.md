# Checklist

- Locate endpoint implementation and route registration.
- Locate existing tests for the endpoint.
- Confirm the expected request/response contract.
- Reproduce current behavior or failure.
- Fix the endpoint or test assumptions if needed.
- Add integration coverage for the happy path.
- Add integration coverage for at least one realistic failure path.
- Validate the endpoint inside the normal local test flow.
- Validate the endpoint in Docker Compose if the stack requires services.
- Record exact commands and results.
