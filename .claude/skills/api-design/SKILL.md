---
name: api-design
description: Design a RESTful or GraphQL API: resource naming, HTTP methods, status codes, request/response schemas (OpenAPI 3.1), authentication, versioning, error format. Produces OpenAPI spec + design rationale. Use when designing new API endpoints or reviewing existing ones. Invoke as: /api-design "<api description or existing spec path>"
---

# API Design

Design production-quality REST APIs with OpenAPI 3.1 spec.

## Steps
1. Parse the requirement or existing spec
2. Define resources (nouns, not verbs): /users, /orders/{id}/items
3. Map CRUD to HTTP methods:
   - GET: read (idempotent, cacheable)
   - POST: create (returns 201 + Location header)
   - PUT: full replace (idempotent)
   - PATCH: partial update (JSON Merge Patch or JSON Patch)
   - DELETE: remove (returns 204)
4. Status codes: 200/201/204/400/401/403/404/409/422/429/500
5. Authentication: Bearer JWT, API key, or OAuth2 (document in securitySchemes)
6. Versioning: URL path (/v1/) preferred over headers
7. Pagination: cursor-based for large datasets, offset for small
8. Error format (consistent across all endpoints):
   ```json
   {"error": {"code": "VALIDATION_ERROR", "message": "...", "details": [...]}}
   ```

## OpenAPI Spec Output
```yaml
openapi: 3.1.0
info:
  title: API Name
  version: 1.0.0
paths:
  /resource:
    post:
      summary: Create resource
      requestBody:
        required: true
        content:
          application/json:
            schema: {$ref: '#/components/schemas/ResourceCreate'}
      responses:
        '201':
          description: Created
          content:
            application/json:
              schema: {$ref: '#/components/schemas/Resource'}
```

## Rules
- Resource names: plural nouns (/users not /user)
- Never verbs in paths: /users/activate not /activateUser
- Always return consistent error schema
- Rate limiting documented in headers (X-RateLimit-*)

## Related Skills
- /prd-writer — requirements that drive API design
- /architect-adr — document API design decisions
- /test-writer — write API integration tests
