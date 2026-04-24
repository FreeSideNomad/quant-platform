# Tenancy, Identity, and Authorisation

## Silo tenancy model

Each customer receives a dedicated instance of the platform. There is no shared database, no shared application process, and no row-level isolation between customers. Tenant boundary is infrastructure boundary: a separate Cloud Run service, a separate Cloud SQL instance, a separate GCS bucket, all within a separate GCP project.

This choice makes the application code materially simpler — there is no tenant identifier on any row, no row-level security policies, no tenant context middleware, no noisy-neighbour reasoning — at the cost of higher per-tenant infrastructure floor. The trade is correct for this customer segment: hedge funds demand isolation, and the minimum infrastructure cost is well below their willingness to pay.

The control plane (described in the infrastructure chapter) maintains a registry of tenants and coordinates their lifecycle. The application itself knows only that it is running for one customer and reads its configuration from environment variables and Secret Manager on startup.

## Identity federation

Customers authenticate their users through their own enterprise identity provider. Two provider types cover the target market:

- **Google Workspace** — an OIDC provider with Google's standard discovery endpoint, issuing ID tokens signed by Google
- **Microsoft Entra (formerly Azure AD)** — an OIDC provider with per-tenant issuer URLs, optionally enriched with group or application role claims

The application does not maintain user passwords, MFA enrolment, or session state beyond the scope of a single browser session. All authentication ceremony happens in the customer's directory. The application trusts the customer's identity provider to assert a verified user identity and builds its own session on top of that assertion.

## Authentication flow

The flow follows the standard OIDC Authorisation Code exchange with PKCE. The application hosts four endpoints on its authentication router: `GET /auth/login`, `GET /auth/callback`, `POST /auth/refresh`, and `POST /auth/logout`.

![OIDC authentication sequence](diagrams/rendered/03-oidc-sequence.pdf){width=95%}

On first request, the React SPA redirects to `/auth/login`, which constructs the authorisation URL against the customer's configured OIDC provider and redirects the browser. The user authenticates against their corporate directory. The provider redirects back to `/auth/callback` with an authorisation code. The application exchanges the code for an ID token, verifies the token's signature against the provider's JWKS, extracts the verified identity claims, and issues its own session JWT. The session JWT is returned to the browser as an HTTP-only, SameSite=strict cookie.

The session JWT is the only credential the React application ever handles. It contains the user identifier, the roles granted to the user in the application domain, and a short expiry (typically fifteen minutes). A longer-lived refresh token is stored separately and used by `/auth/refresh` to mint new session tokens without redirecting to the identity provider.

## Session JWT content

The session token is signed by the application using a key stored in Secret Manager (rotated on a schedule). It carries only the claims the application itself needs:

- **`sub`** — a stable internal user identifier, derived from the external provider's subject claim
- **`email`** — the user's email address, for logging and display
- **`roles`** — application-specific role strings (e.g. `quant`, `risk`, `admin`, `viewer`)
- **`iat`, `exp`** — issuance and expiry timestamps
- **`jti`** — a unique token identifier, used for revocation

The token is validated on every request by a FastAPI dependency that also populates `request.state.user` with the parsed claims. No route handler reads cookies directly or parses tokens; authentication is transparent to business logic.

## Role mapping

Customers' identity providers do not know about the application's role vocabulary. They may emit group memberships (Workspace) or application roles (Entra), but the semantics are the customer's, not the application's.

A `user_roles` table in Postgres maps authenticated users to the application's role vocabulary:

| Column | Purpose |
| :--- | :--- |
| `user_sub` | Stable external subject from the identity provider |
| `email` | Captured at first login for operational convenience |
| `roles` | Array of application role strings |
| `created_at`, `updated_at` | Audit fields |

Two patterns populate this table:

1. **Administrative assignment** — a platform administrator invites users by email and assigns roles before first login. On first authenticated request, the application matches the email claim against the pending invitation and activates the row.

2. **Claim-based mapping** — for customers who have configured their identity provider to emit group or role claims (Entra application roles are the cleanest path), a configuration table maps external claim values to internal roles. On each login, the mapping is applied, and the `user_roles` row is refreshed.

The application never trusts the external provider's groups directly. External claims are inputs to a mapping function owned by the application; roles attached to the session JWT are the output.

## Authorisation enforcement

Authorisation is enforced in two places:

- **At the route** — a FastAPI dependency decorates each protected endpoint with the roles it requires. Requests from users lacking the required role receive HTTP 403.
- **At the domain** — within command handlers, fine-grained checks apply to entity-level permissions (e.g. a `quant` user may edit their own models but not another user's).

The route-level check is coarse and mandatory; the domain-level check is fine and context-aware. Both are unit-tested.

## Multi-provider support per instance

Each instance is configured with exactly one identity provider. A customer organisation running multiple directories (e.g. a parent company with subsidiaries on different tenants) is served by multiple silo instances, each bound to its own directory. There is no need for intra-instance multi-provider routing, because there is no pool tenancy.

This keeps the auth code path trivially simple: one issuer, one JWKS URL, one client ID, one client secret, one group-mapping configuration. All of these are loaded from Secret Manager at startup.

## Service-to-service authentication

Internal components (the application calling MLflow, the application invoking Cloud Run Jobs for training, the CI/CD pipeline deploying revisions) authenticate using GCP service accounts and Workload Identity Federation. No static credentials, API keys, or service account JSON files exist in the codebase or the container images.

The application's service account is granted the minimum IAM roles required to access its Cloud SQL instance, its GCS bucket, its Secret Manager secrets, and its MLflow backend. Cross-tenant access is prevented at the IAM boundary, not at the application layer.
