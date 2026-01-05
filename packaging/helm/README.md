# Helm Chart

This directory contains the Helm chart for deploying Claude Code Proxy on Kubernetes.

## Structure

```
claude-code-proxy/
├── Chart.yaml              # Chart metadata
├── values.yaml             # Default configuration values
├── .helmignore            # Files to ignore when packaging
└── templates/
    ├── _helpers.tpl       # Template helpers
    ├── NOTES.txt         # Post-install notes
    ├── deployment.yaml   # Deployment configuration
    ├── service.yaml      # Service definition
    ├── serviceaccount.yaml # ServiceAccount
    ├── ingress.yaml      # Ingress configuration
    ├── configmap.yaml    # ConfigMap for environment variables
    ├── pvc.yaml          # PersistentVolumeClaim for /data
    ├── hpa.yaml          # HorizontalPodAutoscaler
    └── pdb.yaml          # PodDisruptionBudget
```

## Quick Start

### From Helm Repository

```bash
# Add the Helm repository
helm repo add claude-code-proxy https://joachimbrindeau.github.io/claude-proxy-multi

# Update repository cache
helm repo update

# Install the chart
helm install my-proxy claude-code-proxy/claude-code-proxy
```

### From Local Chart

```bash
# Install from this directory
helm install my-proxy ./claude-code-proxy
```

## Chart Repository Setup

This chart is published to GitHub Pages using chart-releaser-action.

### Helm Repository URL

```
https://joachimbrindeau.github.io/claude-proxy-multi
```

### gh-pages Branch Setup

The Helm chart repository is hosted on the `gh-pages` branch. The chart-releaser GitHub Action automatically:

1. Packages the Helm chart
2. Creates GitHub releases for each chart version
3. Updates the `index.yaml` in the `gh-pages` branch
4. Makes charts available at the repository URL

**Setup Steps** (one-time):

1. Enable GitHub Pages in repository settings:
   - Go to Settings > Pages
   - Source: Deploy from a branch
   - Branch: `gh-pages` / `root`
   - Save

2. The `gh-pages` branch will be created automatically by chart-releaser-action on first release.

3. Verify the chart index is accessible:
   ```bash
   curl https://joachimbrindeau.github.io/claude-proxy-multi/index.yaml
   ```

## Development

### Lint Chart

```bash
helm lint ./claude-code-proxy
```

### Template Rendering

```bash
# Render all templates
helm template my-proxy ./claude-code-proxy

# Render with custom values
helm template my-proxy ./claude-code-proxy -f custom-values.yaml

# Debug mode
helm template my-proxy ./claude-code-proxy --debug
```

### Dry Run Install

```bash
helm install --dry-run --debug my-proxy ./claude-code-proxy
```

### Test Installation Locally

```bash
# Install to local cluster
helm install test-proxy ./claude-code-proxy \
  --namespace test \
  --create-namespace \
  --set persistence.size=100Mi

# Check status
helm status test-proxy -n test

# Uninstall
helm uninstall test-proxy -n test
```

### Package Chart

```bash
# Package the chart
helm package ./claude-code-proxy

# This creates: claude-code-proxy-<version>.tgz
```

## Release Process

Helm charts are automatically released when a Git tag is pushed:

1. Tag the release:
   ```bash
   git tag -a v0.1.7 -m "Release v0.1.7"
   git push origin v0.1.7
   ```

2. GitHub Actions workflow:
   - Updates Chart.yaml version and appVersion
   - Lints the chart
   - Packages the chart
   - Runs chart-releaser to publish to gh-pages

3. Chart is available at:
   ```
   https://joachimbrindeau.github.io/claude-proxy-multi
   ```

## Configuration

See [docs/installation/kubernetes.md](../../docs/installation/kubernetes.md) for comprehensive configuration options and examples.

### Key Configuration Sections

- **Image**: Container registry and tag
- **Service**: Type (ClusterIP, LoadBalancer, NodePort)
- **Persistence**: PVC for /data directory
- **Ingress**: External access with optional TLS
- **Resources**: CPU and memory limits
- **Autoscaling**: HPA configuration
- **Environment**: Application settings

## Testing

### Unit Tests

```bash
# Install helm-unittest plugin
helm plugin install https://github.com/helm-unittest/helm-unittest

# Run tests (if test files exist)
helm unittest ./claude-code-proxy
```

### Integration Tests

```bash
# Install to test namespace
helm install test-integration ./claude-code-proxy \
  --namespace test \
  --create-namespace \
  --wait \
  --timeout 5m

# Test health endpoint
kubectl run curl --rm -it --image=curlimages/curl -- \
  curl http://test-integration-claude-code-proxy.test:8000/health

# Cleanup
helm uninstall test-integration -n test
kubectl delete namespace test
```

## Chart Versioning

- Chart version: Follows SemVer (e.g., 0.1.0)
- App version: Matches Docker image tag (e.g., 0.1.7)
- Both are updated automatically during release

## Values Schema Validation

The chart supports JSON schema validation for values:

```bash
# Validate values against schema (if schema file exists)
helm lint ./claude-code-proxy --strict
```

## References

- [Helm Documentation](https://helm.sh/docs/)
- [Chart Best Practices](https://helm.sh/docs/chart_best_practices/)
- [Chart Template Guide](https://helm.sh/docs/chart_template_guide/)
- [Helm Chart Releaser](https://github.com/helm/chart-releaser)
- [GitHub Pages Deployment](https://docs.github.com/en/pages)
