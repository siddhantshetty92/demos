# Acme Scheduling Security Overview

## Encryption
Customer data is encrypted in transit with TLS 1.2 or higher and at rest with AES-256. Encryption keys are managed by the cloud provider's key management service and rotated annually.

## Single sign-on
Acme Scheduling supports SAML 2.0 and OpenID Connect single sign-on with any standards-based identity provider. SCIM user provisioning is planned for later this year.

## Data residency
Customer data is hosted in the United States by default. EU hosting is available only for Enterprise plans, on request.

## Penetration testing
An independent firm runs a penetration test every year. A summary letter is available under NDA.

## Audit logging
Administrative actions such as role changes, integration changes and exports are written to an audit log retained for 12 months. Field-level change history is not supported.
