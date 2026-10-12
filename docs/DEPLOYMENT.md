# Deployment notes

For development and demos, prefer **stdio** and local execution. Publishing a repository on GitHub is not the same as hosting the MCP server.

For a remote deployment, run the container behind a reverse proxy that validates each inbound MCP client's identity, terminates TLS, applies access policy and limits traffic. Keep the connector and IdentityIQ on an approved private network. Do not expose port 8000 publicly without those controls. See `.env.example` for server transport parameters.

The example `Dockerfile` is for building locally, not proof of production readiness. AWS, ECS or any other hosting service is optional. For AWS, use private subnets, Secrets Manager, network filtering, authenticated ingress and observability, then independently test endpoints before allowing any write operations.
